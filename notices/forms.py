import zoneinfo

from circuits.models import Provider
from django import forms
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from netbox.forms import NetBoxModelBulkEditForm, NetBoxModelFilterSetForm, NetBoxModelForm, NetBoxModelImportForm
from tenancy.models import ContactRole
from utilities.forms import add_blank_choice, get_field_value
from utilities.forms.fields import (
    CSVChoiceField,
    CSVModelChoiceField,
    DynamicModelChoiceField,
    DynamicModelMultipleChoiceField,
    SlugField,
    TagFilterField,
)
from utilities.forms.rendering import FieldSet
from utilities.forms.widgets import BulkEditNullBooleanSelect, DateTimePicker, HTMXSelect

from .choices import (
    BodyFormatChoices,
    MaintenanceTypeChoices,
    MessageEventTypeChoices,
    MessageGranularityChoices,
    OutageStatusChoices,
    PreparedNotificationStatusChoices,
    TimeZoneChoices,
)
from .models import (
    EventNotification,
    Impact,
    Maintenance,
    NotificationTemplate,
    Outage,
    PreparedNotification,
    SentNotification,
    TemplateScope,
)
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
                self.cleaned_data[content_type_field] = ContentType.objects.get_for_model(choice_object)
                self.cleaned_data[object_id_field] = choice_object.id

        return self.cleaned_data


class MaintenanceForm(NetBoxModelForm):
    provider = DynamicModelChoiceField(
        queryset=Provider.objects.all(),
        quick_add=True,
    )

    replaces = DynamicModelChoiceField(
        queryset=Maintenance.objects.all(),
        required=False,
        label="Replaces",
        help_text="The maintenance this event replaces (for rescheduled events)",
        selector=True,
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

    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("status", "provider_id", "acknowledged", name="Attributes"),
    )
    selector_fields = ("filter_id", "q", "provider_id", "status")

    status = forms.MultipleChoiceField(
        choices=MaintenanceTypeChoices,
        required=False,
    )
    provider_id = DynamicModelMultipleChoiceField(
        queryset=Provider.objects.all(),
        required=False,
        label="Provider",
    )
    acknowledged = forms.NullBooleanField(
        required=False,
        widget=forms.Select(
            choices=[
                ("", "---------"),
                (True, "Yes"),
                (False, "No"),
            ]
        ),
    )
    tag = TagFilterField(model)


class BaseEventBulkEditForm(NetBoxModelBulkEditForm):
    """Bulk-editable fields shared by Maintenance and Outage; add shared fields here, not to the
    subclasses. Every field mirrors the abstract `BaseEvent` model.

    Excluded: `status` (reason differs per model -- see each subclass) and the scheduling fields
    (`MaintenanceRescheduleView` owns Maintenance's; a bulk change across unrelated outages is
    judged more likely a mistake). Included: `acknowledged` -- `MaintenanceAcknowledgeView` only
    sets the flag and enforces nothing, unlike the views that write `status`.
    """

    provider = DynamicModelChoiceField(
        queryset=Provider.objects.all(),
        required=False,
    )
    acknowledged = forms.NullBooleanField(
        required=False,
        widget=BulkEditNullBooleanSelect(),
        label="Acknowledged?",
    )
    original_timezone = forms.ChoiceField(
        choices=add_blank_choice(TimeZoneChoices),
        required=False,
        label="Original Timezone",
    )
    internal_ticket = forms.CharField(
        max_length=100,
        required=False,
        label="Internal Ticket #",
    )
    impact = forms.CharField(
        required=False,
        widget=forms.Textarea,
    )
    comments = forms.CharField(
        required=False,
        widget=forms.Textarea,
    )

    nullable_fields = ("internal_ticket", "original_timezone", "impact", "comments")


class MaintenanceBulkEditForm(BaseEventBulkEditForm):
    """Do not add `status`, `start` or `end`.

    `status` belongs to the cancel / mark-in-progress / mark-completed views, which refuse to
    move a maintenance out of a terminal state; `start` and `end` to `MaintenanceRescheduleView`.
    A bulk `setattr` bypasses both.
    """

    model = Maintenance


