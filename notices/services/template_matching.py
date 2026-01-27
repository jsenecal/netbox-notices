# notices/services/template_matching.py
"""
Template matching service for finding and merging templates based on context.

Similar to NetBox Config Contexts, templates are matched by their scopes
and merged by weight to produce final template configuration.
"""

from django.db.models import Q

from notices.choices import MessageEventTypeChoices

__all__ = ("TemplateMatchingService", "find_matching_templates", "merge_templates")


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

    def find_templates(self):
        """
        Find all templates matching the current context.

        Returns:
            List of (template, score) tuples sorted by score descending
        """
        # Get candidate templates by event type
        candidates = self._get_candidates_by_event_type()

        # Score each template
        scored = []
        for template in candidates:
            score, matches = self._score_template(template)
            if matches:
                scored.append((template, score))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    def get_best_template(self):
        """Get the highest-scoring matching template."""
        templates = self.find_templates()
        return templates[0][0] if templates else None

    def get_merged_config(self):
        """
        Get merged template configuration.

        Returns:
            Dict with merged field values from all matching templates
        """
        templates = self.find_templates()
        if not templates:
            return None

        return merge_templates([t for t, _ in templates])

    def _get_candidates_by_event_type(self):
        """Get templates filtered by event type."""
        from notices.models import MessageTemplate

        if self.event_type == "maintenance":
            return MessageTemplate.objects.filter(
                Q(event_type=MessageEventTypeChoices.MAINTENANCE) | Q(event_type=MessageEventTypeChoices.BOTH)
            ).prefetch_related("scopes", "scopes__content_type", "contact_roles")
        elif self.event_type == "outage":
            return MessageTemplate.objects.filter(
                Q(event_type=MessageEventTypeChoices.OUTAGE) | Q(event_type=MessageEventTypeChoices.BOTH)
            ).prefetch_related("scopes", "scopes__content_type", "contact_roles")
        else:
            return MessageTemplate.objects.filter(event_type=MessageEventTypeChoices.NONE).prefetch_related(
                "scopes", "scopes__content_type", "contact_roles"
            )

    def _score_template(self, template):
        """
        Calculate score for a template.

        Returns:
            (score, matches) where matches is True if template should be included
        """
        score = template.weight
        scopes = list(template.scopes.all())

        # No scopes = global default, always matches
        if not scopes:
            return score, True

        # Check each scope
        has_match = False
        for scope in scopes:
            if self._scope_matches(scope):
                score += scope.weight
                has_match = True

        return score, has_match

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


def merge_templates(templates):
    """
    Merge multiple templates with field-level precedence.

    Templates should be ordered by score (highest first).
    Higher-scored template's non-empty fields win.

    Args:
        templates: List of MessageTemplate instances (highest score first)

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
        "extends": None,
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

        # Extends - first non-null wins
        if not config["extends"] and template.extends:
            config["extends"] = template.extends

    # Convert sets to lists for JSON compatibility
    config["contact_roles"] = list(config["contact_roles"])
    config["contact_priorities"] = list(config["contact_priorities"])

    return config


def find_matching_templates(event=None, tenant=None, provider=None):
    """
    Convenience function to find matching templates.

    Args:
        event: Optional Maintenance or Outage instance
        tenant: Optional Tenant instance
        provider: Optional Provider instance

    Returns:
        List of (template, score) tuples sorted by score descending
    """
    service = TemplateMatchingService(event=event, tenant=tenant, provider=provider)
    return service.find_templates()
