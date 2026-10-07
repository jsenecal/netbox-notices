from dataclasses import dataclass

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from tenancy.models import ContactAssignment

__all__ = (
    "RecipientDiscoveryService",
    "RecipientGroup",
    "contacts_for_tenants",
    "discover_recipients",
    "group_impacts",
    "tenant_for_impact",
)


@dataclass(frozen=True)
class RecipientGroup:
    """One outgoing notification's audience: the impacts it covers and whose contacts receive it."""

    tenant: object = None
    impact: object = None
    impacts: tuple = ()
    tenants: tuple = ()


def tenant_for_impact(impact):
    """The tenant owning an impact's target, or None when the target has no tenant."""
    return getattr(impact.target, "tenant", None) if impact.target is not None else None


def group_impacts(event, granularity):
    """Split an event's impacts into recipient groups for the given granularity."""
    from notices.choices import MessageGranularityChoices

    impacts = list(event.impacts.all())
    pairs = [(impact, tenant_for_impact(impact)) for impact in impacts]

    if granularity == MessageGranularityChoices.PER_IMPACT:
        return [
            RecipientGroup(tenant=tenant, impact=impact, impacts=(impact,), tenants=(tenant,) if tenant else ())
            for impact, tenant in pairs
        ]
    if granularity == MessageGranularityChoices.PER_TENANT:
        by_tenant = {}
        for impact, tenant in pairs:
            if tenant is not None:
                by_tenant.setdefault(tenant, []).append(impact)
        return [RecipientGroup(tenant=t, impacts=tuple(i), tenants=(t,)) for t, i in by_tenant.items()]
    tenants = tuple(dict.fromkeys(t for _, t in pairs if t is not None))
    return [RecipientGroup(impacts=tuple(impacts), tenants=tenants)]


def contacts_for_tenants(tenants, roles, priorities):
    """Unique contacts assigned to any of the tenants, filtered by role and priority (never inactive)."""
    tenants = [t for t in tenants if t is not None]
    if not tenants:
        return []
    tenant_ct = ContentType.objects.get_for_model(tenants[0])
    # NetBox names the content type field 'object_type', not 'content_type'.
    filters = Q(object_type=tenant_ct, object_id__in=[t.pk for t in tenants]) & ~Q(priority="inactive")
    if roles:
        filters &= Q(role__in=roles)
    if priorities:
        filters &= Q(priority__in=priorities)
    contacts = {}
    for assignment in ContactAssignment.objects.filter(filters).select_related("contact").order_by("pk"):
        contacts.setdefault(assignment.contact_id, assignment.contact)
    return list(contacts.values())


class RecipientDiscoveryService:
    """
    Discovers recipient contacts for message templates based on event impacts.

    Uses tenant relationships from impacted objects and filters contacts
    by role and priority settings from the template.
    """

    def __init__(self, template):
        """
        Initialize with a MessageTemplate.

        Args:
            template: MessageTemplate instance with contact_roles and contact_priorities
        """
        self.template = template
        self.roles = list(template.contact_roles.all())
        self.priorities = template.contact_priorities or []

    def discover_for_event(self, event, granularity=None):
        """
        Discover recipients for an event based on granularity.

        Args:
            event: Maintenance or Outage instance
            granularity: Override template granularity (per_event, per_tenant, per_impact)

        Returns:
            - per_event: list of Contact objects
            - per_tenant: dict of {tenant: [Contact, ...]}
            - per_impact: dict of {impact: [Contact, ...]}
        """
        from notices.choices import MessageGranularityChoices

        granularity = granularity or self.template.granularity
        groups = group_impacts(event, granularity)

        if granularity == MessageGranularityChoices.PER_TENANT:
            return {g.tenant: self._get_contacts_for_tenant(g.tenant) for g in groups}
        if granularity == MessageGranularityChoices.PER_IMPACT:
            return {g.impact: self._get_contacts_for_tenant(g.tenant) for g in groups}
        return contacts_for_tenants(groups[0].tenants, self.roles, self.priorities)

    def discover_for_tenant(self, tenant):
        """
        Discover recipients for a specific tenant.

        Args:
            tenant: Tenant instance

        Returns:
            list of Contact objects
        """
        return self._get_contacts_for_tenant(tenant)

    def _get_contacts_for_tenant(self, tenant):
        """Contacts assigned to a tenant matching the template's role/priority filters."""
        return contacts_for_tenants([tenant], self.roles, self.priorities)


def discover_recipients(template, event=None, tenant=None, granularity=None):
    """
    Convenience function for recipient discovery.

    Args:
        template: MessageTemplate instance
        event: Optional Maintenance/Outage instance
        tenant: Optional Tenant instance (for standalone messages)
        granularity: Optional granularity override

    Returns:
        Discovered contacts (format depends on granularity)
    """
    service = RecipientDiscoveryService(template)

    if event:
        return service.discover_for_event(event, granularity)
    elif tenant:
        return service.discover_for_tenant(tenant)
    else:
        return []