class MaintenanceImportForm(NetBoxModelImportForm):
    """CSV/JSON/YAML import for Maintenance. Row validation stays on the model -- do not
    duplicate `BaseEvent.clean()` here.
    """

    provider = CSVModelChoiceField(
        queryset=Provider.objects.all(),
        to_field_name="name",
        help_text="Provider name",
    )
    status = CSVChoiceField(
        choices=MaintenanceTypeChoices,
        help_text="Maintenance status",
    )
    original_timezone = CSVChoiceField(
        choices=TimeZoneChoices,
        required=False,
        help_text="Original timezone from provider notification",
    )

    class Meta:
        model = Maintenance
        fields = (
            "name",
            "summary",
            "provider",
            "status",
            "start",
            "end",
            "original_timezone",
            "internal_ticket",
            "acknowledged",
            "impact",
            "comments",
        )


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
        self.fields["event_content_type"].help_text = "Type of event (Maintenance or Outage)"

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
                ct = ContentType.objects.filter(app_label=app_label, model=model).first()
                if ct:
                    target_content_types.append(ct.pk)
            except (ValueError, AttributeError):
                # Skip invalid format
                continue

        # Update target_content_type queryset based on allowed types
        self.fields["target_content_type"].queryset = ContentType.objects.filter(pk__in=target_content_types)

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
        self.fields["event_content_type"].help_text = "Type of event (Maintenance or Outage)"

        # Make hidden object_id field not required
        self.fields["event_object_id"].required = False

        # Determine event content type from form state
        event_ct_id = get_field_value(self, "event_content_type")
        if event_ct_id:
            self.init_generic_choice("event", event_ct_id)


class EventNotificationFilterForm(NetBoxModelFilterSetForm):
    """Filter form for EventNotification list view."""

    model = EventNotification

    fieldsets = (
        FieldSet("q", "filter_id"),
        FieldSet("subject", "email_from", name="Email"),
    )
    selector_fields = ("filter_id", "q")

    subject = forms.CharField(required=False)
    email_from = forms.CharField(required=False, label="From")


class OutageForm(NetBoxModelForm):
    provider = DynamicModelChoiceField(
        queryset=Provider.objects.all(),
        quick_add=True,
    )

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

                # Convert reported_at time if provided
                if instance.reported_at:
                    if timezone.is_naive(instance.reported_at):
                        reported_at_in_original_tz = instance.reported_at.replace(tzinfo=original_tz)
                    else:
                        reported_at_in_original_tz = instance.reported_at.replace(tzinfo=original_tz)
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

    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("status", "provider_id", "acknowledged", name="Attributes"),
    )
    selector_fields = ("filter_id", "q", "provider_id", "status")

    status = forms.MultipleChoiceField(
        choices=OutageStatusChoices,
        required=False,
    )
    provider_id = DynamicModelMultipleChoiceField(
        queryset=Provider.objects.all(),
        required=False,
        label="Provider",
    )
    acknowledged = forms.NullBooleanField(
        required=False,
        widget=forms.Select(
            choices=[
                ("", "---------"),
                (True, "Yes"),
                (False, "No"),
            ]
        ),
    )
    tag = TagFilterField(model)


class OutageBulkEditForm(BaseEventBulkEditForm):
    """Do not add `status`: `Outage.clean()` requires an `end` when RESOLVED, so a bulk status
    change would succeed on some selected rows and fail on others.
    """

    model = Outage


