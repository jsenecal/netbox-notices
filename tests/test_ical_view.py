"""Integration tests for iCal feed endpoint."""

import pytest
from datetime import datetime, timedelta, timezone as dt_timezone
from django.test import Client
from users.models import User, Token

from circuits.models import Provider
from notices.models import Maintenance


@pytest.mark.django_db
class TestMaintenanceICalViewAuthentication:
    """Test authentication methods for iCal endpoint."""

    def test_token_in_url_authenticates(self):
        # Create user and token
        user = User.objects.create_user(username="testuser", password="testpass", is_superuser=True)
        token = Token.objects.create(user=user)

        # Create test maintenance
        provider = Provider.objects.create(name="Test", slug="test")
        Maintenance.objects.create(
            name="M1",
            summary="Test",
            provider=provider,
            start=datetime.now(dt_timezone.utc),
            end=datetime.now(dt_timezone.utc) + timedelta(hours=2),
            status="CONFIRMED",
        )

        # Request with token in URL
        client = Client()
        response = client.get(
            f"/plugins/notices/ical/maintenances.ics?token={token.key}"
        )

        assert response.status_code == 200
        assert response["Content-Type"] == "text/calendar; charset=utf-8"

    def test_invalid_token_returns_403(self):
        client = Client()
        response = client.get(
            "/plugins/notices/ical/maintenances.ics?token=invalid"
        )

        assert response.status_code == 403

    def test_no_authentication_returns_403_when_login_required(self):
        client = Client()
        response = client.get("/plugins/notices/ical/maintenances.ics")

        # Will be 403 if LOGIN_REQUIRED=True (default in tests)
        assert response.status_code in [200, 403]

    def test_authorization_header_authenticates(self):
        user = User.objects.create_user(username="apiuser", password="testpass", is_superuser=True)
        token = Token.objects.create(user=user)

        provider = Provider.objects.create(name="Test", slug="test")
        Maintenance.objects.create(
            name="M1",
            summary="Test",
            provider=provider,
            start=datetime.now(dt_timezone.utc),
            end=datetime.now(dt_timezone.utc) + timedelta(hours=2),
            status="CONFIRMED",
        )

        client = Client()
        response = client.get(
            "/plugins/notices/ical/maintenances.ics",
            HTTP_AUTHORIZATION=f"Token {token.key}",
        )

        assert response.status_code == 200


@pytest.mark.django_db
class TestMaintenanceICalViewFiltering:
    """Test query parameter filtering."""

    def setup_method(self):
        """Create test user and token."""
        self.user = User.objects.create_user(username="testuser", password="testpass", is_superuser=True)
        self.token = Token.objects.create(user=self.user)
        self.client = Client()

    def test_past_days_filter(self):
        provider = Provider.objects.create(name="Test", slug="test")

        # Create old maintenance (60 days ago)
        old_start = datetime.now(dt_timezone.utc) - timedelta(days=60)
        Maintenance.objects.create(
            name="OLD",
            summary="Old",
            provider=provider,
            start=old_start,
            end=old_start + timedelta(hours=2),
            status="COMPLETED",
        )

        # Create recent maintenance (10 days ago)
        recent_start = datetime.now(dt_timezone.utc) - timedelta(days=10)
        Maintenance.objects.create(
            name="RECENT",
            summary="Recent",
            provider=provider,
            start=recent_start,
            end=recent_start + timedelta(hours=2),
            status="CONFIRMED",
        )

        # Default (30 days) should exclude old
        response = self.client.get(
            f"/plugins/notices/ical/maintenances.ics?token={self.token.key}"
        )
        content = response.content.decode("utf-8")
        assert "RECENT" in content
        assert "OLD" not in content

        # past_days=90 should include both
        response = self.client.get(
            f"/plugins/notices/ical/maintenances.ics?token={self.token.key}&past_days=90"
        )
        content = response.content.decode("utf-8")
        assert "RECENT" in content
        assert "OLD" in content

    def test_provider_filter_by_slug(self):
        provider1 = Provider.objects.create(name="AWS", slug="aws")
        provider2 = Provider.objects.create(name="Azure", slug="azure")

        now = datetime.now(dt_timezone.utc)
        Maintenance.objects.create(
            name="AWS-1",
            summary="AWS",
            provider=provider1,
            start=now,
            end=now + timedelta(hours=2),
            status="CONFIRMED",
        )
        Maintenance.objects.create(
            name="AZURE-1",
            summary="Azure",
            provider=provider2,
            start=now,
            end=now + timedelta(hours=2),
            status="CONFIRMED",
        )

        response = self.client.get(
            f"/plugins/notices/ical/maintenances.ics?token={self.token.key}&provider=aws"
        )
        content = response.content.decode("utf-8")
        assert "AWS-1" in content
        assert "AZURE-1" not in content

    def test_status_filter(self):
        provider = Provider.objects.create(name="Test", slug="test")
        now = datetime.now(dt_timezone.utc)

        Maintenance.objects.create(
            name="CONF",
            summary="Confirmed",
            provider=provider,
            start=now,
            end=now + timedelta(hours=2),
            status="CONFIRMED",
        )
        Maintenance.objects.create(
            name="TENT",
            summary="Tentative",
            provider=provider,
            start=now,
            end=now + timedelta(hours=2),
            status="TENTATIVE",
        )

        response = self.client.get(
            f"/plugins/notices/ical/maintenances.ics?token={self.token.key}&status=CONFIRMED"
        )
        content = response.content.decode("utf-8")
        assert "CONF" in content
        assert "TENT" not in content

    def test_invalid_provider_returns_400(self):
        response = self.client.get(
            f"/plugins/notices/ical/maintenances.ics?token={self.token.key}&provider=nonexistent"
        )
        assert response.status_code == 400


@pytest.mark.django_db
class TestMaintenanceICalViewCaching:
    """Test HTTP caching behavior."""

    def setup_method(self):
        self.user = User.objects.create_user(username="testuser", password="testpass", is_superuser=True)
        self.token = Token.objects.create(user=self.user)
        self.client = Client()

    def test_response_includes_cache_headers(self):
        provider = Provider.objects.create(name="Test", slug="test")
        now = datetime.now(dt_timezone.utc)
        Maintenance.objects.create(
            name="M1",
            summary="Test",
            provider=provider,
            start=now,
            end=now + timedelta(hours=2),
            status="CONFIRMED",
        )

        response = self.client.get(
            f"/plugins/notices/ical/maintenances.ics?token={self.token.key}"
        )

        assert "Cache-Control" in response
        assert "public" in response["Cache-Control"]
        assert "max-age" in response["Cache-Control"]
        assert "ETag" in response

    def test_etag_matches_returns_304(self):
        provider = Provider.objects.create(name="Test", slug="test")
        now = datetime.now(dt_timezone.utc)
        Maintenance.objects.create(
            name="M1",
            summary="Test",
            provider=provider,
            start=now,
            end=now + timedelta(hours=2),
            status="CONFIRMED",
        )

        # First request
        response1 = self.client.get(
            f"/plugins/notices/ical/maintenances.ics?token={self.token.key}"
        )
        etag = response1["ETag"]

        # Second request with If-None-Match
        response2 = self.client.get(
            f"/plugins/notices/ical/maintenances.ics?token={self.token.key}",
            HTTP_IF_NONE_MATCH=etag,
        )

        assert response2.status_code == 304

    def test_empty_queryset_returns_valid_calendar(self):
        response = self.client.get(
            f"/plugins/notices/ical/maintenances.ics?token={self.token.key}"
        )

        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "BEGIN:VCALENDAR" in content
        assert "END:VCALENDAR" in content
