import django_tables2 as tables
from netbox.tables import NetBoxTable, columns

from .models import CircuitMaintenance, CircuitOutage


class CircuitMaintenanceTable(NetBoxTable):
    name = tables.Column(linkify=True)

    provider = tables.Column(linkify=True)

    status = columns.ChoiceFieldColumn()

    impact_count = tables.Column(verbose_name="Impacted Circuits")

    summary = tables.TemplateColumn(
        '<data-toggle="tooltip" title="{{record.summary}}">{{record.summary|truncatewords:15}}'
    )

    class Meta(NetBoxTable.Meta):
        model = CircuitMaintenance
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


class CircuitOutageTable(NetBoxTable):
    name = tables.Column(linkify=True)
    provider = tables.Column(linkify=True)
    status = columns.ChoiceFieldColumn()
    start = columns.DateTimeColumn()
    end = columns.DateTimeColumn()
    estimated_time_to_repair = columns.DateTimeColumn(verbose_name="ETR")

    class Meta(NetBoxTable.Meta):
        model = CircuitOutage
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
