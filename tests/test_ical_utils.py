"""Tests for iCal utility functions."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from circuits.models import Circuit, CircuitType, Provider
from core.choices import ObjectChangeActionChoices
from core.models import ObjectChange
from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory
from django.utils import timezone as django_timezone

from notices.ical_utils import (
    calculate_etag,
    feed_last_modified,
    generate_maintenance_ical,
    get_ical_status,
    maintenance_window_cutoff,
)
from notices.models import Impact, Maintenance


class TestICalStatusMapping:
    """Test maintenance status to iCal status mapping."""

    def test_tentative_maps_to_tentative(self):
        assert get_ical_status("TENTATIVE") == "TENTATIVE"

    def test_confirmed_maps_to_confirmed(self):
        assert get_ical_status("CONFIRMED") == "CONFIRMED"

    def test_cancelled_maps_to_cancelled(self):
        assert get_ical_status("CANCELLED") == "CANCELLED"

    def test_in_process_maps_to_confirmed(self):
        assert get_ical_status("IN-PROCESS") == "CONFIRMED"

    def test_completed_maps_to_confirmed(self):
        assert get_ical_status("COMPLETED") == "CONFIRMED"

    def test_unknown_maps_to_tentative(self):
        assert get_ical_status("UNKNOWN") == "TENTATIVE"

    def test_rescheduled_maps_to_cancelled(self):
        assert get_ical_status("RE-SCHEDULED") == "CANCELLED"

    def test_invalid_status_returns_tentative(self):
        assert get_ical_status("INVALID") == "TENTATIVE"

    def test_none_status_returns_tentative(self):
        assert get_ical_status(None) == "TENTATIVE"


class TestETagCalculation:
    """Test ETag generation for cache validation."""

    def test_etag_includes_query_params(self):
        params = {"provider": "aws", "status": "CONFIRMED"}
        etag = calculate_etag(count=5, latest_modified=None, params=params)
        assert isinstance(etag, str)
        assert len(etag) == 32  # MD5 hash length

    def test_etag_includes_count(self):
        etag1 = calculate_etag(count=5, latest_modified=None, params={})
        etag2 = calculate_etag(count=10, latest_modified=None, params={})
        assert etag1 != etag2

    def test_etag_includes_latest_modified(self):
        dt1 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        dt2 = datetime(2025, 1, 2, 12, 0, 0, tzinfo=UTC)
        etag1 = calculate_etag(count=5, latest_modified=dt1, params={})
        etag2 = calculate_etag(count=5, latest_modified=dt2, params={})
        assert etag1 != etag2

    def test_etag_none_latest_modified(self):
        etag = calculate_etag(count=0, latest_modified=None, params={})
        assert isinstance(etag, str)
        assert len(etag) == 32

    def test_etag_deterministic(self):
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        params = {"provider": "aws"}
        etag1 = calculate_etag(count=5, latest_modified=dt, params=params)
        etag2 = calculate_etag(count=5, latest_modified=dt, params=params)
        assert etag1 == etag2

    def test_etag_includes_impact_count(self):
        """Adding or removing an impact must change the tag even when nothing else moved."""
        etag1 = calculate_etag(count=5, latest_modified=None, params={}, impact_count=0)
        etag2 = calculate_etag(count=5, latest_modified=None, params={}, impact_count=2)
        assert etag1 != etag2


@pytest.mark.django_db
class TestFeedLastModified:
    """The validator source must cover everything rendered into the feed body."""

    PAST_DAYS = 30

    @staticmethod
    def _backdate(instance, **fields):
        # update() bypasses auto_now/auto_now_add, so timestamps land exactly
        # where the test needs them instead of at now().
        type(instance).objects.filter(pk=instance.pk).update(**fields)

    def _maintenance(self, provider, start, last_updated, name="M1"):
        maintenance = Maintenance.objects.create(
            name=name,
            summary="Test",
            provider=provider,
            start=start,
            end=start + timedelta(hours=2),
            status="CONFIRMED",
        )
        self._backdate(maintenance, last_updated=last_updated)
        return maintenance

    def _backdate_provider(self, provider, when):
        self._backdate(provider, last_updated=when)

    def _queryset(self):
        return Maintenance.objects.filter(start__gte=maintenance_window_cutoff(self.PAST_DAYS))

    def test_latest_maintenance_update_wins(self, provider):
        now = django_timezone.now()
        self._backdate_provider(provider, now - timedelta(days=10))
        self._maintenance(provider, now - timedelta(days=1), now - timedelta(days=5), name="M1")
        self._maintenance(provider, now - timedelta(days=1), now - timedelta(days=3), name="M2")

        assert feed_last_modified(self._queryset(), self.PAST_DAYS) == now - timedelta(days=3)

    def test_null_last_updated_is_ignored(self, provider):
        """One NULL row must not blank the whole validator (issue #71)."""
        now = django_timezone.now()
        self._backdate_provider(provider, now - timedelta(days=10))
        self._maintenance(provider, now - timedelta(days=1), now - timedelta(days=5), name="M1")
        self._maintenance(provider, now - timedelta(days=1), None, name="M2")

        assert feed_last_modified(self._queryset(), self.PAST_DAYS) == now - timedelta(days=5)

    def test_impact_update_advances(self, provider):
        """An impact edit is rendered into DESCRIPTION, so it must move the validator (issue #73)."""
        now = django_timezone.now()
        self._backdate_provider(provider, now - timedelta(days=10))
        maintenance = self._maintenance(provider, now - timedelta(days=1), now - timedelta(days=5))

        impact = Impact.objects.create(event=maintenance, target=provider, impact="OUTAGE")
        self._backdate(impact, last_updated=now - timedelta(days=2))

        assert feed_last_modified(self._queryset(), self.PAST_DAYS) == now - timedelta(days=2)

    def test_provider_update_advances(self, provider):
        """A provider rename is rendered into LOCATION, so it must move the validator (issue #73)."""
        now = django_timezone.now()
        self._maintenance(provider, now - timedelta(days=1), now - timedelta(days=5))
        self._backdate_provider(provider, now - timedelta(days=2))

        assert feed_last_modified(self._queryset(), self.PAST_DAYS) == now - timedelta(days=2)

    def test_deletion_advances(self, provider):
        """A deletion shrinks the queryset, so the delete changelog must move the validator (issue #70)."""
        now = django_timezone.now()
        self._backdate_provider(provider, now - timedelta(days=10))
        self._maintenance(provider, now - timedelta(days=1), now - timedelta(days=5))

        change = ObjectChange.objects.create(
            user_name="test",
            request_id=uuid4(),
            action=ObjectChangeActionChoices.ACTION_DELETE,
            changed_object_type=ContentType.objects.get_for_model(Maintenance),
            changed_object_id=9999,
            object_repr="M-deleted",
        )
        self._backdate(change, time=now - timedelta(days=2))

        assert feed_last_modified(self._queryset(), self.PAST_DAYS) == now - timedelta(days=2)

    def test_window_exit_advances(self, provider):
        """An event leaving the past_days window changes the body at start + past_days (issue #70)."""
        now = django_timezone.now()
        self._backdate_provider(provider, now - timedelta(days=10))
        self._maintenance(provider, now - timedelta(days=1), now - timedelta(days=5), name="M-in")
        excluded = self._maintenance(
            provider, now - timedelta(days=self.PAST_DAYS + 1), now - timedelta(days=10), name="M-out"
        )

        expected = excluded.start + timedelta(days=self.PAST_DAYS)
        assert feed_last_modified(self._queryset(), self.PAST_DAYS) == expected

    def test_empty_feed_returns_none(self):
        assert feed_last_modified(self._queryset(), self.PAST_DAYS) is None


@pytest.mark.django_db
class TestICalGeneration:
    """Test iCal calendar generation from maintenances."""

    def test_generates_valid_ical(self):
        # Create test data
        provider = Provider.objects.create(name="Test Provider", slug="test-provider")
        maintenance = Maintenance.objects.create(
            name="MAINT-001",
            summary="Test maintenance",
            provider=provider,
            start=datetime(2025, 2, 1, 10, 0, 0, tzinfo=UTC),
            end=datetime(2025, 2, 1, 14, 0, 0, tzinfo=UTC),
            status="CONFIRMED",
        )

        # Generate iCal
        factory = RequestFactory()
        request = factory.get("/")
        request.META["HTTP_HOST"] = "netbox.example.com"

        ical = generate_maintenance_ical([maintenance], request)

        # Verify structure
        assert ical is not None
        ical_str = ical.to_ical().decode("utf-8")
        assert "BEGIN:VCALENDAR" in ical_str
        assert "VERSION:2.0" in ical_str
        assert "PRODID:-//NetBox Vendor Notification Plugin//EN" in ical_str
        assert "BEGIN:VEVENT" in ical_str
        assert "END:VEVENT" in ical_str
        assert "END:VCALENDAR" in ical_str

    def test_event_has_required_fields(self):
        provider = Provider.objects.create(name="AWS", slug="aws")
        maintenance = Maintenance.objects.create(
            name="MAINT-002",
            summary="Network upgrade",
            provider=provider,
            start=datetime(2025, 3, 1, 8, 0, 0, tzinfo=UTC),
            end=datetime(2025, 3, 1, 12, 0, 0, tzinfo=UTC),
            status="TENTATIVE",
            internal_ticket="CHG-12345",
            comments="Planned upgrade",
        )

        factory = RequestFactory()
        request = factory.get("/")
        request.META["HTTP_HOST"] = "netbox.example.com"

        ical = generate_maintenance_ical([maintenance], request)
        ical_str = ical.to_ical().decode("utf-8")

        # Check required iCal fields
        assert "UID:maintenance-" in ical_str
        assert "DTSTART:" in ical_str
        assert "DTEND:" in ical_str
        assert "SUMMARY:MAINT-002 - Network upgrade" in ical_str
        assert "STATUS:TENTATIVE" in ical_str
        assert "LOCATION:AWS" in ical_str

    def test_empty_queryset_returns_empty_calendar(self):
        factory = RequestFactory()
        request = factory.get("/")
        request.META["HTTP_HOST"] = "netbox.example.com"

        ical = generate_maintenance_ical([], request)
        ical_str = ical.to_ical().decode("utf-8")

        assert "BEGIN:VCALENDAR" in ical_str
        assert "END:VCALENDAR" in ical_str
        # Should not have any events
        assert ical_str.count("BEGIN:VEVENT") == 0

    def test_maintenance_with_impacts(self):
        """iCal description should include Affected Objects when impacts exist."""
        provider = Provider.objects.create(name="Impact Provider", slug="impact-provider")
        circuit_type = CircuitType.objects.create(name="Impact Type", slug="impact-type")
        circuit = Circuit.objects.create(cid="CKT-IMPACT-001", provider=provider, type=circuit_type)

        maintenance = Maintenance.objects.create(
            name="MAINT-IMPACT",
            summary="Maintenance with impacts",
            provider=provider,
            start=datetime(2025, 6, 1, 10, 0, 0, tzinfo=UTC),
            end=datetime(2025, 6, 1, 14, 0, 0, tzinfo=UTC),
            status="CONFIRMED",
        )

        maint_ct = ContentType.objects.get_for_model(Maintenance)
        circuit_ct = ContentType.objects.get_for_model(Circuit)
        Impact.objects.create(
            event_content_type=maint_ct,
            event_object_id=maintenance.pk,
            target_content_type=circuit_ct,
            target_object_id=circuit.pk,
            impact="OUTAGE",
        )

        # Must use queryset (not list) for impacts prefetch
        queryset = Maintenance.objects.filter(pk=maintenance.pk).prefetch_related("impacts")

        factory = RequestFactory()
        request = factory.get("/")
        request.META["HTTP_HOST"] = "netbox.example.com"

        ical = generate_maintenance_ical(queryset, request)
        ical_str = ical.to_ical().decode("utf-8")

        # iCal line folding wraps long lines — unfold before checking
        unfolded = ical_str.replace("\r\n ", "")
        assert "Affected Objects" in unfolded
        assert "OUTAGE" in unfolded
