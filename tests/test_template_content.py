"""Tests for template_content module."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from notices.template_content import (
    ProviderEventsExtension,
    _create_event_history_extensions,
    render_event_history,
    render_provider_events,
)


@pytest.mark.django_db
class TestCreateEventHistoryExtensions:
    """Tests for _create_event_history_extensions function."""

    def test_creates_extensions_for_allowed_types(self):
        """Should create extension classes for each allowed content type."""
        extensions = _create_event_history_extensions()
        assert len(extensions) > 0

    def test_extension_classes_have_correct_structure(self):
        """Each extension should have models list and right_page method."""
        extensions = _create_event_history_extensions()
        for ext in extensions:
            assert hasattr(ext, "models")
            assert isinstance(ext.models, list)
            assert len(ext.models) == 1
            assert hasattr(ext, "right_page")

    def test_extension_class_names_are_unique(self):
        """Each extension class should have a unique name."""
        extensions = _create_event_history_extensions()
        names = [ext.__name__ for ext in extensions]
        assert len(names) == len(set(names))


@pytest.mark.django_db
class TestRenderEventHistory:
    """Tests for render_event_history function."""

    def test_returns_empty_string_when_no_impacts(self, circuit):
        """Should return empty string when object has no impacts."""
        result = render_event_history(circuit)
        assert result == ""

    def test_returns_html_when_impacts_exist(self, circuit, provider):
        """Should return HTML when object has maintenance impacts."""
        from notices.models import Impact, Maintenance

        maintenance = Maintenance.objects.create(
            name="Test Maintenance",
            provider=provider,
            start=timezone.now() + timedelta(days=1),
            end=timezone.now() + timedelta(days=2),
            status="CONFIRMED",
        )
        ct = ContentType.objects.get_for_model(circuit)
        Impact.objects.create(
            event_content_type=ContentType.objects.get_for_model(maintenance),
            event_object_id=maintenance.pk,
            target_content_type=ct,
            target_object_id=circuit.pk,
            impact="OUTAGE",
        )

        result = render_event_history(circuit)
        assert "Maintenance" in result
        assert "card" in result

    def test_includes_outage_impacts(self, circuit, provider):
        """Should include outage impacts in result."""
        from notices.models import Impact, Outage

        outage = Outage.objects.create(
            name="Test Outage",
            provider=provider,
            start=timezone.now(),
            status="REPORTED",
        )
        ct = ContentType.objects.get_for_model(circuit)
        Impact.objects.create(
            event_content_type=ContentType.objects.get_for_model(outage),
            event_object_id=outage.pk,
            target_content_type=ct,
            target_object_id=circuit.pk,
            impact="OUTAGE",
        )

        result = render_event_history(circuit)
        assert "Outage" in result

    def test_excludes_old_completed_events(self, circuit, provider):
        """Should exclude events that ended more than 30 days ago."""
        from notices.models import Impact, Maintenance

        old_maintenance = Maintenance.objects.create(
            name="Old Maintenance",
            provider=provider,
            start=timezone.now() - timedelta(days=60),
            end=timezone.now() - timedelta(days=59),
            status="COMPLETED",
        )
        ct = ContentType.objects.get_for_model(circuit)
        Impact.objects.create(
            event_content_type=ContentType.objects.get_for_model(old_maintenance),
            event_object_id=old_maintenance.pk,
            target_content_type=ct,
            target_object_id=circuit.pk,
            impact="OUTAGE",
        )

        result = render_event_history(circuit)
        assert result == ""

    def test_includes_ongoing_outages_without_end(self, circuit, provider):
        """Should include ongoing outages that have no end date."""
        from notices.models import Impact, Outage

        ongoing_outage = Outage.objects.create(
            name="Ongoing Outage",
            provider=provider,
            start=timezone.now() - timedelta(days=5),
            end=None,
            status="INVESTIGATING",
        )
        ct = ContentType.objects.get_for_model(circuit)
        Impact.objects.create(
            event_content_type=ContentType.objects.get_for_model(ongoing_outage),
            event_object_id=ongoing_outage.pk,
            target_content_type=ct,
            target_object_id=circuit.pk,
            impact="OUTAGE",
        )

        result = render_event_history(circuit)
        assert "Ongoing Outage" in result or "Outage" in result

    def test_includes_future_events(self, circuit, provider):
        """Should include events starting in the future."""
        from notices.models import Impact, Maintenance

        future_maintenance = Maintenance.objects.create(
            name="Future Maintenance",
            provider=provider,
            start=timezone.now() + timedelta(days=30),
            end=timezone.now() + timedelta(days=31),
            status="CONFIRMED",
        )
        ct = ContentType.objects.get_for_model(circuit)
        Impact.objects.create(
            event_content_type=ContentType.objects.get_for_model(future_maintenance),
            event_object_id=future_maintenance.pk,
            target_content_type=ct,
            target_object_id=circuit.pk,
            impact="NO-IMPACT",
        )

        result = render_event_history(circuit)
        assert result != ""


@pytest.mark.django_db
class TestRenderProviderEvents:
    """Tests for render_provider_events function."""

    def test_returns_empty_string_when_no_events(self, provider):
        """Should return empty string when provider has no events."""
        result = render_provider_events(provider)
        assert result == ""

    def test_returns_html_when_maintenances_exist(self, provider):
        """Should return HTML when provider has maintenances."""
        from notices.models import Maintenance

        Maintenance.objects.create(
            name="Provider Maintenance",
            provider=provider,
            start=timezone.now() + timedelta(days=1),
            end=timezone.now() + timedelta(days=2),
            status="CONFIRMED",
        )

        result = render_provider_events(provider)
        assert "Maintenance" in result
        assert "card" in result

    def test_returns_html_when_outages_exist(self, provider):
        """Should return HTML when provider has outages."""
        from notices.models import Outage

        Outage.objects.create(
            name="Provider Outage",
            provider=provider,
            start=timezone.now(),
            status="REPORTED",
        )

        result = render_provider_events(provider)
        assert "Outage" in result

    def test_excludes_old_events(self, provider):
        """Should exclude events older than configured days."""
        from notices.models import Maintenance

        Maintenance.objects.create(
            name="Old Maintenance",
            provider=provider,
            start=timezone.now() - timedelta(days=60),
            end=timezone.now() - timedelta(days=59),
            status="COMPLETED",
        )

        result = render_provider_events(provider)
        assert result == ""

    def test_includes_ongoing_outages(self, provider):
        """Should include ongoing outages without end date."""
        from notices.models import Outage

        Outage.objects.create(
            name="Ongoing",
            provider=provider,
            start=timezone.now() - timedelta(days=5),
            end=None,
            status="INVESTIGATING",
        )

        result = render_provider_events(provider)
        assert result != ""


@pytest.mark.django_db
class TestProviderEventsExtension:
    """Tests for ProviderEventsExtension class."""

    def test_models_attribute(self):
        """Should target circuits.provider model."""
        assert ProviderEventsExtension.models == ["circuits.provider"]

    def test_right_page_method_calls_render(self, provider):
        """Should call render_provider_events with context object."""
        context = {"object": provider}
        ext = ProviderEventsExtension(context)

        with patch("notices.template_content.render_provider_events") as mock_render:
            mock_render.return_value = "<div>test</div>"
            result = ext.right_page()
            mock_render.assert_called_once_with(provider)
            assert result == "<div>test</div>"
