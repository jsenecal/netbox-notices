import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from circuits.models import Provider
from notices.models import Maintenance

User = get_user_model()


@pytest.mark.django_db
class TestMaintenanceRescheduleView:
    """Test the MaintenanceRescheduleView."""

    @pytest.fixture
    def user(self):
        """Create a superuser for testing."""
        return User.objects.create_superuser(
            username="testuser", email="test@example.com", password="testpass123"
        )

    @pytest.fixture
    def client(self, user):
        """Create authenticated client."""
        client = Client()
        client.force_login(user)
        return client

    @pytest.fixture
    def provider(self):
        """Create a test provider."""
        return Provider.objects.create(name="Test Provider", slug="test-provider")

    @pytest.fixture
    def original_maintenance(self, provider):
        """Create original maintenance to be rescheduled."""
        return Maintenance.objects.create(
            name="MAINT-001",
            summary="Original maintenance",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=2),
            status="CONFIRMED",
            internal_ticket="TICKET-123",
            comments="Original comments",
        )

    def test_reschedule_url_exists(self, client, original_maintenance):
        """Test that reschedule URL is accessible."""
        url = reverse(
            "plugins:notices:maintenance_reschedule", args=[original_maintenance.pk]
        )
        response = client.get(url)
        assert response.status_code == 200

    def test_reschedule_form_prefilled(self, client, original_maintenance):
        """Test that reschedule form is pre-filled with original data."""
        url = reverse(
            "plugins:notices:maintenance_reschedule", args=[original_maintenance.pk]
        )
        response = client.get(url)

        # Check that form has initial values from original
        form = response.context["form"]
        assert form.initial["name"] == original_maintenance.name
        assert form.initial["summary"] == original_maintenance.summary
        assert form.initial["provider"] == original_maintenance.provider.pk
        assert form.initial["internal_ticket"] == original_maintenance.internal_ticket
        assert form.initial["comments"] == original_maintenance.comments

    def test_reschedule_sets_replaces_field(self, client, original_maintenance):
        """Test that reschedule form sets replaces to original."""
        url = reverse(
            "plugins:notices:maintenance_reschedule", args=[original_maintenance.pk]
        )
        response = client.get(url)

        form = response.context["form"]
        assert form.initial["replaces"] == original_maintenance.pk

    def test_reschedule_resets_status_to_tentative(self, client, original_maintenance):
        """Test that new maintenance starts with TENTATIVE status."""
        url = reverse(
            "plugins:notices:maintenance_reschedule", args=[original_maintenance.pk]
        )
        response = client.get(url)

        form = response.context["form"]
        assert form.initial["status"] == "TENTATIVE"

    def test_reschedule_post_creates_new_maintenance(
        self, client, original_maintenance, provider
    ):
        """Test that posting reschedule form creates new maintenance."""
        url = reverse(
            "plugins:notices:maintenance_reschedule", args=[original_maintenance.pk]
        )

        new_start = timezone.now() + timedelta(days=1)
        new_end = new_start + timedelta(hours=2)

        data = {
            "name": "MAINT-002",
            "summary": "Rescheduled maintenance",
            "provider": provider.pk,
            "start": new_start.strftime("%Y-%m-%d %H:%M:%S"),
            "end": new_end.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "TENTATIVE",
            "replaces": original_maintenance.pk,
        }

        response = client.post(url, data)

        # Should redirect to new maintenance
        assert response.status_code == 302

        # Check new maintenance was created
        new_maintenance = Maintenance.objects.get(name="MAINT-002")
        assert new_maintenance.replaces == original_maintenance

    def test_reschedule_updates_original_status(
        self, client, original_maintenance, provider
    ):
        """Test that rescheduling updates original status to RE-SCHEDULED."""
        url = reverse(
            "plugins:notices:maintenance_reschedule", args=[original_maintenance.pk]
        )

        new_start = timezone.now() + timedelta(days=1)
        new_end = new_start + timedelta(hours=2)

        data = {
            "name": "MAINT-002",
            "summary": "Rescheduled maintenance",
            "provider": provider.pk,
            "start": new_start.strftime("%Y-%m-%d %H:%M:%S"),
            "end": new_end.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "TENTATIVE",
            "replaces": original_maintenance.pk,
        }

        response = client.post(url, data)

        # Should redirect to new maintenance
        assert response.status_code == 302

        # Verify new maintenance was created
        new_maintenance = Maintenance.objects.get(name="MAINT-002")
        assert new_maintenance.replaces == original_maintenance

        # Verify original maintenance status was updated to RE-SCHEDULED
        original_maintenance.refresh_from_db()
        assert original_maintenance.status == "RE-SCHEDULED"

    def test_reschedule_requires_permission(self):
        """Test that reschedule requires add_maintenance permission."""
        # Create user without permissions
        user = User.objects.create_user(username="noauth", password="test")
        client = Client()
        client.force_login(user)

        provider = Provider.objects.create(name="Test Provider", slug="test-provider")
        maintenance = Maintenance.objects.create(
            name="MAINT-001",
            summary="Test",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=2),
            status="CONFIRMED",
        )

        url = reverse("plugins:notices:maintenance_reschedule", args=[maintenance.pk])
        response = client.get(url)

        # Should be forbidden or redirect to login
        assert response.status_code in [302, 403]
