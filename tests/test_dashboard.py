"""Tests for the Summary Dashboard view."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from notices.models import Maintenance, Outage

User = get_user_model()


@pytest.fixture
def admin_client(db):
    user = User.objects.create_superuser("dashboard_admin", "admin@test.com", "admin")
    client = Client()
    client.force_login(user)
    return client


@pytest.mark.django_db
class TestDashboardView:
    def test_dashboard_url_resolves(self):
        from django.urls import reverse

        url = reverse("plugins:notices:dashboard")
        assert url == "/plugins/notices/"

    def test_dashboard_returns_200(self, admin_client):
        response = admin_client.get("/plugins/notices/")
        assert response.status_code == 200

    def test_dashboard_context_has_stats(self, admin_client):
        response = admin_client.get("/plugins/notices/")
        assert "maintenance_in_progress" in response.context
        assert "outage_active" in response.context
        assert "upcoming_7" in response.context
        assert "upcoming_30" in response.context
        assert "unacknowledged" in response.context

    def test_dashboard_counts_in_progress(self, admin_client, provider):
        now = timezone.now()
        Maintenance.objects.create(
            name="M1",
            summary="Test",
            provider=provider,
            status="IN-PROCESS",
            start=now - timedelta(hours=1),
            end=now + timedelta(hours=1),
        )
        response = admin_client.get("/plugins/notices/")
        assert response.context["maintenance_in_progress"] == 1

    def test_dashboard_counts_active_outages(self, admin_client, provider):
        now = timezone.now()
        Outage.objects.create(
            name="O1",
            summary="Test",
            provider=provider,
            status="INVESTIGATING",
            start=now,
        )
        response = admin_client.get("/plugins/notices/")
        assert response.context["outage_active"] == 1

    def test_dashboard_counts_unacknowledged(self, admin_client, provider):
        now = timezone.now()
        Maintenance.objects.create(
            name="M2",
            summary="Test",
            provider=provider,
            status="CONFIRMED",
            start=now + timedelta(days=1),
            end=now + timedelta(days=2),
            acknowledged=False,
        )
        response = admin_client.get("/plugins/notices/")
        assert response.context["unacknowledged"] >= 1

    def test_dashboard_requires_login(self):
        client = Client()
        response = client.get("/plugins/notices/")
        assert response.status_code == 302  # Redirect to login
