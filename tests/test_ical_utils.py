"""Tests for iCal utility functions."""

import hashlib
import pytest
from datetime import datetime, timezone as dt_timezone
from django.test import RequestFactory

from circuits.models import Provider
from vendor_notification.models import Maintenance
from vendor_notification.ical_utils import calculate_etag, get_ical_status, generate_maintenance_ical


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
        dt1 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=dt_timezone.utc)
        dt2 = datetime(2025, 1, 2, 12, 0, 0, tzinfo=dt_timezone.utc)
        etag1 = calculate_etag(count=5, latest_modified=dt1, params={})
        etag2 = calculate_etag(count=5, latest_modified=dt2, params={})
        assert etag1 != etag2

    def test_etag_none_latest_modified(self):
        etag = calculate_etag(count=0, latest_modified=None, params={})
        assert isinstance(etag, str)
        assert len(etag) == 32

    def test_etag_deterministic(self):
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=dt_timezone.utc)
        params = {"provider": "aws"}
        etag1 = calculate_etag(count=5, latest_modified=dt, params=params)
        etag2 = calculate_etag(count=5, latest_modified=dt, params=params)
        assert etag1 == etag2


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
            start=datetime(2025, 2, 1, 10, 0, 0, tzinfo=dt_timezone.utc),
            end=datetime(2025, 2, 1, 14, 0, 0, tzinfo=dt_timezone.utc),
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
            start=datetime(2025, 3, 1, 8, 0, 0, tzinfo=dt_timezone.utc),
            end=datetime(2025, 3, 1, 12, 0, 0, tzinfo=dt_timezone.utc),
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
