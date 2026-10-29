"""Tests for the maintenance duration filters (#85)."""

import pytest

from notices.filtersets import MaintenanceFilterSet
from notices.models import Maintenance


def _names(data):
    qs = MaintenanceFilterSet(data, queryset=Maintenance.objects.all()).qs
    return set(qs.values_list("name", flat=True))


def _is_valid(data):
    return MaintenanceFilterSet(data, queryset=Maintenance.objects.none()).is_valid()


@pytest.mark.django_db
class TestMaintenanceDurationFilter:
    def test_duration_max_is_inclusive(self, make_maintenance):
        make_maintenance("M24", hours=24)
        make_maintenance("M25", hours=25)
        assert _names({"duration_max": "24"}) == {"M24"}

    def test_duration_min_is_inclusive(self, make_maintenance):
        make_maintenance("M2", hours=2)
        make_maintenance("M24", hours=24)
        make_maintenance("M25", hours=25)
        assert _names({"duration_min": "24"}) == {"M24", "M25"}

    def test_fractional_hours(self, make_maintenance):
        make_maintenance("M90MIN", hours=1.5)
        assert _names({"duration_max": "1.5"}) == {"M90MIN"}
        assert _names({"duration_max": "1.4"}) == set()

    def test_min_and_max_combined(self, make_maintenance):
        make_maintenance("M2", hours=2)
        make_maintenance("M24", hours=24)
        make_maintenance("M25", hours=25)
        assert _names({"duration_min": "2.5", "duration_max": "24"}) == {"M24"}

    def test_negative_duration_is_invalid(self):
        assert not _is_valid({"duration_max": "-1"})

    def test_huge_duration_is_invalid(self):
        """A value too large for timedelta must be a validation error, not a 500."""
        assert not _is_valid({"duration_max": "99999999999"})
