"""
Tests for iCal download functionality.
"""

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from vendor_notification.models import Maintenance
from circuits.models import Provider


@pytest.mark.django_db
class TestICalDownload:
    """Test iCal download parameter handling."""

    @pytest.fixture
    def provider(self):
        """Create a test provider."""
        return Provider.objects.create(name="Test Provider", slug="test-provider")

    @pytest.fixture
    def maintenance(self, provider):
        """Create a test maintenance event."""
        now = timezone.now()
        return Maintenance.objects.create(
            name="TEST-001",
            summary="Test maintenance",
            provider=provider,
            start=now + timedelta(days=1),
            end=now + timedelta(days=1, hours=4),
            status="CONFIRMED",
        )

    @pytest.fixture
    def authenticated_client(self, admin_user):
        """Get authenticated client."""
        client = Client()
        client.force_login(admin_user)
        return client

    def test_ical_without_download_parameter(self, authenticated_client, maintenance):
        """Test iCal view without download parameter has caching headers."""
        url = reverse("plugins:vendor_notification:ical_maintenances")
        response = authenticated_client.get(url)

        assert response.status_code == 200
        assert response["Content-Type"] == "text/calendar; charset=utf-8"
        assert "Cache-Control" in response
        assert "Content-Disposition" not in response or "inline" in response.get(
            "Content-Disposition", ""
        )

    def test_ical_with_download_parameter(self, authenticated_client, maintenance):
        """Test iCal view with download=true has attachment header."""
        url = reverse("plugins:vendor_notification:ical_maintenances")
        response = authenticated_client.get(url, {"download": "true"})

        assert response.status_code == 200
        assert response["Content-Type"] == "text/calendar; charset=utf-8"
        assert "Content-Disposition" in response
        assert "attachment" in response["Content-Disposition"]
        assert "netbox-maintenance-" in response["Content-Disposition"]
        assert ".ics" in response["Content-Disposition"]

    def test_ical_download_filename_format(self, authenticated_client, maintenance):
        """Test download filename includes current date."""
        url = reverse("plugins:vendor_notification:ical_maintenances")
        response = authenticated_client.get(url, {"download": "true"})

        # Filename should be: netbox-maintenance-YYYY-MM-DD.ics
        from datetime import date

        expected_date = date.today().strftime("%Y-%m-%d")

        assert (
            f"netbox-maintenance-{expected_date}.ics" in response["Content-Disposition"]
        )
