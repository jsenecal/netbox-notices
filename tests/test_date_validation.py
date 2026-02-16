"""Tests for date range validation on event models."""

from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone


@pytest.mark.django_db
class TestMaintenanceDateValidation:
    def test_end_before_start_raises_error(self, provider):
        from notices.models import Maintenance

        now = timezone.now()
        m = Maintenance(
            name="MAINT-001",
            summary="Test",
            provider=provider,
            status="CONFIRMED",
            start=now,
            end=now - timedelta(hours=1),
        )
        with pytest.raises(ValidationError, match="end.*must be after"):
            m.full_clean()

    def test_end_equal_to_start_is_valid(self, provider):
        from notices.models import Maintenance

        now = timezone.now()
        m = Maintenance(
            name="MAINT-002",
            summary="Test",
            provider=provider,
            status="CONFIRMED",
            start=now,
            end=now,
        )
        m.full_clean()  # Should not raise

    def test_end_after_start_is_valid(self, provider):
        from notices.models import Maintenance

        now = timezone.now()
        m = Maintenance(
            name="MAINT-003",
            summary="Test",
            provider=provider,
            status="CONFIRMED",
            start=now,
            end=now + timedelta(hours=4),
        )
        m.full_clean()  # Should not raise


@pytest.mark.django_db
class TestOutageDateValidation:
    def test_end_before_start_raises_error(self, provider):
        from notices.models import Outage

        now = timezone.now()
        o = Outage(
            name="OUT-001",
            summary="Test",
            provider=provider,
            status="RESOLVED",
            start=now,
            end=now - timedelta(hours=1),
        )
        with pytest.raises(ValidationError, match="end.*must be after"):
            o.full_clean()

    def test_resolved_without_end_raises_error(self, provider):
        """Existing validation still works."""
        from notices.models import Outage

        now = timezone.now()
        o = Outage(
            name="OUT-002",
            summary="Test",
            provider=provider,
            status="RESOLVED",
            start=now,
            end=None,
        )
        with pytest.raises(ValidationError, match="End time is required"):
            o.full_clean()

    def test_no_end_on_active_outage_is_valid(self, provider):
        """Outages without end are valid when not resolved."""
        from notices.models import Outage

        now = timezone.now()
        o = Outage(
            name="OUT-003",
            summary="Test",
            provider=provider,
            status="INVESTIGATING",
            start=now,
        )
        o.full_clean()  # Should not raise
