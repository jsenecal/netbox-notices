import pytest
from django.utils import timezone
from datetime import timedelta

from circuits.models import Provider
from vendor_notification.models import Maintenance
from vendor_notification.forms import MaintenanceForm


@pytest.mark.django_db
class TestMaintenanceFormReplaces:
    """Test that MaintenanceForm includes replaces field."""

    def test_replaces_field_in_form(self):
        """Test that form includes replaces field."""
        form = MaintenanceForm()
        assert 'replaces' in form.fields

    def test_replaces_field_is_optional(self):
        """Test that replaces field is not required."""
        form = MaintenanceForm()
        assert form.fields['replaces'].required is False

    def test_form_saves_with_replaces(self):
        """Test that form correctly saves replaces relationship."""
        provider = Provider.objects.create(name="Test Provider", slug="test-provider")

        original = Maintenance.objects.create(
            name="MAINT-001",
            summary="Original maintenance",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=2),
            status="CONFIRMED"
        )

        form_data = {
            'name': 'MAINT-002',
            'summary': 'Rescheduled maintenance',
            'provider': provider.pk,
            'start': timezone.now() + timedelta(days=1),
            'end': timezone.now() + timedelta(days=1, hours=2),
            'status': 'CONFIRMED',
            'replaces': original.pk,
        }

        form = MaintenanceForm(data=form_data)
        assert form.is_valid(), form.errors

        maintenance = form.save()
        assert maintenance.replaces == original

    def test_form_saves_without_replaces(self):
        """Test that form works when replaces is not provided."""
        provider = Provider.objects.create(name="Test Provider", slug="test-provider")

        form_data = {
            'name': 'MAINT-001',
            'summary': 'New maintenance',
            'provider': provider.pk,
            'start': timezone.now(),
            'end': timezone.now() + timedelta(hours=2),
            'status': 'CONFIRMED',
        }

        form = MaintenanceForm(data=form_data)
        assert form.is_valid(), form.errors

        maintenance = form.save()
        assert maintenance.replaces is None
