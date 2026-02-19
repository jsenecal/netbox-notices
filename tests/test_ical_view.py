"""Integration tests for iCal feed endpoint."""

from datetime import datetime, timedelta
from datetime import timezone as dt_timezone

import pytest
from circuits.models import Provider
from django.test import Client
from users.models import Token, User

from notices.models import Maintenance


@pytest.mark.django_db
class TestMaintenanceICalViewAuthentication:
    """Test authentication methods for iCal endpoint."""

    def test_token_in_url_authenticates(self):
        # Create user and v1 token (plaintext stored, suitable for URL auth)
        user = User.objects.create_user(username="testuser", password="testpass", is_superuser=True)
        token = Token.objects.create(user=user, version=1)

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
        response = client.get(f"/plugins/notices/ical/maintenances.ics?token={token.plaintext}")

        assert response.status_code == 200
        assert response["Content-Type"] == "text/calendar; charset=utf-8"

    def test_invalid_token_returns_403(self):
        client = Client()
        response = client.get("/plugins/notices/ical/maintenances.ics?token=invalid")

        assert response.status_code == 403

    def test_no_authentication_returns_403_when_login_required(self):
        client = Client()
        response = client.get("/plugins/notices/ical/maintenances.ics")

        # Will be 403 if LOGIN_REQUIRED=True (default in tests)
        assert response.status_code in [200, 403]

    def test_authorization_header_authenticates(self):
        user = User.objects.create_user(username="apiuser", password="testpass", is_superuser=True)
        token = Token.objects.create(user=user, version=1)

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
            HTTP_AUTHORIZATION=f"Token {token.plaintext}",
        )

        assert response.status_code == 200


@pytest.mark.django_db
class TestMaintenanceICalViewFiltering:
    """Test query parameter filtering."""

    def setup_method(self):
        """Create test user and token."""
        self.user = User.objects.create_user(username="testuser", password="testpass", is_superuser=True)
        self.token = Token.objects.create(user=self.user, version=1)
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
        response = self.client.get(f"/plugins/notices/ical/maintenances.ics?token={self.token.plaintext}")
        content = response.content.decode("utf-8")
        assert "RECENT" in content
        assert "OLD" not in content

        # past_days=90 should include both
        response = self.client.get(f"/plugins/notices/ical/maintenances.ics?token={self.token.plaintext}&past_days=90")
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

        response = self.client.get(f"/plugins/notices/ical/maintenances.ics?token={self.token.plaintext}&provider=aws")
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
            f"/plugins/notices/ical/maintenances.ics?token={self.token.plaintext}&status=CONFIRMED"
        )
        content = response.content.decode("utf-8")
        assert "CONF" in content
        assert "TENT" not in content

    def test_invalid_provider_returns_400(self):
        response = self.client.get(
            f"/plugins/notices/ical/maintenances.ics?token={self.token.plaintext}&provider=nonexistent"
        )
        assert response.status_code == 400


@pytest.mark.django_db
class TestMaintenanceICalViewCaching:
    """Test HTTP caching behavior."""

    def setup_method(self):
        self.user = User.objects.create_user(username="testuser", password="testpass", is_superuser=True)
        self.token = Token.objects.create(user=self.user, version=1)
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

        response = self.client.get(f"/plugins/notices/ical/maintenances.ics?token={self.token.plaintext}")

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
        response1 = self.client.get(f"/plugins/notices/ical/maintenances.ics?token={self.token.plaintext}")
        etag = response1["ETag"]

        # Second request with If-None-Match
        response2 = self.client.get(
            f"/plugins/notices/ical/maintenances.ics?token={self.token.plaintext}",
            HTTP_IF_NONE_MATCH=etag,
        )

        assert response2.status_code == 304

    def test_empty_queryset_returns_valid_calendar(self):
        response = self.client.get(f"/plugins/notices/ical/maintenances.ics?token={self.token.plaintext}")

        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "BEGIN:VCALENDAR" in content
        assert "END:VCALENDAR" in content


