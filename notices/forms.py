import zoneinfo

from circuits.models import Provider
from django import forms
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from netbox.forms import NetBoxModelFilterSetForm, NetBoxModelForm
from utilities.forms import get_field_value
from utilities.forms.rendering import FieldSet
from utilities.forms.fields import DynamicModelChoiceField
from utilities.forms.widgets import DateTimePicker, HTMXSelect

from .choices import MaintenanceTypeChoices, OutageStatusChoices, TimeZoneChoices
from .models import EventNotification, Impact, Maintenance, Outage
from .utils import get_allowed_content_types


class GenericForeignKeyFormMixin:
    """
    Mixin for forms with GenericForeignKey fields using HTMX pattern.

    Subclasses should declare:
        generic_fk_fields = [('field_prefix', 'content_type_field', 'object_id_field')]

    Example:
        generic_fk_fields = [('event', 'event_content_type', 'event_object_id')]

    This will:
    - Create 'event_choice' DynamicModelChoiceField when event_content_type is selected
    - Extract selected object from event_choice in clean()
    - Populate event_content_type and event_object_id for model save
    """

    # Override in subclasses with list of (prefix, content_type_field, object_id_field) tuples
    generic_fk_fields = []

    def init_generic_choice(self, field_prefix, content_type_id):
        """
        Initialize a choice field based on selected content type.
        Creates DynamicModelChoiceField for selecting actual objects.

        Args:
            field_prefix: Field name prefix (e.g., 'event', 'target')
            content_type_id: Primary key of selected ContentType (may be list from HTMX)
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

            # Get initial value if editing existing object
            object_id_field = f"{field_prefix}_object_id"
            object_id = get_field_value(self, object_id_field)

            # Handle list values from duplicate GET parameters
            if isinstance(object_id, list):
                object_id = object_id[0] if object_id else None

            if object_id:
                initial = model_class.objects.get(pk=object_id)

            # Create dynamic choice field with model-specific queryset
            choice_field_name = f"{field_prefix}_choice"
            self.fields[choice_field_name] = DynamicModelChoiceField(
                label=field_prefix.replace("_", " ").title(),
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

        # Process each registered GenericFK field
        for field_prefix, content_type_field, object_id_field in self.generic_fk_fields:
            choice_field_name = f"{field_prefix}_choice"
            choice_object = self.cleaned_data.get(choice_field_name)

            if choice_object:
                # Populate GenericForeignKey fields
                self.cleaned_data[content_type_field] = (
                    ContentType.objects.get_for_model(choice_object)
                )
                self.cleaned_data[object_id_field] = choice_object.id

        return self.cleaned_data


class MaintenanceForm(NetBoxModelForm):
    provider = DynamicModelChoiceField(queryset=Provider.objects.all())

    replaces = DynamicModelChoiceField(
        queryset=Maintenance.objects.all(),
        required=False,
        label="Replaces",
        help_text="The maintenance this event replaces (for rescheduled events)",
    )

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
            "impact",
            "comments",
            "replaces",
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


class ImpactForm(GenericForeignKeyFormMixin, NetBoxModelForm):
    """
    Form for creating/editing Impact records with GenericForeignKey support.
    Handles both event (Maintenance/Outage) and target (Circuit/Device/etc.) relationships.
    Uses HTMX pattern from EventRuleForm for dynamic object selection.
    """

    # Register GenericFK fields with mixin
    generic_fk_fields = [
        ("event", "event_content_type", "event_object_id"),
        ("target", "target_content_type", "target_object_id"),
    ]

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
            app_label="notices", model__in=["maintenance", "outage"]
        )
        self.fields["event_content_type"].label = "Event Type"
        self.fields[
            "event_content_type"
        ].help_text = "Type of event (Maintenance or Outage)"

        # Customize auto-generated target_content_type field
        self.fields["target_content_type"].label = "Target Type"
        self.fields["target_content_type"].help_text = "Type of affected object"

        # Customize object_id fields (labels and help text)
        self.fields["event_object_id"].label = "Event"
        self.fields["event_object_id"].help_text = "Select a specific maintenance or outage event"
        self.fields["event_object_id"].required = False

        self.fields["target_object_id"].label = "Target Object"
        self.fields["target_object_id"].help_text = "Select the specific object affected by this event"
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
            self.init_generic_choice("event", event_ct_id)

        # Determine target content type from form state
        target_ct_id = get_field_value(self, "target_content_type")
        if target_ct_id:
            self.init_generic_choice("target", target_ct_id)

    def clean(self):
        """
        Extract ContentType and object ID from selected objects.
        Mixin handles the GenericFK field population.
        """
        return super().clean()


class EventNotificationForm(GenericForeignKeyFormMixin, NetBoxModelForm):
    """
    Form for creating/editing EventNotification records.
    Uses GenericForeignKeyFormMixin for HTMX-based event object picker.
    """

    # Register GenericFK field with mixin
    generic_fk_fields = [
        ("event", "event_content_type", "event_object_id"),
    ]

    fieldsets = (
        FieldSet("event_content_type", "event_choice", name="Event"),
        FieldSet("subject", "email_from", "email_received", name="Email Details"),
        FieldSet("email_body", name="Message"),
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
        widgets = {
            "event_content_type": HTMXSelect(),
            "event_object_id": forms.HiddenInput,
            "email_received": DateTimePicker(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Customize event_content_type field
        self.fields["event_content_type"].queryset = ContentType.objects.filter(
            app_label="notices", model__in=["maintenance", "outage"]
        )
        self.fields["event_content_type"].label = "Event Type"
        self.fields[
            "event_content_type"
        ].help_text = "Type of event (Maintenance or Outage)"

        # Make hidden object_id field not required
        self.fields["event_object_id"].required = False

        # Determine event content type from form state
        event_ct_id = get_field_value(self, "event_content_type")
        if event_ct_id:
            self.init_generic_choice("event", event_ct_id)


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
            "reported_at",
            "end",
            "estimated_time_to_repair",
            "original_timezone",
            "internal_ticket",
            "acknowledged",
            "impact",
            "comments",
            "tags",
        )
        widgets = {
            "start": DateTimePicker(),
            "reported_at": DateTimePicker(),
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

                # Convert reported_at time if provided
                if instance.reported_at:
                    if timezone.is_naive(instance.reported_at):
                        reported_at_in_original_tz = instance.reported_at.replace(
                            tzinfo=original_tz
                        )
                    else:
                        reported_at_in_original_tz = instance.reported_at.replace(
                            tzinfo=original_tz
                        )
                    instance.reported_at = reported_at_in_original_tz.astimezone(system_tz)

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
