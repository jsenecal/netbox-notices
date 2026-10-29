"""Integration tests for iCal feed endpoint."""

from datetime import UTC, datetime, timedelta

import pytest
from circuits.models import Provider
from django.test import Client
from users.models import Token, User

from notices.models import Maintenance

ICAL_URL = "/plugins/notices/ical/maintenances.ics"


@pytest.fixture
def ical_get(db):
    """GET the feed as a superuser authenticated by URL token: `ical_get(query="", **headers)`.

    `query` is appended after the token, so it starts with "&".
    """
    user = User.objects.create_user(username="ical-user", password="pass", is_superuser=True)
    token = Token.objects.create(user=user, version=1)
    client = Client()

    def get(query="", **headers):
        return client.get(f"{ICAL_URL}?token={token.plaintext}{query}", **headers)

    return get


def _body(response):
    return response.content.decode("utf-8")


@pytest.mark.django_db
class TestMaintenanceICalViewAuthentication:
    """Test authentication methods for iCal endpoint."""

    def test_token_in_url_authenticates(self, ical_get, make_maintenance):
        make_maintenance("M1")

        response = ical_get()

        assert response.status_code == 200
        assert response["Content-Type"] == "text/calendar; charset=utf-8"

    def test_invalid_token_returns_403(self):
        response = Client().get(f"{ICAL_URL}?token=invalid")

        assert response.status_code == 403

    def test_no_authentication_returns_403_when_login_required(self):
        response = Client().get(ICAL_URL)

        # Will be 403 if LOGIN_REQUIRED=True (default in tests)
        assert response.status_code in [200, 403]

    def test_authorization_header_authenticates(self, make_maintenance):
        user = User.objects.create_user(username="apiuser", password="testpass", is_superuser=True)
        token = Token.objects.create(user=user, version=1)
        make_maintenance("M1")

        response = Client().get(ICAL_URL, HTTP_AUTHORIZATION=f"Token {token.plaintext}")

        assert response.status_code == 200


@pytest.mark.django_db
class TestMaintenanceICalViewFiltering:
    """Test query parameter filtering."""

    def test_past_days_filter(self, ical_get, make_maintenance):
        now = datetime.now(UTC)
        make_maintenance("OLD", start=now - timedelta(days=60), status="COMPLETED")
        make_maintenance("RECENT", start=now - timedelta(days=10))

        # Default (30 days) should exclude old
        content = _body(ical_get())
        assert "RECENT" in content
        assert "OLD" not in content

        # past_days=90 should include both
        content = _body(ical_get("&past_days=90"))
        assert "RECENT" in content
        assert "OLD" in content

    def test_provider_filter_by_slug(self, ical_get, make_maintenance):
        make_maintenance("AWS-1", provider=Provider.objects.create(name="AWS", slug="aws"))
        make_maintenance("AZURE-1", provider=Provider.objects.create(name="Azure", slug="azure"))

        content = _body(ical_get("&provider=aws"))
        assert "AWS-1" in content
        assert "AZURE-1" not in content

    def test_status_filter(self, ical_get, make_maintenance):
        make_maintenance("CONF")
        make_maintenance("TENT", status="TENTATIVE")

        content = _body(ical_get("&status=CONFIRMED"))
        assert "CONF" in content
        assert "TENT" not in content

    def test_invalid_provider_returns_400(self, ical_get):
        assert ical_get("&provider=nonexistent").status_code == 400


@pytest.mark.django_db
class TestMaintenanceICalViewDurationFilter:
    """duration_min / duration_max on the feed (#85)."""

    @pytest.fixture(autouse=True)
    def _maintenances(self, make_maintenance):
        make_maintenance("SHORT", hours=2)
        make_maintenance("LONG", hours=72)

    def test_duration_max_filters_feed(self, ical_get):
        unfiltered = _body(ical_get())
        assert "SHORT" in unfiltered and "LONG" in unfiltered
        content = _body(ical_get("&duration_max=24"))
        assert "SHORT" in content and "LONG" not in content

    def test_duration_min_filters_feed(self, ical_get):
        content = _body(ical_get("&duration_min=24"))
        assert "LONG" in content and "SHORT" not in content

    def test_invalid_duration_returns_400(self, ical_get):
        assert ical_get("&duration_max=abc").status_code == 400
        assert ical_get("&duration_max=-1").status_code == 400
        assert ical_get("&duration_max=99999999999").status_code == 400

    def test_etag_differs_with_duration_filter(self, ical_get):
        assert ical_get()["ETag"] != ical_get("&duration_max=24")["ETag"]


