import zoneinfo

from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone
from netbox.models import NetBoxModel
from utilities.choices import ChoiceSet


class TimeZoneChoices(ChoiceSet):
    """
    Timezone choices grouped by region for maintenance event scheduling.
    Uses IANA timezone database names.
    """

    key = "Maintenance.TimeZone"

    # Common/UTC timezones
    COMMON_CHOICES = [
        ("UTC", "UTC"),
        ("GMT", "GMT"),
    ]

    # Build regional timezone choices
    AFRICA_CHOICES = [
        (tz, tz)
        for tz in sorted(
            [
                "Africa/Cairo",
                "Africa/Johannesburg",
                "Africa/Lagos",
                "Africa/Nairobi",
                "Africa/Casablanca",
            ]
        )
    ]

    AMERICA_CHOICES = [
        (tz, tz)
        for tz in sorted(
            [
                "America/New_York",
                "America/Chicago",
                "America/Denver",
                "America/Los_Angeles",
                "America/Phoenix",
                "America/Anchorage",
                "America/Toronto",
                "America/Vancouver",
                "America/Montreal",
                "America/Mexico_City",
                "America/Sao_Paulo",
                "America/Buenos_Aires",
                "America/Santiago",
                "America/Bogota",
                "America/Lima",
            ]
        )
    ]

    ASIA_CHOICES = [
        (tz, tz)
        for tz in sorted(
            [
                "Asia/Dubai",
                "Asia/Kabul",
                "Asia/Kolkata",
                "Asia/Dhaka",
                "Asia/Bangkok",
                "Asia/Singapore",
                "Asia/Hong_Kong",
                "Asia/Shanghai",
                "Asia/Tokyo",
                "Asia/Seoul",
                "Asia/Manila",
                "Asia/Jakarta",
                "Asia/Tehran",
                "Asia/Jerusalem",
                "Asia/Karachi",
            ]
        )
    ]

    ATLANTIC_CHOICES = [(tz, tz) for tz in sorted(["Atlantic/Azores", "Atlantic/Cape_Verde", "Atlantic/Reykjavik"])]

    AUSTRALIA_CHOICES = [
        (tz, tz)
        for tz in sorted(
            [
                "Australia/Perth",
                "Australia/Adelaide",
                "Australia/Darwin",
                "Australia/Brisbane",
                "Australia/Sydney",
                "Australia/Melbourne",
                "Australia/Hobart",
            ]
        )
    ]

    EUROPE_CHOICES = [
        (tz, tz)
        for tz in sorted(
            [
                "Europe/London",
                "Europe/Dublin",
                "Europe/Lisbon",
                "Europe/Paris",
                "Europe/Brussels",
                "Europe/Amsterdam",
                "Europe/Berlin",
                "Europe/Rome",
                "Europe/Madrid",
                "Europe/Zurich",
                "Europe/Vienna",
                "Europe/Prague",
                "Europe/Warsaw",
                "Europe/Budapest",
                "Europe/Athens",
                "Europe/Helsinki",
                "Europe/Stockholm",
                "Europe/Moscow",
                "Europe/Istanbul",
            ]
        )
    ]

    PACIFIC_CHOICES = [
        (tz, tz)
        for tz in sorted(
            [
                "Pacific/Auckland",
                "Pacific/Fiji",
                "Pacific/Honolulu",
                "Pacific/Guam",
                "Pacific/Port_Moresby",
            ]
        )
    ]

    CHOICES = [
        ("Common", COMMON_CHOICES),
        ("Africa", AFRICA_CHOICES),
        ("America", AMERICA_CHOICES),
        ("Asia", ASIA_CHOICES),
        ("Atlantic", ATLANTIC_CHOICES),
        ("Australia", AUSTRALIA_CHOICES),
        ("Europe", EUROPE_CHOICES),
        ("Pacific", PACIFIC_CHOICES),
    ]


class MaintenanceTypeChoices(ChoiceSet):
    """Valid maintenance status choices from BCOP standard"""

    key = "DocTypeChoices.Maintenance"

    CHOICES = [
        ("TENTATIVE", "Tentative", "yellow"),
        ("CONFIRMED", "Confirmed", "green"),
        ("CANCELLED", "Cancelled", "blue"),
        ("IN-PROCESS", "In-Progress", "orange"),
        ("COMPLETED", "Completed", "indigo"),
        ("RE-SCHEDULED", "Rescheduled", "green"),
        ("UNKNOWN", "Unknown", "blue"),
    ]


