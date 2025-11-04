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
            "comments",
        )

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value) | Q(summary__icontains=value) | Q(internal_ticket__icontains=value)
        )


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
            "end",
            "estimated_time_to_repair",
            "original_timezone",
            "internal_ticket",
            "acknowledged",
            "comments",
        )

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value) | Q(summary__icontains=value) | Q(internal_ticket__icontains=value)
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
            Q(subject__icontains=value) | Q(email_body__icontains=value) | Q(email_from__icontains=value)
        )
