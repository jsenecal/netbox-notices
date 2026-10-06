# tests/test_template_renderer.py
from datetime import UTC, datetime

import pytest

from notices.services.template_renderer import (
    TemplateRenderer,
    TemplateRenderError,
    ical_datetime,
    render_markdown,
    split_body,
)


class TestIcalDatetime:
    """Tests for ical_datetime filter."""

    def test_formats_utc_datetime(self):
        """Test formatting a UTC datetime."""
        dt = datetime(2026, 1, 22, 14, 30, 0, tzinfo=UTC)
        result = ical_datetime(dt)
        assert result == "20260122T143000Z"

    def test_converts_timezone(self):
        """Test converting non-UTC timezone to UTC."""
        # Create a datetime in a different timezone
        from zoneinfo import ZoneInfo

        dt = datetime(2026, 1, 22, 9, 30, 0, tzinfo=ZoneInfo("US/Eastern"))
        result = ical_datetime(dt)
        # 9:30 EST = 14:30 UTC
        assert result == "20260122T143000Z"

    def test_handles_none(self):
        """Test handling None input."""
        result = ical_datetime(None)
        assert result == ""


class TestRenderMarkdown:
    """Tests for render_markdown filter."""

    def test_renders_basic_markdown(self):
        """Test rendering basic markdown."""
        result = render_markdown("**bold** and *italic*")
        assert "<strong>bold</strong>" in result
        assert "<em>italic</em>" in result

    def test_renders_tables(self):
        """Test rendering markdown tables."""
        md = """
| Header |
|--------|
| Cell   |
"""
        result = render_markdown(md)
        assert "<table>" in result

    def test_handles_empty(self):
        """Test handling empty input."""
        result = render_markdown("")
        assert result == ""

        result = render_markdown(None)
        assert result == ""


class TestTemplateRenderer:
    """Tests for TemplateRenderer class."""

    def test_render_simple_template(self):
        """Test rendering a simple template."""
        renderer = TemplateRenderer()
        result = renderer.render("Hello {{ name }}!", {"name": "World"})
        assert result == "Hello World!"

    def test_render_with_filter(self):
        """Test rendering with custom filters."""
        renderer = TemplateRenderer()
        dt = datetime(2026, 1, 22, 14, 30, 0, tzinfo=UTC)
        result = renderer.render("{{ dt|ical_datetime }}", {"dt": dt})
        assert result == "20260122T143000Z"

    def test_render_markdown_filter(self):
        """Test rendering with markdown filter."""
        renderer = TemplateRenderer()
        result = renderer.render("{{ text|markdown }}", {"text": "**bold**"})
        assert "<strong>bold</strong>" in result

    def test_render_invalid_syntax_raises(self):
        """Test that invalid syntax raises error."""
        renderer = TemplateRenderer()
        with pytest.raises(TemplateRenderError, match="rendering failed"):
            renderer.render("{{ invalid syntax }}", {})

    def test_render_runtime_error_wrapped(self):
        """Test that runtime errors in templates are wrapped in TemplateRenderError."""
        renderer = TemplateRenderer()
        with pytest.raises(TemplateRenderError, match="rendering failed"):
            renderer.render("{{ 1/0 }}", {})

    def test_validate_valid_template(self):
        """Test validating a valid template."""
        renderer = TemplateRenderer()
        assert renderer.validate("Hello {{ name }}!") is True

    def test_validate_invalid_template(self):
        """Test validating an invalid template."""
        renderer = TemplateRenderer()
        with pytest.raises(TemplateRenderError, match="Invalid template syntax"):
            renderer.validate("{% if unclosed")

    def test_build_context_minimal(self):
        """Test building minimal context."""
        from notices.choices import MessageEventTypeChoices
        from notices.models import NotificationTemplate

        template = NotificationTemplate(
            name="Test",
            slug="test",
            event_type=MessageEventTypeChoices.NONE,
            subject_template="S",
            body_template="B",
        )

        context = TemplateRenderer.build_context(template)

        assert "now" in context
        assert "netbox_url" in context
        assert context["tenant"] is None
        assert context["impacts"] == []


@pytest.mark.django_db
class TestTemplateRendererWithEvent:
    """Tests for TemplateRenderer with event context."""

    def test_build_context_with_maintenance(self, maintenance):
        """Test building context with maintenance event."""
        from notices.choices import MessageEventTypeChoices
        from notices.models import NotificationTemplate

        template = NotificationTemplate(
            name="Test",
            slug="test",
            event_type=MessageEventTypeChoices.MAINTENANCE,
            subject_template="S",
            body_template="B",
        )

        context = TemplateRenderer.build_context(template, event=maintenance)

        assert "maintenance" in context
        assert context["maintenance"] == maintenance


def _chain(*specs):
    """Build unsaved templates linked by extends: specs are (slug, body), most specific first."""
    from notices.models import NotificationTemplate

    templates = [NotificationTemplate(name=s, slug=s, body_template=b) for s, b in specs]
    for child, parent in zip(templates, templates[1:], strict=False):
        child.extends = parent
    return templates


class TestChainRendering:
    def test_child_block_overrides_parent_with_context(self):
        chain = _chain(
            ("child", '{% extends "base" %}{% block content %}hi {{ name }}{% endblock %}'),
            ("parent", "[{% block content %}default{% endblock %}]"),
        )
        renderer = TemplateRenderer.for_chain(chain)
        assert renderer.render_body(chain, {"name": "acme"}) == "[hi acme]"

    def test_three_level_base_resolves_to_each_parent(self):
        chain = _chain(
            ("leaf", '{% extends "base" %}{% block a %}LEAF{% endblock %}'),
            ("mid", '{% extends "base" %}{% block b %}MID{% endblock %}'),
            ("top", "{% block a %}a{% endblock %}-{% block b %}b{% endblock %}"),
        )
        assert TemplateRenderer.for_chain(chain).render_body(chain, {}) == "LEAF-MID"

    def test_empty_child_body_falls_back_to_parent(self):
        chain = _chain(("child", ""), ("parent", "P {{ x }}"))
        assert TemplateRenderer.for_chain(chain).render_body(chain, {"x": 1}) == "P 1"


class TestSandbox:
    ESCAPE = "{{ cycler.__init__.__globals__.os.getpid() }}"

    def test_plain_render_blocks_attribute_escape(self):
        with pytest.raises(TemplateRenderError):
            TemplateRenderer().render(self.ESCAPE, {})

    def test_chain_render_blocks_attribute_escape(self):
        chain = _chain(
            ("child", '{% extends "base" %}{% block a %}' + self.ESCAPE + "{% endblock %}"),
            ("parent", "{% block a %}{% endblock %}"),
        )
        with pytest.raises(TemplateRenderError):
            TemplateRenderer.for_chain(chain).render_body(chain, {})


class TestSplitBody:
    def test_markdown_keeps_source_as_text_and_renders_html(self):
        text, html = split_body("markdown", "**hi**")
        assert text == "**hi**"
        assert "<strong>hi</strong>" in html

    def test_html_strips_tags_for_text(self):
        text, html = split_body("html", "<p>hi <b>there</b></p>")
        assert html == "<p>hi <b>there</b></p>"
        assert text == "hi there"

    def test_text_has_no_html(self):
        assert split_body("text", "plain") == ("plain", "")
