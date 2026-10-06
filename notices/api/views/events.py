from django.shortcuts import get_object_or_404
from netbox.api.viewsets import NetBoxModelViewSet
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from notices import filtersets, models
from notices.api.permissions import TokenWriteOnlyPermission
from notices.api.serializers import (
    EventNotificationSerializer,
    GenerateNotificationsSerializer,
    ImpactSerializer,
    MaintenanceSerializer,
    OutageSerializer,
    PlannedNotificationSerializer,
)
from notices.constants import GENERATE_NOTIFICATIONS_PERMISSIONS
from notices.services.notification_generation import GenerationResult, NotificationGenerator

__all__ = (
    "MaintenanceViewSet",
    "OutageViewSet",
    "ImpactViewSet",
    "EventNotificationViewSet",
)


class GenerateNotificationsMixin:
    """`generate-notifications` action shared by the Maintenance and Outage viewsets."""

    @action(
        detail=True,
        methods=["post"],
        url_path="generate-notifications",
        permission_classes=[TokenWriteOnlyPermission],
    )
    def generate_notifications(self, request, pk=None):
        if not request.user.has_perms(GENERATE_NOTIFICATIONS_PERMISSIONS):
            raise PermissionDenied(
                "Generating notifications requires add, change and delete on prepared notifications."
            )
        event = get_object_or_404(self.queryset.model.objects.restrict(request.user, "view"), pk=pk)
        generator = NotificationGenerator(event)
        params = GenerateNotificationsSerializer(data=request.data, context={"kinds": generator.applicable_kinds()})
        params.is_valid(raise_exception=True)
        if templates := params.validated_data.get("templates"):
            generator = NotificationGenerator(event, templates=templates)
        plan = generator.plan()
        result = (
            GenerationResult.from_plan(plan)
            if params.validated_data["dry_run"]
            else generator.apply(plan, user=request.user)
        )
        return Response(
            {
                "summary": result.summary(),
                "counts": result.counts,
                "items": PlannedNotificationSerializer(result.items, many=True).data,
            }
        )


class MaintenanceViewSet(GenerateNotificationsMixin, NetBoxModelViewSet):
    queryset = models.Maintenance.objects.prefetch_related("tags")
    serializer_class = MaintenanceSerializer
    filterset_class = filtersets.MaintenanceFilterSet


class OutageViewSet(GenerateNotificationsMixin, NetBoxModelViewSet):
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
