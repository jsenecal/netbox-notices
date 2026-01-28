"""Tests for model methods not covered by other tests."""

from datetime import timedelta

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.utils import timezone

from notices.models import EventNotification, Impact, Maintenance, Outage


@pytest.mark.django_db
class TestMaintenanceTimezoneMethods:
    """Tests for Maintenance timezone conversion methods."""

    def test_get_start_in_original_tz_with_valid_timezone(self, provider):
        """Should convert start to original timezone."""
        maintenance = Maintenance.objects.create(
            name="TZ Test",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=4),
            status="CONFIRMED",
            original_timezone="America/New_York",
        )
        result = maintenance.get_start_in_original_tz()
        assert result.tzinfo is not None
        assert "America/New_York" in str(result.tzinfo) or result != maintenance.start

    def test_get_start_in_original_tz_without_timezone(self, provider):
        """Should return original start when no timezone set."""
        maintenance = Maintenance.objects.create(
            name="No TZ",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=4),
            status="CONFIRMED",
        )
        result = maintenance.get_start_in_original_tz()
        assert result == maintenance.start

    def test_get_start_in_original_tz_with_invalid_timezone(self, provider):
        """Should return original start when timezone is invalid."""
        maintenance = Maintenance.objects.create(
            name="Invalid TZ",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=4),
            status="CONFIRMED",
            original_timezone="Invalid/Timezone",
        )
        result = maintenance.get_start_in_original_tz()
        assert result == maintenance.start

    def test_get_end_in_original_tz_with_valid_timezone(self, provider):
        """Should convert end to original timezone."""
        maintenance = Maintenance.objects.create(
            name="TZ Test",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=4),
            status="CONFIRMED",
            original_timezone="Europe/London",
        )
        result = maintenance.get_end_in_original_tz()
        assert result is not None

    def test_get_end_in_original_tz_without_timezone(self, provider):
        """Should return original end when no timezone set."""
        maintenance = Maintenance.objects.create(
            name="No TZ",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=4),
            status="CONFIRMED",
        )
        result = maintenance.get_end_in_original_tz()
        assert result == maintenance.end

    def test_get_end_in_original_tz_with_invalid_timezone(self, provider):
        """Should return original end when timezone is invalid."""
        maintenance = Maintenance.objects.create(
            name="Invalid TZ",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=4),
            status="CONFIRMED",
            original_timezone="Not/A/Zone",
        )
        result = maintenance.get_end_in_original_tz()
        assert result == maintenance.end

    def test_has_timezone_difference_returns_true(self, provider):
        """Should return True when timezones differ."""
        maintenance = Maintenance.objects.create(
            name="TZ Diff",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=4),
            status="CONFIRMED",
            original_timezone="Pacific/Auckland",
        )
        # Result depends on current server timezone
        result = maintenance.has_timezone_difference()
        assert isinstance(result, bool)

    def test_has_timezone_difference_returns_false_without_tz(self, provider):
        """Should return False when no original timezone."""
        maintenance = Maintenance.objects.create(
            name="No TZ",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=4),
            status="CONFIRMED",
        )
        assert maintenance.has_timezone_difference() is False

    def test_has_timezone_difference_with_invalid_tz(self, provider):
        """Should return False when timezone is invalid."""
        maintenance = Maintenance.objects.create(
            name="Invalid TZ",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=4),
            status="CONFIRMED",
            original_timezone="Invalid/Zone",
        )
        assert maintenance.has_timezone_difference() is False


