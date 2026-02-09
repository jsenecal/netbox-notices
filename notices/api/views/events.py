from netbox.api.viewsets import NetBoxModelViewSet

from notices import filtersets, models
from notices.api.serializers import (
    EventNotificationSerializer,
    ImpactSerializer,
    MaintenanceSerializer,
    OutageSerializer,
)

__all__ = (
    "MaintenanceViewSet",
    "OutageViewSet",
    "ImpactViewSet",
    "EventNotificationViewSet",
)


class MaintenanceViewSet(NetBoxModelViewSet):
    queryset = models.Maintenance.objects.prefetch_related("tags")
    serializer_class = MaintenanceSerializer
    filterset_class = filtersets.MaintenanceFilterSet


class OutageViewSet(NetBoxModelViewSet):
    queryset = models.Outage.objects.prefetch_related("tags")
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
