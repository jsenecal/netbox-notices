import django_filters
from django.db.models import Q
from netbox.filtersets import NetBoxModelFilterSet
from utilities.filters import ContentTypeFilter

from .models import (
    EventNotification,
    Impact,
    Maintenance,
    Outage,
)


class MaintenanceFilterSet(NetBoxModelFilterSet):
    """FilterSet for Maintenance events"""

    replaces_id = django_filters.ModelMultipleChoiceFilter(
        queryset=Maintenance.objects.all(),
        label="Replaces (ID)",
    )

    has_replaces = django_filters.BooleanFilter(
        method="filter_has_replaces",
        label="Has replacement",
    )

    class Meta:
        model = Maintenance
        fields = (
            "id",
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
        )

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value)
            | Q(summary__icontains=value)
            | Q(internal_ticket__icontains=value)
            | Q(impact__icontains=value)
        )

    def filter_has_replaces(self, queryset, name, value):
        """Filter maintenances that have been rescheduled."""
        if value:
            return queryset.exclude(replaced_by_maintenance=None)
        return queryset.filter(replaced_by_maintenance=None)


class OutageFilterSet(NetBoxModelFilterSet):
    """FilterSet for Outage events"""

    class Meta:
        model = Outage
        fields = (
            "id",
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
        )

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value)
            | Q(summary__icontains=value)
            | Q(internal_ticket__icontains=value)
            | Q(impact__icontains=value)
        )


class ImpactFilterSet(NetBoxModelFilterSet):
    """
    FilterSet for Impact objects.
    Supports filtering by both event and target GenericForeignKey relationships.
    """

    # Filter for event content type (Maintenance or Outage)
    event_content_type = ContentTypeFilter()

    # Filter for target content type (Circuit, Device, etc.)
    target_content_type = ContentTypeFilter()

    class Meta:
        model = Impact
        fields = (
            "id",
            "event_content_type",
            "event_object_id",
            "target_content_type",
            "target_object_id",
            "impact",
        )

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        # Search is complex for GenericForeignKey - for now just search impact level
        return queryset.filter(Q(impact__icontains=value))


class EventNotificationFilterSet(NetBoxModelFilterSet):
    """
    FilterSet for EventNotification objects.
    Supports filtering by event GenericForeignKey relationship.
    """

    # Filter for event content type (Maintenance or Outage)
    event_content_type = ContentTypeFilter()

    class Meta:
        model = EventNotification
        fields = (
            "id",
            "event_content_type",
            "event_object_id",
            "email_body",
            "subject",
            "email_from",
            "email_received",
        )

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(subject__icontains=value)
            | Q(email_body__icontains=value)
            | Q(email_from__icontains=value)
        )