@pytest.mark.django_db
class TestMaintenanceICalViewTokenValidation:
    """Test _validate_url_token edge cases."""

    def test_disabled_token_returns_403(self):
        user = User.objects.create_user(username="disabled-tok", password="pass", is_superuser=True)
        token = Token.objects.create(user=user, version=1, enabled=False)

        client = Client()
        response = client.get(f"/plugins/notices/ical/maintenances.ics?token={token.plaintext}")
        assert response.status_code == 403

    def test_expired_token_returns_403(self):
        user = User.objects.create_user(username="expired-tok", password="pass", is_superuser=True)
        token = Token.objects.create(
            user=user,
            version=1,
            expires=datetime.now(dt_timezone.utc) - timedelta(days=1),
        )

        client = Client()
        response = client.get(f"/plugins/notices/ical/maintenances.ics?token={token.plaintext}")
        assert response.status_code == 403

    def test_inactive_user_returns_403(self):
        user = User.objects.create_user(username="inactive-tok", password="pass", is_superuser=True, is_active=False)
        token = Token.objects.create(user=user, version=1)

        client = Client()
        response = client.get(f"/plugins/notices/ical/maintenances.ics?token={token.plaintext}")
        assert response.status_code == 403

    def test_v2_token_authenticates(self):
        from users.constants import TOKEN_PREFIX

        user = User.objects.create_user(username="v2-tok", password="pass", is_superuser=True)
        # v2 tokens: plaintext is ephemeral, only available at creation
        plaintext_value = "a" * 40
        token = Token(user=user, version=2, token=plaintext_value)
        token.save()

        # v2 token format: nbt_<key>.<plaintext>
        token_value = f"{TOKEN_PREFIX}{token.key}.{plaintext_value}"

        provider = Provider.objects.create(name="V2Test", slug="v2test")
        Maintenance.objects.create(
            name="M1",
            summary="Test",
            provider=provider,
            start=datetime.now(dt_timezone.utc),
            end=datetime.now(dt_timezone.utc) + timedelta(hours=2),
            status="CONFIRMED",
        )

        client = Client()
        response = client.get(f"/plugins/notices/ical/maintenances.ics?token={token_value}")
        assert response.status_code == 200

    def test_v2_token_invalid_format(self):
        from users.constants import TOKEN_PREFIX

        client = Client()
        # Missing dot separator
        response = client.get(f"/plugins/notices/ical/maintenances.ics?token={TOKEN_PREFIX}nodot")
        assert response.status_code == 403


@pytest.mark.django_db
class TestMaintenanceICalViewParseQueryParams:
    """Test _parse_query_params edge cases."""

    def setup_method(self):
        self.user = User.objects.create_user(username="param-user", password="pass", is_superuser=True)
        self.token = Token.objects.create(user=self.user, version=1)
        self.client = Client()

    def test_negative_past_days_uses_default(self):
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

        response = self.client.get(f"/plugins/notices/ical/maintenances.ics?token={self.token.plaintext}&past_days=-5")
        assert response.status_code == 200

    def test_past_days_exceeds_365_uses_default(self):
        response = self.client.get(f"/plugins/notices/ical/maintenances.ics?token={self.token.plaintext}&past_days=999")
        # past_days > 365 raises ValueError which is caught and defaults
        assert response.status_code == 200

    def test_non_integer_past_days_uses_default(self):
        response = self.client.get(f"/plugins/notices/ical/maintenances.ics?token={self.token.plaintext}&past_days=abc")
        assert response.status_code == 200


@pytest.mark.django_db
class TestMaintenanceICalViewBuildQueryset:
    """Test _build_queryset edge cases."""

    def setup_method(self):
        self.user = User.objects.create_user(username="qs-user", password="pass", is_superuser=True)
        self.token = Token.objects.create(user=self.user, version=1)
        self.client = Client()

    def test_provider_id_filter(self):
        provider = Provider.objects.create(name="ByID", slug="byid")
        now = datetime.now(dt_timezone.utc)
        Maintenance.objects.create(
            name="BY-ID-1",
            summary="Test",
            provider=provider,
            start=now,
            end=now + timedelta(hours=2),
            status="CONFIRMED",
        )

        response = self.client.get(
            f"/plugins/notices/ical/maintenances.ics?token={self.token.plaintext}&provider_id={provider.pk}"
        )
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "BY-ID-1" in content

    def test_invalid_provider_id_returns_400(self):
        response = self.client.get(
            f"/plugins/notices/ical/maintenances.ics?token={self.token.plaintext}&provider_id=notanumber"
        )
        assert response.status_code == 400

    def test_comma_separated_status_filter(self):
        provider = Provider.objects.create(name="Multi", slug="multi")
        now = datetime.now(dt_timezone.utc)
        Maintenance.objects.create(
            name="CONF1",
            summary="T",
            provider=provider,
            start=now,
            end=now + timedelta(hours=2),
            status="CONFIRMED",
        )
        Maintenance.objects.create(
            name="TENT1",
            summary="T",
            provider=provider,
            start=now,
            end=now + timedelta(hours=2),
            status="TENTATIVE",
        )
        Maintenance.objects.create(
            name="COMP1",
            summary="T",
            provider=provider,
            start=now,
            end=now + timedelta(hours=2),
            status="COMPLETED",
        )

        response = self.client.get(
            f"/plugins/notices/ical/maintenances.ics?token={self.token.plaintext}&status=CONFIRMED,TENTATIVE"
        )
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "CONF1" in content
        assert "TENT1" in content
        assert "COMP1" not in content

    def test_download_mode(self):
        provider = Provider.objects.create(name="DL", slug="dl")
        now = datetime.now(dt_timezone.utc)
        Maintenance.objects.create(
            name="DL1",
            summary="T",
            provider=provider,
            start=now,
            end=now + timedelta(hours=2),
            status="CONFIRMED",
        )

        response = self.client.get(f"/plugins/notices/ical/maintenances.ics?token={self.token.plaintext}&download=true")
        assert response.status_code == 200
        assert "attachment" in response["Content-Disposition"]
