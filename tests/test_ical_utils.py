"""Tests for iCal utility functions."""

import hashlib
import pytest
from datetime import datetime, timezone as dt_timezone

from vendor_notification.ical_utils import calculate_etag, get_ical_status


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
