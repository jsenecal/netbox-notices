# notices/services/ical_generation.py
"""
iCal Generation Service for BCOP-compliant maintenance notifications.

This module provides functionality to generate iCal calendar attachments
that comply with the BCOP (Best Current Operating Practice) Maintnote standard.
"""

from notices.services.template_renderer import TemplateRenderer

__all__ = ("ICalGenerationService", "generate_ical", "DEFAULT_BCOP_ICAL_TEMPLATE")


# Default BCOP-compliant iCal template that can be used as reference
# fmt: off
# ruff: noqa: E501
DEFAULT_BCOP_ICAL_TEMPLATE = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//NetBox//netbox-notices//EN
METHOD:PUBLISH
BEGIN:VEVENT
DTSTAMP:{{ now|ical_datetime }}
DTSTART:{{ maintenance.start|ical_datetime }}
DTEND:{{ maintenance.end|ical_datetime }}
UID:{{ maintenance.pk }}{% if tenant %}-{{ tenant.pk }}{% endif %}@netbox
SUMMARY:{{ maintenance.summary|default(maintenance.name) }}
DESCRIPTION:Provider: {{ maintenance.provider.name }}\\nStatus: {{ maintenance.status }}{% if maintenance.internal_ticket %}\\nTicket: {{ maintenance.internal_ticket }}{% endif %}
SEQUENCE:{{ message_sequence }}
STATUS:{{ maintenance.status|default("TENTATIVE") }}
X-MAINTNOTE-PROVIDER:{{ maintenance.provider.slug }}
{% if tenant %}X-MAINTNOTE-ACCOUNT:{{ tenant.name }}{% endif %}
X-MAINTNOTE-MAINTENANCE-ID;X-MAINTNOTE-PRECEDENCE=PRIMARY:{{ maintenance.name }}
{% for impact in tenant_impacts %}X-MAINTNOTE-OBJECT-ID:{{ impact.target.cid|default(impact.target) }}
{% endfor %}X-MAINTNOTE-IMPACT:{{ highest_impact|default("NO-IMPACT") }}
X-MAINTNOTE-STATUS:{{ maintenance.status }}
END:VEVENT
END:VCALENDAR"""
# fmt: on


class ICalGenerationService:
    """
    Generates BCOP-compliant iCal attachments for maintenance notifications.

    Only generates iCal for Maintenance events, not Outages.

    BCOP Maintnote standard properties included:
    - X-MAINTNOTE-PROVIDER: Provider slug/name
    - X-MAINTNOTE-ACCOUNT: Tenant name
    - X-MAINTNOTE-MAINTENANCE-ID: Maintenance name with PRECEDENCE=PRIMARY
    - X-MAINTNOTE-OBJECT-ID: Affected service IDs (one per impact)
    - X-MAINTNOTE-IMPACT: Impact level
    - X-MAINTNOTE-STATUS: Event status
    """

    def __init__(self, template, event, tenant=None, impacts=None):
        """
        Initialize the service.

        Args:
            template: MessageTemplate with ical_template
            event: Maintenance event
            tenant: Target tenant (for per-tenant/per-impact granularity)
            impacts: List of impacts (filtered for tenant if applicable)
        """
        self.template = template
        self.event = event
        self.tenant = tenant
        self.impacts = impacts or []
        self.renderer = TemplateRenderer()

    def should_generate(self):
        """
        Check if iCal should be generated.

        Returns:
            True if:
            - Event is a Maintenance (not Outage)
            - Template has include_ical=True
            - Template has ical_template content

        Returns:
            bool: Whether iCal generation is applicable
        """
        # Must be Maintenance event
        if not self._is_maintenance():
            return False

        # Template must have include_ical=True
        if not getattr(self.template, "include_ical", False):
            return False

        # Template must have ical_template (non-empty string)
        ical_template = getattr(self.template, "ical_template", None)
        if not ical_template or not ical_template.strip():
            return False

        return True

    def generate(self, message_sequence=1):
        """
        Generate the iCal content.

        Args:
            message_sequence: Notification sequence number (for SEQUENCE property)

        Returns:
            Rendered iCal string

        Raises:
            TemplateRenderError: If template rendering fails
            ValueError: If should_generate() returns False
        """
        if not self.should_generate():
            raise ValueError("iCal generation not applicable for this template/event")

        # Build context
        context = self._build_context(message_sequence)

        # Render template
        return self.renderer.render(self.template.ical_template, context)

    def validate_template(self):
        """
        Validate the iCal template syntax.

        Returns:
            True if valid

        Raises:
            TemplateRenderError: If syntax is invalid
        """
        ical_template = getattr(self.template, "ical_template", None)
        if not ical_template or not ical_template.strip():
            return True
        return self.renderer.validate(ical_template)

    def _is_maintenance(self):
        """
        Check if event is a Maintenance.

        Returns:
            bool: True if event is a Maintenance model instance
        """
        if not self.event:
            return False
        model_name = self.event.__class__.__name__.lower()
        return "maintenance" in model_name

    def _build_context(self, message_sequence):
        """
        Build the template context for iCal rendering.

        Args:
            message_sequence: Notification sequence number

        Returns:
            dict: Context variables for template rendering
        """
        context = TemplateRenderer.build_context(
            self.template,
            event=self.event,
            tenant=self.tenant,
            impacts=self.impacts,
        )

        # Ensure maintenance is always in context (for backward compatibility)
        if self.event and "maintenance" not in context:
            context["maintenance"] = self.event

        # Add iCal-specific context
        context["message_sequence"] = message_sequence

        # Ensure highest_impact is calculated
        if "highest_impact" not in context:
            context["highest_impact"] = self._calculate_highest_impact()

        return context

    def _calculate_highest_impact(self):
        """
        Calculate the highest (worst) impact level.

        Returns:
            str: Highest impact level from impacts, or 'NO-IMPACT' if none
        """
        if not self.impacts:
            return "NO-IMPACT"

        impact_order = ["OUTAGE", "DEGRADED", "REDUCED-REDUNDANCY", "NO-IMPACT"]
        highest = "NO-IMPACT"

        for impact in self.impacts:
            impact_level = getattr(impact, "impact", "NO-IMPACT")
            if impact_level and impact_order.index(impact_level) < impact_order.index(highest):
                highest = impact_level

        return highest


def generate_ical(template, event, tenant=None, impacts=None, message_sequence=1):
    """
    Convenience function to generate iCal content.

    Args:
        template: MessageTemplate instance
        event: Maintenance instance
        tenant: Optional Tenant
        impacts: Optional list of impacts
        message_sequence: Notification sequence number

    Returns:
        iCal string or None if not applicable
    """
    service = ICalGenerationService(template, event, tenant, impacts)

    if not service.should_generate():
        return None

    return service.generate(message_sequence)