class OutageImportForm(NetBoxModelImportForm):
    """CSV/JSON/YAML import for Outage. Row validation stays on the model -- do not duplicate
    `Outage.clean()` here.
    """

    provider = CSVModelChoiceField(
        queryset=Provider.objects.all(),
        to_field_name="name",
        help_text="Provider name",
    )
    status = CSVChoiceField(
        choices=OutageStatusChoices,
        help_text="Outage status",
    )
    original_timezone = CSVChoiceField(
        choices=TimeZoneChoices,
        required=False,
        help_text="Original timezone from provider notification",
    )
    # Both fields default to timezone.now on the model but are not blank=True, so keep
    # required=False AND the clean_* methods -- each covers a CSV shape the other misses:
    #   column absent -> field is required, whole file rejected
    #   column empty  -> construct_instance writes None (a present-but-empty cell does not count
    #                    as "omitted"), full_clean() then excludes the field, and the row dies at
    #                    the database with an IntegrityError BulkImportView does not catch -- a
    #                    500 that rolls back every valid row in the file too
    # Maintenance needs neither: its start/end have no default, so requiring them is correct.
    start = forms.DateTimeField(
        required=False,
        help_text="When the outage began (default: import time)",
    )
    reported_at = forms.DateTimeField(
        required=False,
        help_text="When the outage was reported (default: import time)",
    )

    def _default_if_empty(self, field_name):
        """Return the submitted value, or the model field's own default when it is empty."""
        value = self.cleaned_data.get(field_name)
        if value:
            return value
        return self._meta.model._meta.get_field(field_name).get_default()

    def clean_start(self):
        return self._default_if_empty("start")

    def clean_reported_at(self):
        return self._default_if_empty("reported_at")

    class Meta:
        model = Outage
        fields = (
            "name",
            "summary",
            "provider",
            "status",
            "start",
            "end",
            "reported_at",
            "estimated_time_to_repair",
            "original_timezone",
            "internal_ticket",
            "acknowledged",
            "impact",
            "comments",
        )


# NotificationTemplate Forms
class NotificationTemplateForm(NetBoxModelForm):
    """Form for creating/editing NotificationTemplate records."""

    slug = SlugField(
        slug_source="name",
    )
    contact_roles = DynamicModelMultipleChoiceField(
        queryset=ContactRole.objects.all(),
        required=False,
    )
    extends = DynamicModelChoiceField(
        queryset=NotificationTemplate.objects.filter(is_base_template=True),
        required=False,
        label="Extends Template",
        help_text="Parent template to extend (for Jinja block inheritance).",
        selector=True,
    )

    fieldsets = (
        FieldSet("name", "slug", "description", "weight", name="Template"),
        FieldSet("event_type", "granularity", name="Targeting"),
        FieldSet(
            "subject_template",
            "body_template",
            "body_format",
            "css_template",
            "headers_template",
            name="Content",
        ),
        FieldSet("include_ical", "ical_template", name="iCal"),
        FieldSet("contact_roles", "contact_priorities", name="Recipients"),
        FieldSet("is_base_template", "extends", name="Inheritance"),
        FieldSet("tags", name="Tags"),
    )

    class Meta:
        model = NotificationTemplate
        fields = [
            "name",
            "slug",
            "description",
            "weight",
            "event_type",
            "granularity",
            "subject_template",
            "body_template",
            "body_format",
            "css_template",
            "headers_template",
            "include_ical",
            "ical_template",
            "contact_roles",
            "contact_priorities",
            "is_base_template",
            "extends",
            "tags",
        ]
        widgets = {
            "body_template": forms.Textarea(attrs={"rows": 10, "class": "font-monospace"}),
            "ical_template": forms.Textarea(attrs={"rows": 10, "class": "font-monospace"}),
            "css_template": forms.Textarea(attrs={"rows": 5, "class": "font-monospace"}),
            "subject_template": forms.TextInput(attrs={"class": "font-monospace"}),
        }


class NotificationTemplateFilterForm(NetBoxModelFilterSetForm):
    model = NotificationTemplate

    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("event_type", "granularity", "body_format", "is_base_template", name="Attributes"),
    )
    selector_fields = ("filter_id", "q", "event_type")

    event_type = forms.MultipleChoiceField(
        choices=MessageEventTypeChoices,
        required=False,
    )
    granularity = forms.MultipleChoiceField(
        choices=MessageGranularityChoices,
        required=False,
    )
    body_format = forms.MultipleChoiceField(
        choices=BodyFormatChoices,
        required=False,
    )
    is_base_template = forms.NullBooleanField(
        required=False,
        widget=forms.Select(
            choices=[
                ("", "---------"),
                (True, "Yes"),
                (False, "No"),
            ]
        ),
    )
    tag = TagFilterField(model)


