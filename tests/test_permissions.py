"""
Tests for permission enforcement across all views.

These tests verify that Django permissions are properly enforced
for all models and views in the notices plugin.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from circuits.models import Provider
from notices.models import Maintenance, Outage, Impact, EventNotification
from django.contrib.contenttypes.models import ContentType

User = get_user_model()


@pytest.mark.django_db
class TestMaintenancePermissions:
    """Test permission enforcement for Maintenance views."""

    @pytest.fixture
    def provider(self):
        """Create a test provider."""
        return Provider.objects.create(name="Test Provider", slug="test-provider")

    @pytest.fixture
    def maintenance(self, provider):
        """Create a test maintenance."""
        return Maintenance.objects.create(
            name="MAINT-001",
            summary="Test",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=2),
            status="CONFIRMED",
        )

    @pytest.fixture
    def user_no_perms(self):
        """Create user without any permissions."""
        return User.objects.create_user(
            username="noauth",
            password="test",
            email="noauth@example.com"
        )

    def test_list_view_requires_permission(self, user_no_perms):
        """Test that maintenance list requires view_maintenance permission."""
        client = Client()
        client.force_login(user_no_perms)

        url = reverse("plugins:notices:maintenance_list")
        response = client.get(url)

        # Should be forbidden or redirect
        assert response.status_code in [302, 403]

    def test_detail_view_requires_permission(self, user_no_perms, maintenance):
        """Test that maintenance detail requires view_maintenance permission."""
        client = Client()
        client.force_login(user_no_perms)

        url = reverse("plugins:notices:maintenance", args=[maintenance.pk])
        response = client.get(url)

        # Should be forbidden or redirect
        assert response.status_code in [302, 403]

    def test_edit_view_requires_permission(self, user_no_perms, maintenance):
        """Test that maintenance edit requires change_maintenance permission."""
        client = Client()
        client.force_login(user_no_perms)

        url = reverse("plugins:notices:maintenance_edit", args=[maintenance.pk])
        response = client.get(url)

        # Should be forbidden or redirect
        assert response.status_code in [302, 403]

    def test_delete_view_requires_permission(self, user_no_perms, maintenance):
        """Test that maintenance delete requires delete_maintenance permission."""
        client = Client()
        client.force_login(user_no_perms)

        url = reverse("plugins:notices:maintenance_delete", args=[maintenance.pk])
        response = client.get(url)

        # Should be forbidden or redirect
        assert response.status_code in [302, 403]

    def test_add_view_requires_permission(self, user_no_perms):
        """Test that maintenance add requires add_maintenance permission."""
        client = Client()
        client.force_login(user_no_perms)

        url = reverse("plugins:notices:maintenance_add")
        response = client.get(url)

        # Should be forbidden or redirect
        assert response.status_code in [302, 403]

    def test_calendar_view_requires_permission(self, user_no_perms):
        """Test that calendar view requires view_maintenance permission."""
        client = Client()
        client.force_login(user_no_perms)

        url = reverse("plugins:notices:maintenance_calendar")
        response = client.get(url)

        # Should be forbidden
        assert response.status_code == 403


@pytest.mark.django_db
class TestOutagePermissions:
    """Test permission enforcement for Outage views."""

    @pytest.fixture
    def provider(self):
        """Create a test provider."""
        return Provider.objects.create(name="Test Provider", slug="test-provider")

    @pytest.fixture
    def outage(self, provider):
        """Create a test outage."""
        return Outage.objects.create(
            name="OUT-001",
            summary="Test",
            provider=provider,
            start=timezone.now(),
            status="IN-PROGRESS",
        )

    @pytest.fixture
    def user_no_perms(self):
        """Create user without any permissions."""
        return User.objects.create_user(
            username="noauth",
            password="test",
            email="noauth@example.com"
        )

    def test_list_view_requires_permission(self, user_no_perms):
        """Test that outage list requires view_outage permission."""
        client = Client()
        client.force_login(user_no_perms)

        url = reverse("plugins:notices:outage_list")
        response = client.get(url)

        # Should be forbidden or redirect
        assert response.status_code in [302, 403]

    def test_detail_view_requires_permission(self, user_no_perms, outage):
        """Test that outage detail requires view_outage permission."""
        client = Client()
        client.force_login(user_no_perms)

        url = reverse("plugins:notices:outage", args=[outage.pk])
        response = client.get(url)

        # Should be forbidden or redirect
        assert response.status_code in [302, 403]

    def test_edit_view_requires_permission(self, user_no_perms, outage):
        """Test that outage edit requires change_outage permission."""
        client = Client()
        client.force_login(user_no_perms)

        url = reverse("plugins:notices:outage_edit", args=[outage.pk])
        response = client.get(url)

        # Should be forbidden or redirect
        assert response.status_code in [302, 403]

    def test_delete_view_requires_permission(self, user_no_perms, outage):
        """Test that outage delete requires delete_outage permission."""
        client = Client()
        client.force_login(user_no_perms)

        url = reverse("plugins:notices:outage_delete", args=[outage.pk])
        response = client.get(url)

        # Should be forbidden or redirect
        assert response.status_code in [302, 403]


@pytest.mark.django_db
class TestAPIPermissions:
    """Test permission enforcement for API endpoints."""

    @pytest.fixture
    def provider(self):
        """Create a test provider."""
        return Provider.objects.create(name="Test Provider", slug="test-provider")

    @pytest.fixture
    def maintenance(self, provider):
        """Create a test maintenance."""
        return Maintenance.objects.create(
            name="MAINT-001",
            summary="Test",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=2),
            status="CONFIRMED",
        )

    @pytest.fixture
    def user_no_perms(self):
        """Create user without any permissions."""
        return User.objects.create_user(
            username="apiuser",
            password="test",
            email="api@example.com"
        )

    def test_api_list_requires_permission(self, user_no_perms):
        """Test that API list endpoint requires view permission."""
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=user_no_perms)

        url = "/api/plugins/notices/maintenance/"
        response = client.get(url)

        # Should be forbidden
        assert response.status_code == 403

    def test_api_detail_requires_permission(self, user_no_perms, maintenance):
        """Test that API detail endpoint requires view permission."""
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=user_no_perms)

        url = f"/api/plugins/notices/maintenance/{maintenance.pk}/"
        response = client.get(url)

        # Should be forbidden
        assert response.status_code == 403

    def test_api_create_requires_permission(self, user_no_perms, provider):
        """Test that API create endpoint requires add permission."""
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=user_no_perms)

        url = "/api/plugins/notices/maintenance/"
        data = {
            "name": "MAINT-002",
            "summary": "Test",
            "provider": provider.pk,
            "start": timezone.now().isoformat(),
            "end": (timezone.now() + timedelta(hours=2)).isoformat(),
            "status": "TENTATIVE",
        }
        response = client.post(url, data, format="json")

        # Should be forbidden
        assert response.status_code == 403

    def test_api_update_requires_permission(self, user_no_perms, maintenance):
        """Test that API update endpoint requires change permission."""
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=user_no_perms)

        url = f"/api/plugins/notices/maintenance/{maintenance.pk}/"
        data = {
            "name": "MAINT-001-UPDATED",
            "summary": "Updated",
            "provider": maintenance.provider.pk,
            "start": maintenance.start.isoformat(),
            "end": maintenance.end.isoformat(),
            "status": "CONFIRMED",
        }
        response = client.patch(url, data, format="json")

        # Should be forbidden
        assert response.status_code == 403

    def test_api_delete_requires_permission(self, user_no_perms, maintenance):
        """Test that API delete endpoint requires delete permission."""
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=user_no_perms)

        url = f"/api/plugins/notices/maintenance/{maintenance.pk}/"
        response = client.delete(url)

        # Should be forbidden
        assert response.status_code == 403


@pytest.mark.django_db
class TestICalPermissions:
    """Test permission enforcement for iCal feed."""

    @pytest.fixture
    def user_no_perms(self):
        """Create user without any permissions."""
        return User.objects.create_user(
            username="icaluser",
            password="test",
            email="ical@example.com"
        )

    def test_ical_requires_permission(self, user_no_perms):
        """Test that iCal feed requires view_maintenance permission."""
        client = Client()
        client.force_login(user_no_perms)

        url = "/plugins/notices/ical/maintenances.ics"
        response = client.get(url)

        # Should be forbidden
        assert response.status_code == 403
        assert b"Permission denied" in response.content
