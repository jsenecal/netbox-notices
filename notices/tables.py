import django_tables2 as tables
from netbox.tables import NetBoxTable, columns

from .models import (
    EventNotification,
    Maintenance,
    NotificationTemplate,
    Outage,
    PreparedNotification,
    SentNotification,
)


class MaintenanceTable(NetBoxTable):
    name = tables.Column(linkify=True)

    provider = tables.Column(linkify=True)

    status = columns.ChoiceFieldColumn()

    impact_count = tables.Column(verbose_name="Impacted Objects")

    summary = tables.TemplateColumn(
        '<data-toggle="tooltip" title="{{record.summary}}">{{record.summary|truncatewords:15}}'
    )

    actions = columns.ActionsColumn(
        extra_buttons="""
        {% load tz %}
        {% now "U" as current_timestamp %}
        {% if record.status not in 'COMPLETED,CANCELLED,RE-SCHEDULED' and record.start|date:"U" > current_timestamp %}
        <a href="{% url 'plugins:notices:maintenance_reschedule' pk=record.pk %}" class="btn btn-sm btn-warning lh-1" title="Reschedule">
            <i class="mdi mdi-calendar-refresh"></i>
        </a>
        {% else %}
        <button type="button" class="btn btn-sm btn-outline-secondary lh-1 disabled" title="Cannot reschedule">
            <i class="mdi mdi-calendar-refresh"></i>
        </button>
        {% endif %}
        {% if record.status not in 'COMPLETED,CANCELLED,RE-SCHEDULED' %}
        <a href="{% url 'plugins:notices:maintenance_cancel' pk=record.pk %}?return_url={{ request.get_full_path|urlencode }}" class="btn btn-sm btn-danger lh-1" title="Cancel">
            <i class="mdi mdi-cancel"></i>
        </a>
        {% else %}
        <button type="button" class="btn btn-sm btn-outline-secondary lh-1 disabled" title="Cannot cancel">
            <i class="mdi mdi-cancel"></i>
        </button>
        {% endif %}
        """
    )

    class Meta(NetBoxTable.Meta):
        model = Maintenance
        fields = (
            "pk",
            "id",
            "name",
            "summary",
            "status",
            "provider",
            "start",
            "end",
            "internal_ticket",
            "acknowledged",
            "impact_count",
            "actions",
        )
        default_columns = (
            "name",
            "summary",
            "provider",
            "start",
            "end",
            "acknowledged",
            "internal_ticket",
            "status",
            "impact_count",
        )


class OutageTable(NetBoxTable):
    name = tables.Column(linkify=True)
    provider = tables.Column(linkify=True)
    status = columns.ChoiceFieldColumn()
    start = columns.DateTimeColumn()
    end = columns.DateTimeColumn()
    estimated_time_to_repair = columns.DateTimeColumn(verbose_name="ETR")

    class Meta(NetBoxTable.Meta):
        model = Outage
        fields = (
            "pk",
            "name",
            "provider",
            "summary",
            "status",
            "start",
            "end",
            "estimated_time_to_repair",
            "internal_ticket",
            "acknowledged",
            "created",
        )
        default_columns = (
            "name",
            "provider",
            "status",
            "start",
            "end",
            "estimated_time_to_repair",
        )