class NotificationTemplateBulkEditForm(NetBoxModelBulkEditForm):
    """Metadata only. The Jinja bodies, `headers_template`, `contact_priorities`, `extends` and
    the unique `slug` are per-template and must stay off this form.
    """

    model = NotificationTemplate

    description = forms.CharField(
        required=False,
        widget=forms.Textarea,
    )
    event_type = forms.ChoiceField(
        choices=add_blank_choice(MessageEventTypeChoices),
        required=False,
    )
    granularity = forms.ChoiceField(
        choices=add_blank_choice(MessageGranularityChoices),
        required=False,
    )
    body_format = forms.ChoiceField(
        choices=add_blank_choice(BodyFormatChoices),
        required=False,
    )
    include_ical = forms.NullBooleanField(
        required=False,
        widget=BulkEditNullBooleanSelect(),
    )
    weight = forms.IntegerField(
        required=False,
    )
    contact_roles = DynamicModelMultipleChoiceField(
        queryset=ContactRole.objects.all(),
        required=False,
    )

    nullable_fields = ("description",)


# PreparedNotification Forms
class PreparedNotificationForm(NetBoxModelForm):
    """Form for creating/editing PreparedNotification records."""

    from tenancy.models import Contact

    template = DynamicModelChoiceField(
        queryset=NotificationTemplate.objects.all(),
        quick_add=True,
        selector=True,
    )
    contacts = DynamicModelMultipleChoiceField(
        queryset=Contact.objects.all(),
        required=False,
    )

    fieldsets = (
        FieldSet("template", name="Notification"),
        FieldSet("contacts", name="Recipients"),
        FieldSet("subject", "body_text", "body_html", name="Content"),
        FieldSet("tags", name="Tags"),
    )

    class Meta:
        model = PreparedNotification
        # No `status`: a ModelForm writes the column directly, skipping the side effects only
        # PreparedNotificationStateMachine applies (recipient snapshot, approved_by/at, sent_at,
        # delivered_at). Status is API-only.
        fields = [
            "template",
            "contacts",
            "subject",
            "body_text",
            "body_html",
            "headers",
            "css",
            "ical_content",
            "tags",
        ]
        widgets = {
            "body_text": forms.Textarea(attrs={"rows": 10}),
            "body_html": forms.Textarea(attrs={"rows": 10}),
        }


class PreparedNotificationFilterForm(NetBoxModelFilterSetForm):
    model = PreparedNotification

    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("status", "template_id", name="Attributes"),
    )
    selector_fields = ("filter_id", "q", "status", "template_id")

    status = forms.MultipleChoiceField(
        choices=PreparedNotificationStatusChoices,
        required=False,
    )
    template_id = DynamicModelMultipleChoiceField(
        queryset=NotificationTemplate.objects.all(),
        required=False,
        label="Template",
    )
    tag = TagFilterField(model)


class SentNotificationFilterForm(NetBoxModelFilterSetForm):
    """Filter form for Sent notifications (only sent/delivered statuses)."""

    model = SentNotification

    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("status", "template_id", name="Attributes"),
    )
    selector_fields = ("filter_id", "q", "status", "template_id")

    # Only show sent/delivered status options
    status = forms.MultipleChoiceField(
        choices=[
            ("sent", "Sent"),
            ("delivered", "Delivered"),
        ],
        required=False,
    )
    template_id = DynamicModelMultipleChoiceField(
        queryset=NotificationTemplate.objects.all(),
        required=False,
        label="Template",
    )
    tag = TagFilterField(PreparedNotification)  # Use parent model for tags


# PreparedNotification has no bulk edit form on purpose. `status` was its only bulk-editable
# field, and `BulkEditView._update_objects` assigns and saves directly -- skipping the state
# machine's recipient snapshot, "no recipients" guard and timestamps. The view is unmounted;
# status is changed through the REST API.


