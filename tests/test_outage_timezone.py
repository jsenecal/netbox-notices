"""Tests for Outage model timezone conversion methods."""

from datetime import timedelta

import pytest
from django.utils import timezone

from notices.models import Outage


@pytest.mark.django_db
class TestOutageTimezoneConversions:
    """Test Outage.*_in_original_tz methods."""

    def test_get_start_in_original_tz_valid(self, provider):
        now = timezone.now()
        outage = Outage.objects.create(
            name="O1",
            summary="Test",
            provider=provider,
            status="REPORTED",
            start=now,
            original_timezone="America/New_York",
        )
        result = outage.get_start_in_original_tz()
        assert result.tzinfo is not None
        assert str(result.tzinfo) == "America/New_York"

    def test_get_start_in_original_tz_invalid(self, provider):
        now = timezone.now()
        outage = Outage.objects.create(
            name="O1",
            summary="Test",
            provider=provider,
            status="REPORTED",
            start=now,
            original_timezone="Invalid/Zone",
        )
        result = outage.get_start_in_original_tz()
        # Falls back to raw start value
        assert result == now

    def test_get_start_in_original_tz_no_tz(self, provider):
        now = timezone.now()
        outage = Outage.objects.create(
            name="O1",
            summary="Test",
            provider=provider,
            status="REPORTED",
            start=now,
            original_timezone="",
        )
        result = outage.get_start_in_original_tz()
        assert result == now

    def test_get_end_in_original_tz_valid(self, provider):
        now = timezone.now()
        outage = Outage.objects.create(
            name="O1",
            summary="Test",
            provider=provider,
            status="RESOLVED",
            start=now,
            end=now + timedelta(hours=2),
            original_timezone="Europe/London",
        )
        result = outage.get_end_in_original_tz()
        assert str(result.tzinfo) == "Europe/London"

    def test_get_end_in_original_tz_invalid(self, provider):
        now = timezone.now()
        outage = Outage.objects.create(
            name="O1",
            summary="Test",
            provider=provider,
            status="RESOLVED",
            start=now,
            end=now + timedelta(hours=2),
            original_timezone="Bad/Zone",
        )
        result = outage.get_end_in_original_tz()
        assert result == outage.end

    def test_get_end_in_original_tz_no_end(self, provider):
        outage = Outage.objects.create(
            name="O1",
            summary="Test",
            provider=provider,
            status="REPORTED",
            original_timezone="America/New_York",
        )
        result = outage.get_end_in_original_tz()
        assert result is None

    def test_get_estimated_time_to_repair_in_original_tz_valid(self, provider):
        now = timezone.now()
        etr = now + timedelta(hours=4)
        outage = Outage.objects.create(
            name="O1",
            summary="Test",
            provider=provider,
            status="INVESTIGATING",
            start=now,
            estimated_time_to_repair=etr,
            original_timezone="Asia/Tokyo",
        )
        result = outage.get_estimated_time_to_repair_in_original_tz()
        assert str(result.tzinfo) == "Asia/Tokyo"

    def test_get_estimated_time_to_repair_in_original_tz_invalid(self, provider):
        now = timezone.now()
        etr = now + timedelta(hours=4)
        outage = Outage.objects.create(
            name="O1",
            summary="Test",
            provider=provider,
            status="INVESTIGATING",
            start=now,
            estimated_time_to_repair=etr,
            original_timezone="Nope/Zone",
        )
        result = outage.get_estimated_time_to_repair_in_original_tz()
        assert result == etr

    def test_get_estimated_time_to_repair_no_etr(self, provider):
        outage = Outage.objects.create(
            name="O1",
            summary="Test",
            provider=provider,
            status="REPORTED",
            original_timezone="Asia/Tokyo",
        )
        result = outage.get_estimated_time_to_repair_in_original_tz()
        assert result is None

    def test_get_reported_at_in_original_tz_valid(self, provider):
        now = timezone.now()
        outage = Outage.objects.create(
            name="O1",
            summary="Test",
            provider=provider,
            status="REPORTED",
            start=now,
            reported_at=now,
            original_timezone="Australia/Sydney",
        )
        result = outage.get_reported_at_in_original_tz()
        assert str(result.tzinfo) == "Australia/Sydney"

    def test_get_reported_at_in_original_tz_invalid(self, provider):
        now = timezone.now()
        outage = Outage.objects.create(
            name="O1",
            summary="Test",
            provider=provider,
            status="REPORTED",
            start=now,
            reported_at=now,
            original_timezone="Fake/TZ",
        )
        result = outage.get_reported_at_in_original_tz()
        assert result == now

    def test_get_reported_at_no_tz(self, provider):
        now = timezone.now()
        outage = Outage.objects.create(
            name="O1",
            summary="Test",
            provider=provider,
            status="REPORTED",
            start=now,
            reported_at=now,
            original_timezone="",
        )
        result = outage.get_reported_at_in_original_tz()
        assert result == now
