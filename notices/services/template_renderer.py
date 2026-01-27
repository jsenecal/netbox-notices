from datetime import timezone as dt_timezone

import markdown
from django.conf import settings
from django.utils import timezone
from jinja2 import BaseLoader, Environment, TemplateSyntaxError, UndefinedError

__all__ = ("TemplateRenderer", "TemplateRenderError")


class TemplateRenderError(Exception):
    """Raised when template rendering fails."""

    pass


class StringLoader(BaseLoader):
    """Jinja loader that loads templates from strings."""

    def __init__(self, templates=None):
        self.templates = templates or {}

    def get_source(self, environment, template):
        if template in self.templates:
            source = self.templates[template]
            return source, template, lambda: True
        raise TemplateSyntaxError(f"Template '{template}' not found", lineno=1)


def ical_datetime(dt):
    """Format datetime as iCal datetime string."""
    if dt is None:
        return ""
    # Convert to UTC and format as YYYYMMDDTHHMMSSZ
    if timezone.is_aware(dt):
        dt = dt.astimezone(dt_timezone.utc)
    return dt.strftime("%Y%m%dT%H%M%SZ")


def render_markdown(text):
    """Render markdown text to HTML."""
    if not text:
        return ""
    return markdown.markdown(
        text,
        extensions=["tables", "fenced_code", "nl2br"],
    )


class TemplateRenderer:
    """
    Renders Jinja templates with message context.

    Provides custom filters for iCal datetime formatting and Markdown rendering.
    """

    def __init__(self, templates=None):
        """
        Initialize renderer.

        Args:
            templates: Optional dict of template_name -> template_string for inheritance
        """
        loader = StringLoader(templates) if templates else None
        self.env = Environment(
            loader=loader,
            autoescape=False,
        )
        # Register custom filters
        self.env.filters["ical_datetime"] = ical_datetime
        self.env.filters["markdown"] = render_markdown

    def render(self, template_string, context):
        """
        Render a template string with context.

        Args:
            template_string: Jinja template string
            context: Dict of template variables

        Returns:
            Rendered string

        Raises:
            TemplateRenderError: If rendering fails
        """
        try:
            template = self.env.from_string(template_string)
            return template.render(**context)
        except (TemplateSyntaxError, UndefinedError) as e:
            raise TemplateRenderError(f"Template rendering failed: {e}")

    def validate(self, template_string):
        """
        Validate template syntax without rendering.

        Args:
            template_string: Jinja template string

        Returns:
            True if valid

        Raises:
            TemplateRenderError: If syntax is invalid
        """
        try:
            self.env.parse(template_string)
            return True
        except TemplateSyntaxError as e:
            raise TemplateRenderError(f"Invalid template syntax: {e}")

    def render_with_inheritance(self, child_template, base_name="base"):
        """
        Render a template that extends a base template.

        Args:
            child_template: Child template string (should have {% extends "base" %})
            base_name: Name of the base template in self.templates

        Returns:
            Rendered string
        """
        try:
            template = self.env.from_string(child_template)
            return template.render()
        except (TemplateSyntaxError, UndefinedError) as e:
            raise TemplateRenderError(f"Template inheritance rendering failed: {e}")

    @classmethod
    def build_context(cls, message_template, event=None, tenant=None, impacts=None, **extra):
        """
        Build the full template context for rendering.

        Args:
            message_template: The MessageTemplate being rendered
            event: Optional Maintenance or Outage event
            tenant: Optional target tenant
            impacts: Optional list of Impact records
            **extra: Additional context variables

        Returns:
            Dict of context variables
        """
        context = {
            "now": timezone.now(),
            "netbox_url": getattr(settings, "BASE_URL", ""),
            "tenant": tenant,
            "impacts": impacts or [],
        }

        if event:
            # Determine event type and add appropriate variables
            event_type = event.__class__.__name__.lower()
            context[event_type] = event

            if event_type == "maintenance":
                context["maintenance"] = event
            elif event_type == "outage":
                context["outage"] = event

            # Filter impacts for this tenant if specified
            if tenant and impacts:
                context["tenant_impacts"] = [
                    i for i in impacts if hasattr(i.target, "tenant") and i.target.tenant == tenant
                ]
            else:
                context["tenant_impacts"] = impacts or []

            # Calculate highest impact
            if impacts:
                impact_order = ["OUTAGE", "DEGRADED", "REDUCED-REDUNDANCY", "NO-IMPACT"]
                highest = "NO-IMPACT"
                for impact in impacts:
                    impact_level = getattr(impact, "impact", None) or "NO-IMPACT"
                    if impact_level in impact_order:
                        if impact_order.index(impact_level) < impact_order.index(highest):
                            highest = impact_level
                context["highest_impact"] = highest

        context.update(extra)
        return context