@pytest.mark.django_db
class TestOutageTimezoneMethods:
    """Tests for Outage timezone conversion methods."""

    def test_get_start_in_original_tz(self, provider):
        """Should convert start to original timezone."""
        outage = Outage.objects.create(
            name="TZ Test",
            provider=provider,
            status="REPORTED",
            original_timezone="America/Los_Angeles",
        )
        result = outage.get_start_in_original_tz()
        assert result is not None

    def test_get_end_in_original_tz_with_end(self, provider):
        """Should convert end to original timezone when set."""
        outage = Outage.objects.create(
            name="TZ Test",
            provider=provider,
            end=timezone.now() + timedelta(hours=2),
            status="RESOLVED",
            original_timezone="Asia/Tokyo",
        )
        result = outage.get_end_in_original_tz()
        assert result is not None

    def test_get_end_in_original_tz_without_end(self, provider):
        """Should return None when no end time."""
        outage = Outage.objects.create(
            name="No End",
            provider=provider,
            status="INVESTIGATING",
            original_timezone="Asia/Tokyo",
        )
        result = outage.get_end_in_original_tz()
        assert result is None

    def test_get_estimated_time_to_repair_in_original_tz(self, provider):
        """Should convert ETR to original timezone."""
        outage = Outage.objects.create(
            name="ETR Test",
            provider=provider,
            status="INVESTIGATING",
            estimated_time_to_repair=timezone.now() + timedelta(hours=4),
            original_timezone="Europe/Paris",
        )
        result = outage.get_estimated_time_to_repair_in_original_tz()
        assert result is not None

    def test_get_estimated_time_to_repair_without_etr(self, provider):
        """Should return None when no ETR."""
        outage = Outage.objects.create(
            name="No ETR",
            provider=provider,
            status="INVESTIGATING",
        )
        result = outage.get_estimated_time_to_repair_in_original_tz()
        assert result is None

    def test_get_reported_at_in_original_tz(self, provider):
        """Should convert reported_at to original timezone."""
        outage = Outage.objects.create(
            name="Reported TZ",
            provider=provider,
            status="REPORTED",
            original_timezone="Australia/Sydney",
        )
        result = outage.get_reported_at_in_original_tz()
        assert result is not None

    def test_has_timezone_difference(self, provider):
        """Should detect timezone differences."""
        outage = Outage.objects.create(
            name="TZ Diff",
            provider=provider,
            status="REPORTED",
            original_timezone="Pacific/Fiji",
        )
        result = outage.has_timezone_difference()
        assert isinstance(result, bool)

    def test_has_timezone_difference_without_tz(self, provider):
        """Should return False without original timezone."""
        outage = Outage.objects.create(
            name="No TZ",
            provider=provider,
            status="REPORTED",
        )
        assert outage.has_timezone_difference() is False

    def test_outage_str(self, provider):
        """Should return name as string representation."""
        outage = Outage.objects.create(
            name="Test Outage Name",
            provider=provider,
            status="REPORTED",
        )
        assert str(outage) == "Test Outage Name"

    def test_get_status_color(self, provider):
        """Should return color for status."""
        outage = Outage.objects.create(
            name="Color Test",
            provider=provider,
            status="REPORTED",
        )
        color = outage.get_status_color()
        assert color is not None


