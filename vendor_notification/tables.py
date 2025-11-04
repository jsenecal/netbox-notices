import django_tables2 as tables
from netbox.tables import NetBoxTable, columns

from .models import EventNotification, Impact, Maintenance, Outage


class MaintenanceTable(NetBoxTable):
    name = tables.Column(linkify=True)

    provider = tables.Column(linkify=True)

    status = columns.ChoiceFieldColumn()

    impact_count = tables.Column(verbose_name="Impacted Objects")

    summary = tables.TemplateColumn(
        '<data-toggle="tooltip" title="{{record.summary}}">{{record.summary|truncatewords:15}}'
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


class ImpactTable(NetBoxTable):
    """
    Table for displaying Impact records with GenericForeignKey support.
    Shows both the event (Maintenance/Outage) and target (Circuit/Device/etc).
    """

    # Event column - display the event name and link to it
    event = tables.TemplateColumn(
        template_code="""
        {% if record.event %}
            <a href="{{ record.event.get_absolute_url }}">{{ record.event }}</a>
            <span class="badge bg-{{ record.event.get_status_color }}">
                {{ record.event.status }}
            </span>
        {% else %}
            <span class="text-muted">Unknown</span>
        {% endif %}
        """,
        verbose_name="Event",
        orderable=False,
    )

    # Event type column - show if it's Maintenance or Outage
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

    # Target column - display the affected object
    target = tables.TemplateColumn(
        template_code="""
        {% if record.target %}
            {% if record.target.get_absolute_url %}
                <a href="{{ record.target.get_absolute_url }}">{{ record.target }}</a>
            {% else %}
                {{ record.target }}
            {% endif %}
        {% else %}
            <span class="text-muted">Unknown</span>
        {% endif %}
        """,
        verbose_name="Impacted Object",
        orderable=False,
    )

    # Target type column - show the object type
    target_type = tables.TemplateColumn(
        template_code="""
        {% if record.target_content_type %}
            {{ record.target_content_type.model|title }}
        {% else %}
            <span class="text-muted">Unknown</span>
        {% endif %}
        """,
        verbose_name="Object Type",
        orderable=False,
    )

    # Impact level
    impact = columns.ChoiceFieldColumn()

    class Meta(NetBoxTable.Meta):
        model = Impact
        fields = (
            "pk",
            "id",
            "event",
            "event_type",
            "target",
            "target_type",
            "impact",
            "created",
            "last_updated",
            "actions",
        )
        default_columns = (
            "event",
            "event_type",
            "target",
            "target_type",
            "impact",
        )


class EventNotificationTable(NetBoxTable):
    """
    Table for displaying EventNotification records with GenericForeignKey support.
    Shows the associated event (Maintenance/Outage) and email details.
    """

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