class EventNotificationTable(NetBoxTable):
    """
    Table for displaying EventNotification records with GenericForeignKey support.
    Shows the associated event (Maintenance/Outage) and email details.
    """

    # Customize actions column to exclude edit (notifications are read-only)
    actions = columns.ActionsColumn(actions=("delete",))

    # Event column - display the event name and link to it
    event = tables.TemplateColumn(
        template_code="""
        {% if record.event %}
            <a href="{{ record.event.get_absolute_url }}">{{ record.event }}</a>
        {% else %}
            <span class="text-muted">Unknown</span>
        {% endif %}
        """,
        verbose_name="Event",
        orderable=False,
    )

    # Event type column
    event_type = tables.TemplateColumn(
        template_code="""
        {% if record.event_content_type %}
            {{ record.event_content_type.model|title }}
        {% else %}
            <span class="text-muted">Unknown</span>
        {% endif %}
        """,
        verbose_name="Event Type",
        orderable=False,
    )

    # Subject column - linkify to detail page
    subject = tables.Column(linkify=True)

    # Email from
    email_from = tables.Column(verbose_name="From")

    # Email received
    email_received = columns.DateTimeColumn(verbose_name="Received")

    # Email body preview
    email_body = tables.TemplateColumn(
        template_code='<data-toggle="tooltip" title="{{record.email_body}}">{{record.email_body|truncatewords:20}}',
        verbose_name="Body Preview",
    )

    class Meta(NetBoxTable.Meta):
        model = EventNotification
        fields = (
            "pk",
            "id",
            "event",
            "event_type",
            "subject",
            "email_from",
            "email_received",
            "email_body",
            "created",
            "actions",
        )
        default_columns = (
            "event",
            "event_type",
            "subject",
            "email_from",
            "email_received",
        )


class NotificationTemplateTable(NetBoxTable):
    """Table for displaying NotificationTemplate records."""

    name = tables.Column(linkify=True)
    event_type = columns.ChoiceFieldColumn()
    granularity = columns.ChoiceFieldColumn()
    body_format = columns.ChoiceFieldColumn()
    extends = tables.Column(linkify=True)
    is_base_template = columns.BooleanColumn()
    actions = columns.ActionsColumn()

    class Meta(NetBoxTable.Meta):
        model = NotificationTemplate
        fields = (
            "pk",
            "id",
            "name",
            "slug",
            "event_type",
            "granularity",
            "body_format",
            "is_base_template",
            "extends",
            "weight",
            "created",
            "actions",
        )
        default_columns = (
            "name",
            "event_type",
            "granularity",
            "is_base_template",
            "weight",
        )


class PreparedNotificationTable(NetBoxTable):
    """Table for displaying PreparedNotification records."""

    subject = tables.Column(linkify=True)
    template = tables.Column(linkify=True)
    status = columns.ChoiceFieldColumn()
    approved_by = tables.Column(linkify=True)
    sent_at = columns.DateTimeColumn()
    delivered_at = columns.DateTimeColumn()
    actions = columns.ActionsColumn()

    class Meta(NetBoxTable.Meta):
        model = PreparedNotification
        fields = (
            "pk",
            "id",
            "subject",
            "template",
            "status",
            "approved_by",
            "approved_at",
            "sent_at",
            "delivered_at",
            "created",
            "actions",
        )
        default_columns = (
            "subject",
            "template",
            "status",
            "sent_at",
        )


class SentNotificationTable(NetBoxTable):
    """Table for displaying SentNotification records (sent/delivered only)."""

    subject = tables.Column(linkify=True)
    template = tables.Column(linkify=True)
    status = columns.ChoiceFieldColumn()
    approved_by = tables.Column(linkify=True)
    sent_at = columns.DateTimeColumn()
    delivered_at = columns.DateTimeColumn()
    # Keep this explicit. ActionsColumn defaults to edit/delete/changelog and reverses eagerly,
    # but the proxy has no per-object edit or delete URL -- so the default raises NoReverseMatch
    # and 500s the list as soon as it has one row (an empty list renders fine, which is how that
    # survived unnoticed).
    actions = columns.ActionsColumn(actions=("changelog",))

    class Meta(NetBoxTable.Meta):
        model = SentNotification
        fields = (
            "pk",
            "id",
            "subject",
            "template",
            "status",
            "approved_by",
            "approved_at",
            "sent_at",
            "delivered_at",
            "created",
            "actions",
        )
        default_columns = (
            "subject",
            "template",
            "status",
            "sent_at",
            "delivered_at",
        )
