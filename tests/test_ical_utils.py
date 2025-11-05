"""Tests for iCal utility functions."""

import pytest

from vendor_notification.ical_utils import get_ical_status


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
