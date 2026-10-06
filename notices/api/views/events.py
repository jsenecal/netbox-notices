from netbox.api.viewsets import NetBoxModelViewSet

from notices import filtersets, models
from notices.api.serializers import (
    EventNotificationSerializer,
    ImpactSerializer,
    MaintenanceSerializer,
    OutageSerializer,
)

# The nested impact/notification serializers read each row's content types and
# generic foreign keys; prefetch them so list responses do not issue per-event queries.
EVENT_PREFETCHES = (
    "tags",
    "impacts__event_content_type",
    "impacts__event",
    "impacts__target_content_type",
    "impacts__target",
    "notifications__event_content_type",
    "notifications__event",
)

__all__ = (
    "MaintenanceViewSet",
    "OutageViewSet",
    "ImpactViewSet",
    "EventNotificationViewSet",
)


class MaintenanceViewSet(NetBoxModelViewSet):
    queryset = models.Maintenance.objects.prefetch_related(*EVENT_PREFETCHES)
    serializer_class = MaintenanceSerializer
    filterset_class = filtersets.MaintenanceFilterSet


class OutageViewSet(NetBoxModelViewSet):
    queryset = models.Outage.objects.prefetch_related(*EVENT_PREFETCHES)
    serializer_class = OutageSerializer
    filterset_class = filtersets.OutageFilterSet


class ImpactViewSet(NetBoxModelViewSet):
    queryset = models.Impact.objects.prefetch_related("tags")
    serializer_class = ImpactSerializer
    filterset_class = filtersets.ImpactFilterSet


class EventNotificationViewSet(NetBoxModelViewSet):
    queryset = models.EventNotification.objects.prefetch_related("tags")
    serializer_class = EventNotificationSerializer
    filterset_class = filtersets.EventNotificationFilterSet
