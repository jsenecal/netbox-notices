from datetime import UTC

import markdown
from django.conf import settings
from django.utils import timezone
from django.utils.html import strip_tags
from jinja2 import BaseLoader, Environment, TemplateSyntaxError

__all__ = ("TemplateRenderer", "TemplateRenderError", "split_body")


class TemplateRenderError(Exception):
    """Raised when template rendering fails."""


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
        dt = dt.astimezone(UTC)
    return dt.strftime("%Y%m%dT%H%M%SZ")


def render_markdown(text):
    """Render markdown text to HTML."""
    if not text:
        return ""
    return markdown.markdown(
        text,
        extensions=["tables", "fenced_code", "nl2br"],
    )


class ChainEnvironment(Environment):
    """Jinja environment where `{% extends "base" %}` means "my own parent template"."""

    def __init__(self, parents, **kwargs):
        super().__init__(**kwargs)
        self.parents = parents

    def join_path(self, template, parent):
        if template == "base" and parent in self.parents:
            return self.parents[parent]
        return template


def split_body(body_format, rendered):
    """Return (body_text, body_html) for a rendered body according to its format."""
    if body_format == "markdown":
        return rendered, render_markdown(rendered)
    if body_format == "html":
        return strip_tags(rendered).strip(), rendered
    return rendered, ""


class TemplateRenderer:
    """
    Renders Jinja templates with message context.

    Provides custom filters for iCal datetime formatting and Markdown rendering.
    """

    def __init__(self, templates=None, parents=None):
        """
        Initialize renderer.

        Args:
            templates: Optional dict of template_name -> template_string for inheritance
            parents: Optional dict of slug -> parent_slug for chain inheritance
        """
        loader = StringLoader(templates) if templates else None
        if parents:
            self.env = ChainEnvironment(
                parents=parents,
                loader=loader,
                autoescape=False,
            )
        else:
            self.env = Environment(
                loader=loader,
                autoescape=False,
            )
        # Register custom filters
        self.env.filters["ical_datetime"] = ical_datetime
        self.env.filters["markdown"] = render_markdown

    def _safe_render(self, template, context, prefix="Template rendering failed"):
        """
        Safely render a template, wrapping any exception in TemplateRenderError.

        Args:
            template: Jinja2 template object
            context: Dict of template variables
            prefix: Error message prefix

        Returns:
            Rendered string

        Raises:
            TemplateRenderError: For any error during rendering
        """
        try:
            return template.render(**context)
        except Exception as e:
            raise TemplateRenderError(f"{prefix}: {e}")

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
            return self._safe_render(template, context)
        except TemplateRenderError:
            raise
        except Exception as e:
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

    @classmethod
    def for_chain(cls, chain):
        """Renderer whose loader knows every template in an inheritance chain by slug."""
        templates = {t.slug: t.body_template or "" for t in chain}
        parents = {t.slug: t.extends.slug for t in chain if t.extends_id is not None or t.extends is not None}
        return cls(templates=templates, parents=parents)

    def render_body(self, chain, context):
        """Render the most specific non-empty body in the chain, with inheritance and context."""
        source = next((t for t in chain if t.body_template), None)
        if source is None:
            return ""
        try:
            template = self.env.get_template(source.slug)
        except Exception as e:
            raise TemplateRenderError(f"Template rendering failed: {e}")
        return self._safe_render(template, context)

    @classmethod
    def build_context(cls, notification_template, event=None, tenant=None, impacts=None, **extra):
        """
        Build the full template context for rendering.

        Args:
            notification_template: The NotificationTemplate being rendered
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
