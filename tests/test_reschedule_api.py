import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient

from circuits.models import Provider
from notices.models import Maintenance

User = get_user_model()


@pytest.mark.django_db
class TestMaintenanceRescheduleAPI:
    """Test API support for replaces field."""

    @pytest.fixture
    def user(self):
        """Create superuser for API testing."""
        return User.objects.create_superuser(
            username="apiuser", email="api@example.com", password="apipass123"
        )

    @pytest.fixture
    def api_client(self, user):
        """Create authenticated API client."""
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    @pytest.fixture
    def provider(self):
        """Create test provider."""
        return Provider.objects.create(name="Test Provider", slug="test-provider")

    def test_api_includes_replaces_field(self, api_client, provider):
        """Test that API response includes replaces field."""
        maintenance = Maintenance.objects.create(
            name="MAINT-001",
            summary="Test",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=2),
            status="CONFIRMED",
        )

        url = f"/api/plugins/notices/maintenance/{maintenance.pk}/"
        response = api_client.get(url)

        assert response.status_code == 200
        assert "replaces" in response.data

    def test_api_create_with_replaces(self, api_client, provider):
        """Test creating maintenance with replaces via API."""
        original = Maintenance.objects.create(
            name="MAINT-001",
            summary="Original",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=2),
            status="CONFIRMED",
        )

        url = "/api/plugins/notices/maintenance/"
        data = {
            "name": "MAINT-002",
            "summary": "Rescheduled",
            "provider": provider.pk,
            "start": (timezone.now() + timedelta(days=1)).isoformat(),
            "end": (timezone.now() + timedelta(days=1, hours=2)).isoformat(),
            "status": "TENTATIVE",
            "replaces": original.pk,
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == 201
        assert response.data["replaces"] == original.pk

        # Verify in database
        new_maintenance = Maintenance.objects.get(name="MAINT-002")
        assert new_maintenance.replaces == original