class ImpactTypeChoices(ChoiceSet):
    """Valid impact level choices from BCOP standard"""

    key = "DocTypeChoices.Impact"

    CHOICES = [
        ("NO-IMPACT", "No-Impact", "green"),
        ("REDUCED-REDUNDANCY", "Reduced Redundancy", "yellow"),
        ("DEGRADED", "Degraded", "orange"),
        ("OUTAGE", "Outage", "red"),
    ]


class OutageStatusChoices(ChoiceSet):
    """Status choices for unplanned outage events"""

    key = "Outage.Status"

    CHOICES = [
        ("REPORTED", "Reported", "red"),
        ("INVESTIGATING", "Investigating", "orange"),
        ("IDENTIFIED", "Identified", "yellow"),
        ("MONITORING", "Monitoring", "blue"),
        ("RESOLVED", "Resolved", "green"),
    ]


class BaseEvent(NetBoxModel):
    """
    Abstract base class for maintenance and outage events.
    Provides common fields and relationships shared by both event types.
    """

    name = models.CharField(
        max_length=100,
        verbose_name="Event ID",
        help_text="Provider supplied event ID or ticket number",
    )

    summary = models.CharField(max_length=200, help_text="Brief summary of the event")

    provider = models.ForeignKey(
        to="circuits.provider",
        on_delete=models.CASCADE,
        related_name="%(class)s_events",  # Dynamic related name per subclass
    )

    start = models.DateTimeField(help_text="Start date and time of the event")

    original_timezone = models.CharField(
        max_length=63,
        blank=True,
        verbose_name="Original Timezone",
        help_text="Original timezone from provider notification",
    )

    internal_ticket = models.CharField(
        max_length=100,
        verbose_name="Internal Ticket #",
        help_text="Internal ticket or change reference",
        blank=True,
    )

    acknowledged = models.BooleanField(
        default=False,
        null=True,
        blank=True,
        verbose_name="Acknowledged?",
        help_text="Confirm if this event has been acknowledged",
    )

    comments = models.TextField(blank=True)

    class Meta:
        abstract = True
        ordering = ("-created",)


class Maintenance(BaseEvent):
    """
    Planned maintenance events with scheduled end times.
    Inherits common fields from BaseEvent.
    """

    # Override provider to preserve backward compatibility with related_name
    provider = models.ForeignKey(
        to="circuits.provider",
        on_delete=models.CASCADE,
        related_name="maintenance",
        default=None,
    )

    end = models.DateTimeField(help_text="End date and time of the maintenance event")

    status = models.CharField(max_length=30, choices=MaintenanceTypeChoices)

    # Reverse relation for GenericForeignKey in Impact model
    impacts = GenericRelation(
        to="vendor_notification.Impact",
        content_type_field="event_content_type",
        object_id_field="event_object_id",
        related_query_name="maintenance",
    )

    class Meta:
        ordering = ("-created",)
        verbose_name = "Maintenance"
        verbose_name_plural = "Maintenances"

    def __str__(self):
        return self.name

    def get_status_color(self):
        return MaintenanceTypeChoices.colors.get(self.status)

    def get_start_in_original_tz(self):
        """Get start time in original timezone if specified"""
        if self.original_timezone and self.start:
            try:
                tz = zoneinfo.ZoneInfo(self.original_timezone)
                return self.start.astimezone(tz)
            except (zoneinfo.ZoneInfoNotFoundError, ValueError):
                return self.start
        return self.start

    def get_end_in_original_tz(self):
        """Get end time in original timezone if specified"""
        if self.original_timezone and self.end:
            try:
                tz = zoneinfo.ZoneInfo(self.original_timezone)
                return self.end.astimezone(tz)
            except (zoneinfo.ZoneInfoNotFoundError, ValueError):
                return self.end
        return self.end

    def has_timezone_difference(self):
        """Check if original timezone differs from current timezone"""
        if not self.original_timezone:
            return False
        try:
            original_tz = zoneinfo.ZoneInfo(self.original_timezone)
            current_tz = timezone.get_current_timezone()
            # Compare timezone names - if they're different, we should show both
            return str(original_tz) != str(current_tz)
        except (zoneinfo.ZoneInfoNotFoundError, ValueError):
            return False

    def get_absolute_url(self):
        return reverse("plugins:vendor_notification:maintenance", args=[self.pk])