# TemplateScope Forms
class TemplateScopeForm(GenericForeignKeyFormMixin, forms.ModelForm):
    """
    Form for creating/editing TemplateScope records.
    Uses GenericForeignKeyFormMixin for HTMX-based object picker.
    """

    # Register GenericFK field with mixin
    generic_fk_fields = [
        ("scope", "content_type", "object_id"),
    ]

    template = DynamicModelChoiceField(
        queryset=NotificationTemplate.objects.all(),
        selector=True,
    )

    fieldsets = (
        FieldSet("template", name="Template"),
        FieldSet("content_type", "scope_choice", name="Scope Target"),
        FieldSet("event_type", "event_status", name="Event Filtering"),
        FieldSet("weight", name="Priority"),
    )

    class Meta:
        model = TemplateScope
        fields = [
            "template",
            "content_type",
            "object_id",
            "event_type",
            "event_status",
            "weight",
        ]
        widgets = {
            "content_type": HTMXSelect(),
            "object_id": forms.HiddenInput,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Get allowed content types from plugin configuration + event types
        allowed_types = get_allowed_content_types()
        content_type_pks = []

        # Add configured allowed types (circuits, devices, etc.)
        for type_string in allowed_types:
            try:
                app_label, model = type_string.lower().split(".")
                ct = ContentType.objects.filter(app_label=app_label, model=model).first()
                if ct:
                    content_type_pks.append(ct.pk)
            except (ValueError, AttributeError):
                continue

        # Also add Provider content type (commonly used for scoping)
        provider_ct = ContentType.objects.filter(app_label="circuits", model="provider").first()
        if provider_ct:
            content_type_pks.append(provider_ct.pk)

        # Add event types (Maintenance, Outage)
        event_cts = ContentType.objects.filter(app_label="notices", model__in=["maintenance", "outage"])
        content_type_pks.extend([ct.pk for ct in event_cts])

        self.fields["content_type"].queryset = ContentType.objects.filter(pk__in=content_type_pks)
        self.fields["content_type"].label = "Scope Type"
        self.fields["content_type"].help_text = "Type of object this scope applies to"

        self.fields["object_id"].required = False

        # Event filtering fields
        self.fields["event_type"].required = False
        self.fields["event_status"].required = False

        # Determine content type from form state
        ct_id = get_field_value(self, "content_type")
        if ct_id:
            self.init_generic_choice("scope", ct_id)

    def init_generic_choice(self, field_prefix, content_type_id):
        """Override to make the object field optional (null = all objects of type)."""
        if isinstance(content_type_id, list):
            content_type_id = content_type_id[0] if content_type_id else None

        if not content_type_id:
            return

        initial = None
        try:
            content_type = ContentType.objects.get(pk=content_type_id)
            model_class = content_type.model_class()

            # Get initial value if editing existing object
            object_id_field = "object_id"
            object_id = get_field_value(self, object_id_field)

            if isinstance(object_id, list):
                object_id = object_id[0] if object_id else None

            if object_id:
                initial = model_class.objects.get(pk=object_id)

            # Create dynamic choice field with model-specific queryset
            choice_field_name = f"{field_prefix}_choice"
            self.fields[choice_field_name] = DynamicModelChoiceField(
                label=f"Specific {content_type.model.title()} (optional)",
                queryset=model_class.objects.all(),
                required=False,  # Optional - null means "all of this type"
                initial=initial,
                help_text="Leave blank to match all objects of this type",
            )
        except (ContentType.DoesNotExist, ObjectDoesNotExist):
            # Content type or referenced object no longer exists; skip creating
            # the optional dynamic choice field and leave scope matching unchanged.
            pass

    def clean(self):
        """Extract ContentType and object ID from selected object."""
        cleaned_data = super(forms.ModelForm, self).clean()

        # Handle the optional scope_choice field
        choice_object = cleaned_data.get("scope_choice")
        if choice_object:
            cleaned_data["content_type"] = ContentType.objects.get_for_model(choice_object)
            cleaned_data["object_id"] = choice_object.id
        else:
            # Keep content_type but set object_id to None (matches all of type)
            cleaned_data["object_id"] = None

        return cleaned_data