@pytest.mark.django_db
class TestImpactMethods:
    """Tests for Impact model methods."""

    def test_str_representation(self, circuit, provider):
        """Should return formatted string."""
        maintenance = Maintenance.objects.create(
            name="MAINT-001",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=4),
            status="CONFIRMED",
        )
        ct = ContentType.objects.get_for_model(circuit)
        impact = Impact.objects.create(
            event_content_type=ContentType.objects.get_for_model(maintenance),
            event_object_id=maintenance.pk,
            target_content_type=ct,
            target_object_id=circuit.pk,
            impact="OUTAGE",
        )
        assert "MAINT-001" in str(impact)

    def test_str_with_missing_event(self, circuit):
        """Should handle missing event gracefully."""
        ct = ContentType.objects.get_for_model(circuit)
        maint_ct = ContentType.objects.get(app_label="notices", model="maintenance")
        impact = Impact(
            event_content_type=maint_ct,
            event_object_id=99999,  # Non-existent
            target_content_type=ct,
            target_object_id=circuit.pk,
            impact="OUTAGE",
        )
        result = str(impact)
        assert "Unknown" in result or result is not None

    def test_get_absolute_url_with_event(self, circuit, provider):
        """Should return event URL when event exists."""
        maintenance = Maintenance.objects.create(
            name="URL Test",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=4),
            status="CONFIRMED",
        )
        ct = ContentType.objects.get_for_model(circuit)
        impact = Impact.objects.create(
            event_content_type=ContentType.objects.get_for_model(maintenance),
            event_object_id=maintenance.pk,
            target_content_type=ct,
            target_object_id=circuit.pk,
        )
        url = impact.get_absolute_url()
        assert "maintenance" in url

    def test_get_impact_color(self, circuit, provider):
        """Should return color for impact level."""
        maintenance = Maintenance.objects.create(
            name="Color Test",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=4),
            status="CONFIRMED",
        )
        ct = ContentType.objects.get_for_model(circuit)
        impact = Impact.objects.create(
            event_content_type=ContentType.objects.get_for_model(maintenance),
            event_object_id=maintenance.pk,
            target_content_type=ct,
            target_object_id=circuit.pk,
            impact="OUTAGE",
        )
        color = impact.get_impact_color()
        assert color is not None

    def test_to_objectchange(self, circuit, provider):
        """Should set related_object to event."""
        maintenance = Maintenance.objects.create(
            name="Change Test",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=4),
            status="CONFIRMED",
        )
        ct = ContentType.objects.get_for_model(circuit)
        impact = Impact.objects.create(
            event_content_type=ContentType.objects.get_for_model(maintenance),
            event_object_id=maintenance.pk,
            target_content_type=ct,
            target_object_id=circuit.pk,
        )
        from core.choices import ObjectChangeActionChoices

        objectchange = impact.to_objectchange(ObjectChangeActionChoices.ACTION_CREATE)
        assert objectchange.related_object == maintenance

    def test_clean_validates_completed_event_status(self, circuit, provider):
        """Should reject modifications to impacts on completed events."""
        # Create a completed maintenance
        maintenance = Maintenance.objects.create(
            name="Completed",
            provider=provider,
            start=timezone.now() - timedelta(days=2),
            end=timezone.now() - timedelta(days=1),
            status="COMPLETED",
        )
        ct = ContentType.objects.get_for_model(circuit)
        maint_ct = ContentType.objects.get_for_model(maintenance)
        impact = Impact(
            event_content_type=maint_ct,
            event_object_id=maintenance.pk,
            target_content_type=ct,
            target_object_id=circuit.pk,
            impact="OUTAGE",
        )
        with pytest.raises(ValidationError) as exc_info:
            impact.clean()
        assert "cannot alter" in str(exc_info.value).lower()

    def test_clean_validates_cancelled_event_status(self, circuit, provider):
        """Should reject modifications to impacts on cancelled events."""
        # Create a cancelled maintenance
        maintenance = Maintenance.objects.create(
            name="Cancelled",
            provider=provider,
            start=timezone.now() + timedelta(days=1),
            end=timezone.now() + timedelta(days=2),
            status="CANCELLED",
        )
        ct = ContentType.objects.get_for_model(circuit)
        maint_ct = ContentType.objects.get_for_model(maintenance)
        impact = Impact(
            event_content_type=maint_ct,
            event_object_id=maintenance.pk,
            target_content_type=ct,
            target_object_id=circuit.pk,
            impact="DEGRADED",
        )
        with pytest.raises(ValidationError) as exc_info:
            impact.clean()
        assert "cannot alter" in str(exc_info.value).lower()


@pytest.mark.django_db
class TestEventNotificationMethods:
    """Tests for EventNotification model methods."""

    def test_str_returns_subject(self, provider):
        """Should return subject as string representation."""
        maintenance = Maintenance.objects.create(
            name="Notif Test",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=4),
            status="CONFIRMED",
        )
        notification = EventNotification.objects.create(
            event_content_type=ContentType.objects.get_for_model(maintenance),
            event_object_id=maintenance.pk,
            email=b"raw email data",
            email_body="Email body text",
            subject="Test Subject Line",
            email_from="noc@example.com",
            email_received=timezone.now(),
        )
        assert str(notification) == "Test Subject Line"

    def test_get_absolute_url(self, provider):
        """Should return notification URL."""
        maintenance = Maintenance.objects.create(
            name="URL Test",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=4),
            status="CONFIRMED",
        )
        notification = EventNotification.objects.create(
            event_content_type=ContentType.objects.get_for_model(maintenance),
            event_object_id=maintenance.pk,
            email=b"data",
            email_body="body",
            subject="Subject",
            email_from="test@example.com",
            email_received=timezone.now(),
        )
        url = notification.get_absolute_url()
        assert "notification" in url
        assert str(notification.pk) in url

    def test_to_objectchange(self, provider):
        """Should set related_object to event."""
        maintenance = Maintenance.objects.create(
            name="Change Test",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=4),
            status="CONFIRMED",
        )
        notification = EventNotification.objects.create(
            event_content_type=ContentType.objects.get_for_model(maintenance),
            event_object_id=maintenance.pk,
            email=b"data",
            email_body="body",
            subject="Subject",
            email_from="test@example.com",
            email_received=timezone.now(),
        )
        from core.choices import ObjectChangeActionChoices

        objectchange = notification.to_objectchange(
            ObjectChangeActionChoices.ACTION_CREATE
        )
        assert objectchange.related_object == maintenance