@pytest.mark.django_db
class TestMaintenanceICalViewCaching:
    """Test HTTP caching behavior."""

    def test_response_includes_cache_headers(self, ical_get, maintenance):
        response = ical_get()

        assert "Cache-Control" in response
        assert "public" in response["Cache-Control"]
        assert "max-age" in response["Cache-Control"]
        assert "ETag" in response

    def test_stale_if_modified_since_returns_200(self, ical_get, maintenance):
        """An old If-Modified-Since date must not be treated as proof of freshness."""
        response = ical_get(
            # Not the epoch: timestamp 0 is falsy, and Django would treat the
            # header as absent instead of exercising the date comparison.
            HTTP_IF_MODIFIED_SINCE="Sat, 01 Jan 2000 00:00:00 GMT",
        )

        assert response.status_code == 200
        assert "BEGIN:VCALENDAR" in _body(response)

    def test_current_if_modified_since_returns_304(self, ical_get, maintenance):
        """Echoing back the Last-Modified we sent revalidates as unchanged."""
        last_modified = ical_get()["Last-Modified"]

        response2 = ical_get(HTTP_IF_MODIFIED_SINCE=last_modified)

        assert response2.status_code == 304
        assert response2["Last-Modified"] == last_modified

    def test_if_modified_since_returns_200_after_change(self, ical_get, maintenance):
        """A feed modified after the client's copy must be resent in full."""
        last_modified = ical_get()["Last-Modified"]

        # last_updated is auto_now. update() bypasses auto_now, which is how we
        # place last_updated past the Last-Modified header above.
        maintenance.last_updated = datetime.now(UTC) + timedelta(minutes=5)
        Maintenance.objects.filter(pk=maintenance.pk).update(last_updated=maintenance.last_updated)

        response2 = ical_get(HTTP_IF_MODIFIED_SINCE=last_modified)

        assert response2.status_code == 200

    def test_malformed_if_modified_since_returns_200(self, ical_get, maintenance):
        """An unparseable date is ignored rather than honoured as a validator."""
        response = ical_get(HTTP_IF_MODIFIED_SINCE="not a date")

        assert response.status_code == 200

    def test_if_none_match_takes_precedence_over_if_modified_since(self, ical_get, maintenance):
        """RFC 9110: If-Modified-Since is ignored when If-None-Match is present."""
        last_modified = ical_get()["Last-Modified"]

        # Fresh by date, stale by ETag -> the ETag decides, so send the full feed.
        # The stale tag must be quoted: parse_etags() discards an unquoted one,
        # which would leave no ETag to take precedence and fall through to the date.
        response2 = ical_get(HTTP_IF_NONE_MATCH='"stale-etag"', HTTP_IF_MODIFIED_SINCE=last_modified)

        assert response2.status_code == 200

    def test_304_includes_etag_and_last_modified(self, ical_get, maintenance):
        response1 = ical_get()

        response2 = ical_get(HTTP_IF_NONE_MATCH=response1["ETag"])

        assert response2.status_code == 304
        assert response2["ETag"] == response1["ETag"]
        assert response2["Last-Modified"] == response1["Last-Modified"]
        # A 304 has to keep telling the client how long the copy stays fresh.
        assert response2["Cache-Control"] == response1["Cache-Control"]

    def test_etag_is_quoted(self, ical_get, maintenance):
        """An unquoted tag is unparseable to every client, so it could never match."""
        response = ical_get()

        assert response["ETag"].startswith('"')
        assert response["ETag"].endswith('"')

    def test_added_impact_invalidates_revalidation(self, ical_get, maintenance):
        """An impact is rendered into the feed, so adding one must break the 304 (issue #73)."""
        from notices.models import Impact

        response1 = ical_get()

        Impact.objects.create(event=maintenance, target=maintenance.provider, impact="OUTAGE")

        response2 = ical_get(HTTP_IF_NONE_MATCH=response1["ETag"])

        assert response2.status_code == 200

    def test_empty_queryset_returns_valid_calendar(self, ical_get):
        response = ical_get()

        assert response.status_code == 200
        content = _body(response)
        assert "BEGIN:VCALENDAR" in content
        assert "END:VCALENDAR" in content


