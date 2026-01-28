# tests/test_template_renderer.py
from datetime import datetime
from datetime import timezone as dt_timezone

import pytest

from notices.services.template_renderer import (
    TemplateRenderer,
    TemplateRenderError,
    ical_datetime,
    render_markdown,
)


class TestIcalDatetime:
    """Tests for ical_datetime filter."""

    def test_formats_utc_datetime(self):
        """Test formatting a UTC datetime."""
        dt = datetime(2026, 1, 22, 14, 30, 0, tzinfo=dt_timezone.utc)
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
        dt = datetime(2026, 1, 22, 14, 30, 0, tzinfo=dt_timezone.utc)
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

    def test_validate_valid_template(self):
        """Test validating a valid template."""
        renderer = TemplateRenderer()
        assert renderer.validate("Hello {{ name }}!") is True

    def test_validate_invalid_template(self):
        """Test validating an invalid template."""
        renderer = TemplateRenderer()
        with pytest.raises(TemplateRenderError, match="Invalid template syntax"):
            renderer.validate("{% if unclosed")

    def test_render_with_blocks(self):
        """Test rendering with Jinja blocks."""
        templates = {
            "base": "{% block content %}default{% endblock %}",
        }
        renderer = TemplateRenderer(templates)

        child = '{% extends "base" %}{% block content %}custom{% endblock %}'
        result = renderer.render_with_inheritance(child)
        assert result == "custom"

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