class Outage(BaseEvent):
    """
    Unplanned outage events with optional end times and ETR tracking.
    Inherits common fields from BaseEvent.
    """

    end = models.DateTimeField(
        null=True,
        blank=True,
        help_text="End date and time of the outage (required when resolved)",
    )

    estimated_time_to_repair = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Estimated Time to Repair",
        help_text="Current estimate for when service will be restored",
    )

    status = models.CharField(max_length=30, choices=OutageStatusChoices)

    # Reverse relation for GenericForeignKey in Impact model
    impacts = GenericRelation(
        to="vendor_notification.Impact",
        content_type_field="event_content_type",
        object_id_field="event_object_id",
        related_query_name="outage",
    )

    class Meta:
        verbose_name = "Outage"
        verbose_name_plural = "Outages"
        ordering = ("-created",)

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        # Validation: end time required when status = RESOLVED
        if self.status == "RESOLVED" and not self.end:
            raise ValidationError({"end": "End time is required when marking outage as resolved"})

    def get_status_color(self):
        return OutageStatusChoices.colors.get(self.status)

    def get_absolute_url(self):
        return reverse("plugins:vendor_notification:outage", args=[self.pk])


class Impact(NetBoxModel):
    """
    Links a maintenance or outage event to an affected NetBox object.
    Uses GenericForeignKey to support any configured object type.
    """

    # Link to event (Maintenance or Outage)
    event_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name="impacts_as_event",
        limit_choices_to=models.Q(app_label="vendor_notification", model__in=["maintenance", "outage"]),
    )
    event_object_id = models.PositiveIntegerField(db_index=True)
    event = GenericForeignKey("event_content_type", "event_object_id")

    # Link to target NetBox object (Circuit, Device, Site, etc.)
    target_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name="impacts_as_target")
    target_object_id = models.PositiveIntegerField(db_index=True)
    target = GenericForeignKey("target_content_type", "target_object_id")

    # Impact level
    impact = models.CharField(
        max_length=30,
        choices=ImpactTypeChoices,
        null=True,
        blank=True,
    )

    class Meta:
        unique_together = [("event_content_type", "event_object_id", "target_content_type", "target_object_id")]
        ordering = ("impact",)
        verbose_name = "Impact"
        verbose_name_plural = "Impacts"

    def __str__(self):
        event_name = str(self.event) if self.event else "Unknown"
        target_name = str(self.target) if self.target else "Unknown"
        return f"{event_name} - {target_name}"

    def get_absolute_url(self):
        # Link to the event detail page
        if self.event and hasattr(self.event, "get_absolute_url"):
            return self.event.get_absolute_url()
        return reverse("plugins:vendor_notification:impact", args=[self.pk])

    def get_impact_color(self):
        return ImpactTypeChoices.colors.get(self.impact)

    def clean(self):
        super().clean()
        from .utils import get_allowed_content_types

        allowed_types = get_allowed_content_types()

        # Validate target is an allowed type
        if self.target_content_type:
            app_label = self.target_content_type.app_label
            model = self.target_content_type.model
            type_string = f"{app_label}.{model}"

            # Case-insensitive comparison
            allowed_types_lower = [t.lower() for t in allowed_types]
            if type_string.lower() not in allowed_types_lower:
                raise ValidationError(
                    {
                        "target_content_type": f"Content type '{type_string}' is not allowed. "
                        f"Allowed types: {', '.join(allowed_types)}"
                    }
                )

        # Validate event is Maintenance or Outage
        if self.event_content_type:
            if self.event_content_type.app_label != "vendor_notification":
                raise ValidationError({"event_content_type": "Event must be a Maintenance or Outage"})
            if self.event_content_type.model not in ["maintenance", "outage"]:
                raise ValidationError({"event_content_type": "Event must be a Maintenance or Outage"})

        # Validate event status - cannot modify impacts on completed events
        if hasattr(self.event, "status"):
            if self.event.status in ["COMPLETED", "CANCELLED", "RESOLVED"]:
                raise ValidationError("You cannot alter an impact once the event has completed.")


class EventNotification(NetBoxModel):
    """
    Stores raw email notifications for maintenance or outage events.
    Uses GenericForeignKey to link to either event type.
    """

    # Link to event (Maintenance or Outage)
    event_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to=models.Q(app_label="vendor_notification", model__in=["maintenance", "outage"]),
    )
    event_object_id = models.PositiveIntegerField(db_index=True)
    event = GenericForeignKey("event_content_type", "event_object_id")

    email = models.BinaryField()
    email_body = models.TextField(verbose_name="Email Body")
    subject = models.CharField(max_length=100)
    email_from = models.EmailField(verbose_name="Email From")
    email_received = models.DateTimeField(verbose_name="Email Received")  # Fixed typo

    class Meta:
        ordering = ("email_received",)
        verbose_name = "Event Notification"
        verbose_name_plural = "Event Notifications"

    def __str__(self):
        return self.subject

    def get_absolute_url(self):
        return reverse("plugins:vendor_notification:eventnotification", args=[self.pk])