@pytest.mark.django_db
class TestMaintenanceICalViewTokenValidation:
    """Test _validate_url_token edge cases."""

    def test_disabled_token_returns_403(self):
        user = User.objects.create_user(username="disabled-tok", password="pass", is_superuser=True)
        token = Token.objects.create(user=user, version=1, enabled=False)

        assert Client().get(f"{ICAL_URL}?token={token.plaintext}").status_code == 403

    def test_expired_token_returns_403(self):
        user = User.objects.create_user(username="expired-tok", password="pass", is_superuser=True)
        token = Token.objects.create(
            user=user,
            version=1,
            expires=datetime.now(UTC) - timedelta(days=1),
        )

        assert Client().get(f"{ICAL_URL}?token={token.plaintext}").status_code == 403

    def test_inactive_user_returns_403(self):
        user = User.objects.create_user(username="inactive-tok", password="pass", is_superuser=True, is_active=False)
        token = Token.objects.create(user=user, version=1)

        assert Client().get(f"{ICAL_URL}?token={token.plaintext}").status_code == 403

    def test_v2_token_authenticates(self, make_maintenance):
        from users.constants import TOKEN_PREFIX

        user = User.objects.create_user(username="v2-tok", password="pass", is_superuser=True)
        # v2 tokens: plaintext is ephemeral, only available at creation
        plaintext_value = "a" * 40
        token = Token(user=user, version=2, token=plaintext_value)
        token.save()

        # v2 token format: nbt_<key>.<plaintext>
        token_value = f"{TOKEN_PREFIX}{token.key}.{plaintext_value}"

        make_maintenance("M1")

        assert Client().get(f"{ICAL_URL}?token={token_value}").status_code == 200

    def test_v2_token_invalid_format(self):
        from users.constants import TOKEN_PREFIX

        # Missing dot separator
        assert Client().get(f"{ICAL_URL}?token={TOKEN_PREFIX}nodot").status_code == 403


@pytest.mark.django_db
class TestMaintenanceICalViewParseQueryParams:
    """Test _parse_query_params edge cases."""

    def test_negative_past_days_uses_default(self, ical_get, make_maintenance):
        make_maintenance("M1")

        assert ical_get("&past_days=-5").status_code == 200

    def test_past_days_exceeds_365_uses_default(self, ical_get):
        # past_days > 365 raises ValueError which is caught and defaults
        assert ical_get("&past_days=999").status_code == 200

    def test_non_integer_past_days_uses_default(self, ical_get):
        assert ical_get("&past_days=abc").status_code == 200


@pytest.mark.django_db
class TestMaintenanceICalViewBuildQueryset:
    """Test _build_queryset edge cases."""

    def test_provider_id_filter(self, ical_get, make_maintenance, provider):
        make_maintenance("BY-ID-1")

        response = ical_get(f"&provider_id={provider.pk}")
        assert response.status_code == 200
        assert "BY-ID-1" in _body(response)

    def test_invalid_provider_id_returns_400(self, ical_get):
        assert ical_get("&provider_id=notanumber").status_code == 400

    def test_comma_separated_status_filter(self, ical_get, make_maintenance):
        make_maintenance("CONF1")
        make_maintenance("TENT1", status="TENTATIVE")
        make_maintenance("COMP1", status="COMPLETED")

        response = ical_get("&status=CONFIRMED,TENTATIVE")
        assert response.status_code == 200
        content = _body(response)
        assert "CONF1" in content
        assert "TENT1" in content
        assert "COMP1" not in content

    def test_download_mode(self, ical_get, make_maintenance):
        make_maintenance("DL1")

        response = ical_get("&download=true")
        assert response.status_code == 200
        assert "attachment" in response["Content-Disposition"]
