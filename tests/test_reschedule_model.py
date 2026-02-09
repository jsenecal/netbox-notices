from datetime import timedelta

import pytest
from circuits.models import Provider
from django.utils import timezone

from notices.models import Maintenance


@pytest.mark.django_db
class TestMaintenanceReplaces:
    """Test the self-referencing replaces field on Maintenance model."""

    def test_replaces_field_exists(self):
        """Test that Maintenance model has replaces field."""
        assert hasattr(Maintenance, "replaces")

    def test_replaces_field_is_nullable(self):
        """Test that replaces field can be null."""
        provider = Provider.objects.create(name="Test Provider", slug="test-provider")
        maintenance = Maintenance.objects.create(
            name="MAINT-001",
            summary="Test maintenance",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=2),
            status="CONFIRMED",
            replaces=None,  # Should not raise error
        )
        assert maintenance.replaces is None

    def test_replaces_references_maintenance(self):
        """Test that replaces field can reference another maintenance."""
        provider = Provider.objects.create(name="Test Provider", slug="test-provider")

        original = Maintenance.objects.create(
            name="MAINT-001",
            summary="Original maintenance",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=2),
            status="CONFIRMED",
        )

        rescheduled = Maintenance.objects.create(
            name="MAINT-002",
            summary="Rescheduled maintenance",
            provider=provider,
            start=timezone.now() + timedelta(days=1),
            end=timezone.now() + timedelta(days=1, hours=2),
            status="CONFIRMED",
            replaces=original,
        )

        assert rescheduled.replaces == original

    def test_reverse_relation_replaced_by_maintenance(self):
        """Test that replaced maintenance has reverse relation."""
        provider = Provider.objects.create(name="Test Provider", slug="test-provider")

        original = Maintenance.objects.create(
            name="MAINT-001",
            summary="Original maintenance",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=2),
            status="CONFIRMED",
        )

        rescheduled = Maintenance.objects.create(
            name="MAINT-002",
            summary="Rescheduled maintenance",
            provider=provider,
            start=timezone.now() + timedelta(days=1),
            end=timezone.now() + timedelta(days=1, hours=2),
            status="CONFIRMED",
            replaces=original,
        )

        # Access reverse relation
        replacements = original.replaced_by_maintenance.all()
        assert rescheduled in replacements

    def test_replaces_on_delete_set_null(self):
        """Test that deleting original maintenance sets replaces to null."""
        provider = Provider.objects.create(name="Test Provider", slug="test-provider")

        original = Maintenance.objects.create(
            name="MAINT-001",
            summary="Original maintenance",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=2),
            status="CONFIRMED",
        )

        rescheduled = Maintenance.objects.create(
            name="MAINT-002",
            summary="Rescheduled maintenance",
            provider=provider,
            start=timezone.now() + timedelta(days=1),
            end=timezone.now() + timedelta(days=1, hours=2),
            status="CONFIRMED",
            replaces=original,
        )

        original.delete()

        # Refresh from database
        rescheduled.refresh_from_db()
        assert rescheduled.replaces is None
