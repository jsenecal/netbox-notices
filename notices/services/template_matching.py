# notices/services/template_matching.py
"""
Template matching service for finding and merging templates based on context.

Similar to NetBox Config Contexts, templates are matched by their scopes
and merged by weight to produce final template configuration.
"""

from django.db.models import Q

from notices.choices import MessageEventTypeChoices

__all__ = ("TemplateMatchingService", "kinds_for_event", "merge_templates", "resolve_chain")


class TemplateMatchingService:
    """
    Service for finding and merging templates based on context.

    Similar to NetBox Config Contexts, templates are matched by their scopes
    and merged by weight to produce final template configuration.
    """

    def __init__(self, event=None, tenant=None, provider=None):
        """
        Initialize with context objects.

        Args:
            event: Maintenance or Outage instance
            tenant: Tenant instance
            provider: Provider instance
        """
        self.event = event
        self.tenant = tenant
        self.provider = provider
        self.event_type = self._get_event_type()
        self.event_status = getattr(event, "status", None) if event else None

    def _get_event_type(self):
        """Determine event type from event object."""
        if not self.event:
            return "none"
        model_name = self.event.__class__.__name__.lower()
        if "maintenance" in model_name:
            return "maintenance"
        elif "outage" in model_name:
            return "outage"
        return "none"

    def score(self, template):
        """Return the template's score for this context, or None when it does not apply."""
        scopes = list(template.scopes.all())
        if not scopes:
            return template.weight
        matched = [scope.weight for scope in scopes if self._scope_matches(scope)]
        if not matched:
            return None
        return template.weight + sum(matched)

    def _scope_matches(self, scope):
        """Check if a scope matches the current context."""
        # Check event type filter
        if scope.event_type:
            if scope.event_type == MessageEventTypeChoices.BOTH:
                if self.event_type not in ("maintenance", "outage"):
                    return False
            elif scope.event_type != self.event_type:
                return False

        # Check event status filter
        if scope.event_status and self.event_status:
            if scope.event_status != self.event_status:
                return False

        # Check object match
        ct = scope.content_type
        obj_id = scope.object_id

        # Get the object to check against
        target_obj = self._get_context_object(ct)

        if target_obj is None:
            # No matching context object provided
            return obj_id is None  # Only match if scope is wildcard

        # Wildcard (all of this type) or specific match
        if obj_id is None:
            return True  # Wildcard matches

        return obj_id == target_obj.pk

    def _get_context_object(self, content_type):
        """Get the context object matching a content type."""
        model_name = content_type.model.lower()

        if model_name == "tenant" and self.tenant:
            return self.tenant
        elif model_name == "provider" and self.provider:
            return self.provider
        elif self.event:
            # Check if event has this attribute (e.g., event.provider)
            if hasattr(self.event, model_name):
                return getattr(self.event, model_name)
        return None


def kinds_for_event(event):
    """Independent notification kinds for an event: non-base templates that override nothing."""
    from notices.models import NotificationTemplate

    event_type = event._meta.model_name
    return (
        NotificationTemplate.objects.filter(
            Q(event_type=event_type) | Q(event_type=MessageEventTypeChoices.BOTH),
            is_base_template=False,
        )
        .filter(Q(extends__isnull=True) | Q(extends__is_base_template=True))
        .prefetch_related("scopes__content_type", "contact_roles")
    )


def resolve_chain(root, matcher):
    """
    Return the inheritance chain to render for one recipient group, most specific first.

    Starting at the root kind, descend into the highest-scoring override that applies to the
    matcher's context and event type, repeatedly; then append the root's base-template
    ancestors, which only contribute layout and fallback fields.
    """
    chain = [root]
    current = root
    while True:
        scored = [
            (score, child)
            for child in current.children.filter(
                Q(event_type=matcher.event_type) | Q(event_type=MessageEventTypeChoices.BOTH),
                is_base_template=False,
            ).prefetch_related("scopes__content_type")
            if (score := matcher.score(child)) is not None
        ]
        if not scored:
            break
        scored.sort(key=lambda pair: pair[0], reverse=True)
        current = scored[0][1]
        chain.insert(0, current)
    ancestor = root.extends
    while ancestor is not None:
        chain.append(ancestor)
        ancestor = ancestor.extends
    return chain


def merge_templates(templates):
    """
    Merge an inheritance chain with field-level precedence.

    The first (most specific) template's non-empty fields win.

    Args:
        templates: inheritance chain, most specific first (see resolve_chain)

    Returns:
        Dict with merged configuration
    """
    if not templates:
        return None

    # Start with empty config
    config = {
        "subject_template": "",
        "body_template": "",
        "body_format": "",
        "headers_template": {},
        "css_template": "",
        "ical_template": "",
        "include_ical": False,
        "contact_roles": set(),
        "contact_priorities": set(),
    }

    # Process templates from highest to lowest score
    for template in templates:
        # Subject - first non-empty wins
        if not config["subject_template"] and template.subject_template:
            config["subject_template"] = template.subject_template

        # Body - first non-empty wins
        if not config["body_template"] and template.body_template:
            config["body_template"] = template.body_template
            config["body_format"] = template.body_format

        # Headers - merge dicts, higher priority keys win
        if template.headers_template:
            for key, value in template.headers_template.items():
                if key not in config["headers_template"]:
                    config["headers_template"][key] = value

        # CSS - first non-empty wins
        if not config["css_template"] and template.css_template:
            config["css_template"] = template.css_template

        # iCal - first non-empty wins
        if not config["ical_template"] and template.ical_template:
            config["ical_template"] = template.ical_template

        # Include iCal - OR of all templates
        if template.include_ical:
            config["include_ical"] = True

        # Contact roles - union of all
        config["contact_roles"].update(template.contact_roles.all())

        # Contact priorities - union of all
        if template.contact_priorities:
            config["contact_priorities"].update(template.contact_priorities)

    # Granularity belongs to the root kind, i.e. the last non-base entry of the chain
    config["granularity"] = next(
        (t.granularity for t in reversed(templates) if not t.is_base_template), templates[-1].granularity
    )

    # Convert sets to lists for JSON compatibility
    config["contact_roles"] = list(config["contact_roles"])
    config["contact_priorities"] = list(config["contact_priorities"])

    return config
