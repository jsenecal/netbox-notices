from netbox.api.viewsets import NetBoxModelViewSet

from .. import filtersets, models
from .serializers import (
    CircuitMaintenanceImpactSerializer,
    CircuitMaintenanceNotificationsSerializer,
    CircuitMaintenanceSerializer,
    CircuitOutageSerializer,
)


class CircuitMaintenanceViewSet(NetBoxModelViewSet):
    queryset = models.CircuitMaintenance.objects.prefetch_related("tags")
    serializer_class = CircuitMaintenanceSerializer
    filterset_class = filtersets.CircuitMaintenanceFilterSet


class CircuitMaintenanceImpactViewSet(NetBoxModelViewSet):
    queryset = models.CircuitMaintenanceImpact.objects.prefetch_related("tags")
    serializer_class = CircuitMaintenanceImpactSerializer
    filterset_class = filtersets.CircuitMaintenanceImpactFilterSet


class CircuitMaintenanceNotificationsViewSet(NetBoxModelViewSet):
    queryset = models.CircuitMaintenanceNotifications.objects.prefetch_related("tags")
    serializer_class = CircuitMaintenanceNotificationsSerializer
    filterset_class = filtersets.CircuitMaintenanceNotificationsFilterSet


class CircuitOutageViewSet(NetBoxModelViewSet):
    queryset = models.CircuitOutage.objects.prefetch_related("tags")
    serializer_class = CircuitOutageSerializer
    filterset_class = filtersets.CircuitOutageFilterSet
