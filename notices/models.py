import zoneinfo

from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone
from netbox.models import NetBoxModel

from .choices import ImpactTypeChoices, MaintenanceTypeChoices, OutageStatusChoices


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

    impact = models.TextField(
        blank=True,
        help_text="Description of the impact of this event"
    )

    clone_fields = [
        "name",
        "summary",
        "provider",
        "start",
        "end",
        "original_timezone",
        "internal_ticket",
        "impact",
        "comments",
    ]

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
        to="notices.Impact",
        content_type_field="event_content_type",
        object_id_field="event_object_id",
        related_query_name="maintenance",
    )

    # Self-referencing FK for rescheduled maintenance tracking
    replaces = models.ForeignKey(
        to="self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replaced_by_maintenance",
        verbose_name="Replaces Maintenance",
        help_text="The maintenance event that this event replaces (for rescheduled events)",
    )

    class Meta:
        ordering = ("-created",)
        verbose_name = "Maintenance"
        verbose_name_plural = "Maintenances"

    def __str__(self):
        return str(self.name)

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
        return reverse("plugins:notices:maintenance", args=[self.pk])


class Outage(BaseEvent):
    """
    Unplanned outage events with optional end times and ETR tracking.
    Inherits common fields from BaseEvent.
    """

    # Override start field to default to now() for outages
    start = models.DateTimeField(
        default=timezone.now,
        help_text="Start date and time of the outage"
    )

    reported_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="Reported At",
        help_text="Date and time when this outage was reported"
    )

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
        to="notices.Impact",
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
            raise ValidationError(
                {"end": "End time is required when marking outage as resolved"}
            )

    def get_status_color(self):
        return OutageStatusChoices.colors.get(self.status)

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

    def get_estimated_time_to_repair_in_original_tz(self):
        """Get ETR in original timezone if specified"""
        if self.original_timezone and self.estimated_time_to_repair:
            try:
                tz = zoneinfo.ZoneInfo(self.original_timezone)
                return self.estimated_time_to_repair.astimezone(tz)
            except (zoneinfo.ZoneInfoNotFoundError, ValueError):
                return self.estimated_time_to_repair
        return self.estimated_time_to_repair

    def get_reported_at_in_original_tz(self):
        """Get reported_at time in original timezone if specified"""
        if self.original_timezone and self.reported_at:
            try:
                tz = zoneinfo.ZoneInfo(self.original_timezone)
                return self.reported_at.astimezone(tz)
            except (zoneinfo.ZoneInfoNotFoundError, ValueError):
                return self.reported_at
        return self.reported_at

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
        return reverse("plugins:notices:outage", args=[self.pk])


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
        limit_choices_to=models.Q(
            app_label="notices", model__in=["maintenance", "outage"]
        ),
    )
    event_object_id = models.PositiveIntegerField(db_index=True)
    event = GenericForeignKey("event_content_type", "event_object_id")

    # Link to target NetBox object (Circuit, Device, Site, etc.)
    target_content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, related_name="impacts_as_target"
    )
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
        unique_together = [
            (
                "event_content_type",
                "event_object_id",
                "target_content_type",
                "target_object_id",
            )
        ]
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
        return reverse("plugins:notices:impact", args=[self.pk])

    def get_impact_color(self):
        return ImpactTypeChoices.colors.get(self.impact)

    def to_objectchange(self, action):
        """
        Return a new ObjectChange with the related_object set to the parent event.
        This ensures that changes to impacts appear in the event's changelog.
        """
        objectchange = super().to_objectchange(action)
        objectchange.related_object = self.event
        return objectchange

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
            if self.event_content_type.app_label != "notices":
                raise ValidationError(
                    {"event_content_type": "Event must be a Maintenance or Outage"}
                )
            if self.event_content_type.model not in ["maintenance", "outage"]:
                raise ValidationError(
                    {"event_content_type": "Event must be a Maintenance or Outage"}
                )

        # Validate event status - cannot modify impacts on completed events
        if hasattr(self.event, "status"):
            if self.event.status in ["COMPLETED", "CANCELLED", "RESOLVED"]:
                raise ValidationError(
                    "You cannot alter an impact once the event has completed."
                )


class EventNotification(NetBoxModel):
    """
    Stores raw email notifications for maintenance or outage events.
    Uses GenericForeignKey to link to either event type.
    """

    # Link to event (Maintenance or Outage)
    event_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to=models.Q(
            app_label="notices", model__in=["maintenance", "outage"]
        ),
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
        return reverse("plugins:notices:eventnotification", args=[self.pk])

    def to_objectchange(self, action):
        """
        Return a new ObjectChange with the related_object set to the parent event.
        This ensures that changes to notifications appear in the event's changelog.
        """
        objectchange = super().to_objectchange(action)
        objectchange.related_object = self.event
        return objectchange
