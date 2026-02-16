"""Tests for the sanitize_html template filter."""

import pytest
from django.template import Context, Template


@pytest.mark.django_db
class TestSanitizeHtmlFilter:
    def test_strips_script_tags(self):
        t = Template("{% load notices_filters %}{{ html|sanitize_html }}")
        result = t.render(Context({"html": '<p>Hello</p><script>alert("xss")</script>'}))
        assert "<script>" not in result
        assert "<p>Hello</p>" in result

    def test_allows_safe_tags(self):
        t = Template("{% load notices_filters %}{{ html|sanitize_html }}")
        html = "<p>Text with <strong>bold</strong> and <a href='https://example.com'>link</a></p>"
        result = t.render(Context({"html": html}))
        assert "<strong>bold</strong>" in result
        assert "<a " in result

    def test_strips_event_handlers(self):
        t = Template("{% load notices_filters %}{{ html|sanitize_html }}")
        result = t.render(Context({"html": '<img src="x" onerror="alert(1)">'}))
        assert "onerror" not in result

    def test_empty_string(self):
        t = Template("{% load notices_filters %}{{ html|sanitize_html }}")
        result = t.render(Context({"html": ""}))
        assert result.strip() == ""

    def test_plain_text_passes_through(self):
        t = Template("{% load notices_filters %}{{ html|sanitize_html }}")
        result = t.render(Context({"html": "Just plain text"}))
        assert "Just plain text" in result
