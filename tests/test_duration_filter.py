"""Tests for the maintenance duration filters (#85)."""

from datetime import timedelta

import pytest
from django.utils import timezone

from notices.filtersets import MaintenanceFilterSet
from notices.models import Maintenance


def _maint(provider, name, hours):
    start = timezone.now()
    return Maintenance.objects.create(
        name=name,
        summary="x",
        provider=provider,
        status="CONFIRMED",
        start=start,
        end=start + timedelta(hours=hours),
    )


def _names(data):
    qs = MaintenanceFilterSet(data, queryset=Maintenance.objects.all()).qs
    return set(qs.values_list("name", flat=True))


@pytest.mark.django_db
class TestMaintenanceDurationFilter:
    def test_duration_max_is_inclusive(self, provider):
        _maint(provider, "M24", 24)
        _maint(provider, "M25", 25)
        assert _names({"duration_max": "24"}) == {"M24"}

    def test_duration_min_is_inclusive(self, provider):
        _maint(provider, "M2", 2)
        _maint(provider, "M24", 24)
        _maint(provider, "M25", 25)
        assert _names({"duration_min": "24"}) == {"M24", "M25"}

    def test_fractional_hours(self, provider):
        _maint(provider, "M90MIN", 1.5)
        assert _names({"duration_max": "1.5"}) == {"M90MIN"}
        assert _names({"duration_max": "1.4"}) == set()

    def test_min_and_max_combined(self, provider):
        _maint(provider, "M2", 2)
        _maint(provider, "M24", 24)
        _maint(provider, "M25", 25)
        assert _names({"duration_min": "2.5", "duration_max": "24"}) == {"M24"}

    def test_negative_duration_is_invalid(self):
        fs = MaintenanceFilterSet({"duration_max": "-1"}, queryset=Maintenance.objects.all())
        assert not fs.is_valid()

    def test_huge_duration_is_invalid(self):
        """A value too large for timedelta must be a validation error, not a 500."""
        fs = MaintenanceFilterSet({"duration_max": "99999999999"}, queryset=Maintenance.objects.all())
        assert not fs.is_valid()
