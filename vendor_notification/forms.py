import zoneinfo

from circuits.models import Provider
from django import forms
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from netbox.forms import NetBoxModelFilterSetForm, NetBoxModelForm
from utilities.forms.fields import ContentTypeChoiceField, DynamicModelChoiceField
from utilities.forms.widgets import DateTimePicker

from .models import (
    EventNotification,
    Impact,
    Maintenance,
    MaintenanceTypeChoices,
    Outage,
    OutageStatusChoices,
    TimeZoneChoices,
)
from .utils import get_allowed_content_types


class MaintenanceForm(NetBoxModelForm):
    provider = DynamicModelChoiceField(queryset=Provider.objects.all())

    original_timezone = forms.ChoiceField(
        choices=TimeZoneChoices,
        required=False,
        label="Timezone",
        help_text="Timezone for the start/end times (converted to system timezone on save)",
    )

    class Meta:
        model = Maintenance
        fields = (
            "name",
            "summary",
            "status",
            "provider",
            "start",
            "end",
            "original_timezone",
            "internal_ticket",
            "acknowledged",
            "comments",
            "tags",
        )
        widgets = {"start": DateTimePicker(), "end": DateTimePicker()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # On edit, change help text since we don't convert
        if self.instance and self.instance.pk:
            self.fields["original_timezone"].help_text = "Original timezone from provider notification (reference only)"
            self.fields["original_timezone"].label = "Original Timezone"

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Only convert timezone on CREATE (not on edit)
        if not instance.pk and instance.original_timezone:
            try:
                # Get the timezone objects
                original_tz = zoneinfo.ZoneInfo(instance.original_timezone)
                system_tz = timezone.get_current_timezone()

                # Convert start time if provided
                if instance.start:
                    # Make the datetime aware in the original timezone if it's naive
                    if timezone.is_naive(instance.start):
                        start_in_original_tz = instance.start.replace(tzinfo=original_tz)
                    else:
                        # If already aware, interpret it as being in the original timezone
                        start_in_original_tz = instance.start.replace(tzinfo=original_tz)
                    # Convert to system timezone
                    instance.start = start_in_original_tz.astimezone(system_tz)

                # Convert end time if provided
                if instance.end:
                    if timezone.is_naive(instance.end):
                        end_in_original_tz = instance.end.replace(tzinfo=original_tz)
                    else:
                        end_in_original_tz = instance.end.replace(tzinfo=original_tz)
                    instance.end = end_in_original_tz.astimezone(system_tz)

            except (zoneinfo.ZoneInfoNotFoundError, ValueError):
                # If timezone is invalid, just save without conversion
                pass

        if commit:
            instance.save()
            self.save_m2m()

        return instance


class MaintenanceFilterForm(NetBoxModelFilterSetForm):
    model = Maintenance

    name = forms.CharField(required=False)

    summary = forms.CharField(required=False)

    provider = forms.ModelMultipleChoiceField(queryset=Provider.objects.all(), required=False)

    status = forms.MultipleChoiceField(choices=MaintenanceTypeChoices, required=False)

    start = forms.CharField(required=False)

    end = forms.CharField(required=False)

    acknowledged = forms.BooleanField(required=False)

    internal_ticket = forms.CharField(required=False)


class ImpactForm(NetBoxModelForm):
    """
    Form for creating/editing Impact records with GenericForeignKey support.
    Handles both event (Maintenance/Outage) and target (Circuit/Device/etc.) relationships.
    """

    event_content_type = ContentTypeChoiceField(
        label="Event Type",
        queryset=ContentType.objects.filter(app_label="vendor_notification", model__in=["maintenance", "outage"]),
        help_text="Type of event (Maintenance or Outage)",
    )

    target_content_type = ContentTypeChoiceField(
        label="Target Type",
        queryset=ContentType.objects.none(),  # Will be set in __init__
        help_text="Type of affected object",
    )

    class Meta:
        model = Impact
        fields = (
            "event_content_type",
            "event_object_id",
            "target_content_type",
            "target_object_id",
            "impact",
            "tags",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Get allowed content types from plugin configuration
        allowed_types = get_allowed_content_types()

        # Build queryset for target_content_type based on allowed types
        # Parse "app_label.model" format
        target_content_types = []
        for type_string in allowed_types:
            try:
                app_label, model = type_string.lower().split(".")
                ct = ContentType.objects.filter(app_label=app_label, model=model).first()
                if ct:
                    target_content_types.append(ct.pk)
            except (ValueError, AttributeError):
                # Skip invalid format
                continue

        # Update the queryset
        self.fields["target_content_type"].queryset = ContentType.objects.filter(pk__in=target_content_types)

        # Update field labels for clarity
        self.fields["event_object_id"].label = "Event"
        self.fields["event_object_id"].help_text = "ID of the maintenance or outage event"
        self.fields["target_object_id"].label = "Target Object"
        self.fields["target_object_id"].help_text = "ID of the affected object"


class EventNotificationForm(NetBoxModelForm):
    """
    Form for creating/editing EventNotification records.
    """

    event_content_type = ContentTypeChoiceField(
        label="Event Type",
        queryset=ContentType.objects.filter(app_label="vendor_notification", model__in=["maintenance", "outage"]),
        help_text="Type of event (Maintenance or Outage)",
    )

    class Meta:
        model = EventNotification
        fields = (
            "event_content_type",
            "event_object_id",
            "subject",
            "email_from",
            "email_body",
            "email_received",
        )
        widgets = {"email_received": DateTimePicker()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["event_object_id"].label = "Event"
        self.fields["event_object_id"].help_text = "ID of the maintenance or outage event"


class OutageForm(NetBoxModelForm):
    provider = DynamicModelChoiceField(queryset=Provider.objects.all())

    original_timezone = forms.ChoiceField(
        choices=TimeZoneChoices,
        required=False,
        label="Timezone",
        help_text="Timezone for the start/end/ETR times (converted to system timezone on save)",
    )

    class Meta:
        model = Outage
        fields = (
            "name",
            "summary",
            "status",
            "provider",
            "start",
            "end",
            "estimated_time_to_repair",
            "original_timezone",
            "internal_ticket",
            "acknowledged",
            "comments",
            "tags",
        )
        widgets = {
            "start": DateTimePicker(),
            "end": DateTimePicker(),
            "estimated_time_to_repair": DateTimePicker(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # On edit, change help text since we don't convert
        if self.instance and self.instance.pk:
            self.fields["original_timezone"].help_text = "Original timezone from provider notification (reference only)"
            self.fields["original_timezone"].label = "Original Timezone"

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Only convert timezone on CREATE (not on edit)
        if not instance.pk and instance.original_timezone:
            try:
                # Get the timezone objects
                original_tz = zoneinfo.ZoneInfo(instance.original_timezone)
                system_tz = timezone.get_current_timezone()

                # Convert start time if provided
                if instance.start:
                    if timezone.is_naive(instance.start):
                        start_in_original_tz = instance.start.replace(tzinfo=original_tz)
                    else:
                        start_in_original_tz = instance.start.replace(tzinfo=original_tz)
                    instance.start = start_in_original_tz.astimezone(system_tz)

                # Convert end time if provided
                if instance.end:
                    if timezone.is_naive(instance.end):
                        end_in_original_tz = instance.end.replace(tzinfo=original_tz)
                    else:
                        end_in_original_tz = instance.end.replace(tzinfo=original_tz)
                    instance.end = end_in_original_tz.astimezone(system_tz)

                # Convert ETR time if provided
                if instance.estimated_time_to_repair:
                    if timezone.is_naive(instance.estimated_time_to_repair):
                        etr_in_original_tz = instance.estimated_time_to_repair.replace(tzinfo=original_tz)
                    else:
                        etr_in_original_tz = instance.estimated_time_to_repair.replace(tzinfo=original_tz)
                    instance.estimated_time_to_repair = etr_in_original_tz.astimezone(system_tz)

            except (zoneinfo.ZoneInfoNotFoundError, ValueError):
                # If timezone is invalid, just save without conversion
                pass

        if commit:
            instance.save()
            self.save_m2m()

        return instance


class OutageFilterForm(NetBoxModelFilterSetForm):
    model = Outage

    name = forms.CharField(required=False)
    summary = forms.CharField(required=False)
    provider = forms.ModelMultipleChoiceField(queryset=Provider.objects.all(), required=False)
    status = forms.MultipleChoiceField(choices=OutageStatusChoices, required=False)
    start = forms.CharField(required=False)
    end = forms.CharField(required=False)
    acknowledged = forms.BooleanField(required=False)
    internal_ticket = forms.CharField(required=False)
