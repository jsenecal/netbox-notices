from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from tenancy.models import ContactAssignment

__all__ = ("RecipientDiscoveryService", "discover_recipients")


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

        # Get impacts from the event
        impacts = self._get_impacts(event)

        if granularity == MessageGranularityChoices.PER_EVENT:
            return self._discover_per_event(impacts)
        elif granularity == MessageGranularityChoices.PER_TENANT:
            return self._discover_per_tenant(impacts)
        elif granularity == MessageGranularityChoices.PER_IMPACT:
            return self._discover_per_impact(impacts)
        else:
            return self._discover_per_event(impacts)

    def discover_for_tenant(self, tenant):
        """
        Discover recipients for a specific tenant.

        Args:
            tenant: Tenant instance

        Returns:
            list of Contact objects
        """
        return self._get_contacts_for_tenant(tenant)

    def _get_impacts(self, event):
        """Get impact records from an event."""
        # Check for different impact relation names
        if hasattr(event, "impacts"):
            return list(event.impacts.all())
        elif hasattr(event, "circuitmaintenanceimpact_set"):
            return list(event.circuitmaintenanceimpact_set.all())
        return []

    def _get_tenant_from_impact(self, impact):
        """Extract tenant from an impact's target object."""
        # Impact models have different field names for the target
        target = None
        if hasattr(impact, "circuit"):
            target = impact.circuit
        elif hasattr(impact, "target"):
            target = impact.target

        if target and hasattr(target, "tenant"):
            return target.tenant
        return None

    def _discover_per_event(self, impacts):
        """Discover all contacts for all tenants in the event."""
        contacts = set()
        seen_tenants = set()

        for impact in impacts:
            tenant = self._get_tenant_from_impact(impact)
            if tenant and tenant.pk not in seen_tenants:
                seen_tenants.add(tenant.pk)
                contacts.update(self._get_contacts_for_tenant(tenant))

        return list(contacts)

    def _discover_per_tenant(self, impacts):
        """Group contacts by tenant."""
        result = {}

        for impact in impacts:
            tenant = self._get_tenant_from_impact(impact)
            if tenant and tenant not in result:
                result[tenant] = self._get_contacts_for_tenant(tenant)

        return result

    def _discover_per_impact(self, impacts):
        """Get contacts for each impact separately."""
        result = {}

        for impact in impacts:
            tenant = self._get_tenant_from_impact(impact)
            if tenant:
                result[impact] = self._get_contacts_for_tenant(tenant)
            else:
                result[impact] = []

        return result

    def _get_contacts_for_tenant(self, tenant):
        """
        Get contacts assigned to a tenant matching role/priority filters.

        Queries ContactAssignment to find contacts with matching roles and priorities.
        """
        if not tenant:
            return []

        # Get content type for tenant
        tenant_ct = ContentType.objects.get_for_model(tenant)

        # Build filter for ContactAssignment
        # Note: NetBox uses 'object_type' for the content type field, not 'content_type'
        filters = Q(object_id=tenant.pk) & Q(object_type=tenant_ct)

        # Filter by roles if specified
        if self.roles:
            filters &= Q(role__in=self.roles)

        # Filter by priorities if specified (exclude 'inactive')
        if self.priorities:
            filters &= Q(priority__in=self.priorities)
        filters &= ~Q(priority="inactive")

        # Get contact assignments for this tenant
        assignments = ContactAssignment.objects.filter(filters).select_related("contact")

        # Return unique contacts
        contacts = []
        seen = set()
        for assignment in assignments:
            if assignment.contact_id not in seen:
                seen.add(assignment.contact_id)
                contacts.append(assignment.contact)

        return contacts


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
