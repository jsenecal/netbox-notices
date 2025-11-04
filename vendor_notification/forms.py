import zoneinfo

from circuits.models import Provider
from django import forms
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from netbox.forms import NetBoxModelFilterSetForm, NetBoxModelForm
from utilities.forms import get_field_value
from utilities.forms.rendering import FieldSet
from utilities.forms.fields import ContentTypeChoiceField, DynamicModelChoiceField
from utilities.forms.widgets import DateTimePicker, HTMXSelect

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
            self.fields[
                "original_timezone"
            ].help_text = (
                "Original timezone from provider notification (reference only)"
            )
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
                        start_in_original_tz = instance.start.replace(
                            tzinfo=original_tz
                        )
                    else:
                        # If already aware, interpret it as being in the original timezone
                        start_in_original_tz = instance.start.replace(
                            tzinfo=original_tz
                        )
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

    provider = forms.ModelMultipleChoiceField(
        queryset=Provider.objects.all(), required=False
    )

    status = forms.MultipleChoiceField(choices=MaintenanceTypeChoices, required=False)

    start = forms.CharField(required=False)

    end = forms.CharField(required=False)

    acknowledged = forms.BooleanField(required=False)

    internal_ticket = forms.CharField(required=False)


class ImpactForm(NetBoxModelForm):
    """
    Form for creating/editing Impact records with GenericForeignKey support.
    Handles both event (Maintenance/Outage) and target (Circuit/Device/etc.) relationships.
    Uses HTMX pattern from EventRuleForm for dynamic object selection.
    """

    # Dynamic choice fields - created in __init__ based on content type selection
    event_choice = None
    target_choice = None

    fieldsets = (
        FieldSet("event_content_type", "event_choice", name="Event"),
        FieldSet("target_content_type", "target_choice", name="Target"),
        FieldSet("impact", "tags", name="Impact Details"),
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
        widgets = {
            "event_content_type": HTMXSelect(),
            "target_content_type": HTMXSelect(),
            "event_object_id": forms.HiddenInput,
            "target_object_id": forms.HiddenInput,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Customize auto-generated event_content_type field
        self.fields["event_content_type"].queryset = ContentType.objects.filter(
            app_label="vendor_notification", model__in=["maintenance", "outage"]
        )
        self.fields["event_content_type"].label = "Event Type"
        self.fields[
            "event_content_type"
        ].help_text = "Type of event (Maintenance or Outage)"

        # Customize auto-generated target_content_type field
        self.fields["target_content_type"].label = "Target Type"
        self.fields["target_content_type"].help_text = "Type of affected object"

        # Make hidden object_id fields not required
        self.fields["event_object_id"].required = False
        self.fields["target_object_id"].required = False

        # Get allowed content types for targets from plugin configuration
        allowed_types = get_allowed_content_types()
        target_content_types = []
        for type_string in allowed_types:
            try:
                app_label, model = type_string.lower().split(".")
                ct = ContentType.objects.filter(
                    app_label=app_label, model=model
                ).first()
                if ct:
                    target_content_types.append(ct.pk)
            except (ValueError, AttributeError):
                # Skip invalid format
                continue

        # Update target_content_type queryset based on allowed types
        self.fields["target_content_type"].queryset = ContentType.objects.filter(
            pk__in=target_content_types
        )

        # Determine event content type from form state (instance, initial, or GET/POST)
        event_ct_id = get_field_value(self, "event_content_type")
        if event_ct_id:
            self.init_event_choice(event_ct_id)

        # Determine target content type from form state
        target_ct_id = get_field_value(self, "target_content_type")
        if target_ct_id:
            self.init_target_choice(target_ct_id)

    def init_event_choice(self, content_type_id):
        """
        Initialize event choice field based on selected content type.
        Creates DynamicModelChoiceField with appropriate queryset.

        Args:
            content_type_id: Primary key of selected ContentType (may be list from duplicate params)
        """
        # Handle list values from duplicate GET parameters (HTMX includes all fields)
        if isinstance(content_type_id, list):
            content_type_id = content_type_id[0] if content_type_id else None

        if not content_type_id:
            return

        initial = None
        try:
            content_type = ContentType.objects.get(pk=content_type_id)
            model_class = content_type.model_class()

            # Get initial value if editing existing Impact
            event_id = get_field_value(self, "event_object_id")

            # Handle list values from duplicate GET parameters
            if isinstance(event_id, list):
                event_id = event_id[0] if event_id else None

            if event_id:
                initial = model_class.objects.get(pk=event_id)

            # Create dynamic choice field with model-specific queryset
            self.fields["event_choice"] = DynamicModelChoiceField(
                label="Event",
                queryset=model_class.objects.all(),
                required=True,
                initial=initial,
            )
        except (ContentType.DoesNotExist, ObjectDoesNotExist):
            # Invalid content type or object - form validation will catch this
            pass

    def init_target_choice(self, content_type_id):
        """
        Initialize target choice field based on selected content type.
        Creates DynamicModelChoiceField with appropriate queryset.

        Args:
            content_type_id: Primary key of selected ContentType (may be list from duplicate params)
        """
        # Handle list values from duplicate GET parameters (HTMX includes all fields)
        if isinstance(content_type_id, list):
            content_type_id = content_type_id[0] if content_type_id else None

        if not content_type_id:
            return

        initial = None
        try:
            content_type = ContentType.objects.get(pk=content_type_id)
            model_class = content_type.model_class()

            # Get initial value if editing existing Impact
            target_id = get_field_value(self, "target_object_id")

            # Handle list values from duplicate GET parameters
            if isinstance(target_id, list):
                target_id = target_id[0] if target_id else None

            if target_id:
                initial = model_class.objects.get(pk=target_id)

            # Create dynamic choice field with model-specific queryset
            self.fields["target_choice"] = DynamicModelChoiceField(
                label="Target Object",
                queryset=model_class.objects.all(),
                required=True,
                initial=initial,
            )
        except (ContentType.DoesNotExist, ObjectDoesNotExist):
            # Invalid content type or object - form validation will catch this
            pass

    def clean(self):
        """
        Extract ContentType and object ID from selected objects.
        Populates hidden GenericForeignKey fields for model persistence.
        """
        super().clean()

        # Extract event object and populate GenericForeignKey fields
        event_choice = self.cleaned_data.get("event_choice")
        if event_choice:
            self.cleaned_data["event_content_type"] = ContentType.objects.get_for_model(
                event_choice
            )
            self.cleaned_data["event_object_id"] = event_choice.id

        # Extract target object and populate GenericForeignKey fields
        target_choice = self.cleaned_data.get("target_choice")
        if target_choice:
            self.cleaned_data["target_content_type"] = (
                ContentType.objects.get_for_model(target_choice)
            )
            self.cleaned_data["target_object_id"] = target_choice.id

        return self.cleaned_data


class EventNotificationForm(NetBoxModelForm):
    """
    Form for creating/editing EventNotification records.
    """

    event_content_type = ContentTypeChoiceField(
        label="Event Type",
        queryset=ContentType.objects.filter(
            app_label="vendor_notification", model__in=["maintenance", "outage"]
        ),
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
        self.fields[
            "event_object_id"
        ].help_text = "ID of the maintenance or outage event"


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
            self.fields[
                "original_timezone"
            ].help_text = (
                "Original timezone from provider notification (reference only)"
            )
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
                        start_in_original_tz = instance.start.replace(
                            tzinfo=original_tz
                        )
                    else:
                        start_in_original_tz = instance.start.replace(
                            tzinfo=original_tz
                        )
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
                        etr_in_original_tz = instance.estimated_time_to_repair.replace(
                            tzinfo=original_tz
                        )
                    else:
                        etr_in_original_tz = instance.estimated_time_to_repair.replace(
                            tzinfo=original_tz
                        )
                    instance.estimated_time_to_repair = etr_in_original_tz.astimezone(
                        system_tz
                    )

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
    provider = forms.ModelMultipleChoiceField(
        queryset=Provider.objects.all(), required=False
    )
    status = forms.MultipleChoiceField(choices=OutageStatusChoices, required=False)
    start = forms.CharField(required=False)
    end = forms.CharField(required=False)
    acknowledged = forms.BooleanField(required=False)
    internal_ticket = forms.CharField(required=False)
