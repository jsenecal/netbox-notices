from django.shortcuts import get_object_or_404
from netbox.api.viewsets import NetBoxModelViewSet
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from notices.api.permissions import TokenWriteOnlyPermission
from notices.api.serializers import (
    NotificationTemplateSerializer,
    PreparedNotificationSerializer,
    SentNotificationSerializer,
)
from notices.filtersets import NotificationTemplateFilterSet, PreparedNotificationFilterSet
from notices.models import NotificationTemplate, PreparedNotification, SentNotification
from notices.services.notification_generation import NotificationGenerator
from notices.services.template_renderer import TemplateRenderError

__all__ = (
    "NotificationTemplateViewSet",
    "PreparedNotificationViewSet",
    "SentNotificationViewSet",
)


class NotificationTemplateViewSet(NetBoxModelViewSet):
    """API viewset for NotificationTemplate."""

    queryset = NotificationTemplate.objects.prefetch_related(
        "scopes",
        "contact_roles",
        "tags",
    )
    serializer_class = NotificationTemplateSerializer
    filterset_class = NotificationTemplateFilterSet


class PreparedNotificationViewSet(NetBoxModelViewSet):
    """API viewset for PreparedNotification."""

    queryset = PreparedNotification.objects.select_related(
        "template",
        "approved_by",
    ).prefetch_related(
        "contacts",
        "tags",
    )
    serializer_class = PreparedNotificationSerializer
    filterset_class = PreparedNotificationFilterSet

    @action(detail=True, methods=["post"], permission_classes=[TokenWriteOnlyPermission])
    def reset(self, request, pk=None):
        """Re-render a draft from its template, discarding manual edits."""
        if not request.user.has_perm("notices.change_preparednotification"):
            raise PermissionDenied()
        notification = get_object_or_404(PreparedNotification.objects.restrict(request.user, "change"), pk=pk)
        try:
            NotificationGenerator(notification.event).reset(notification)
        except (ValueError, TemplateRenderError) as e:
            raise ValidationError({"detail": str(e)})
        return Response(self.get_serializer(notification).data)


class SentNotificationViewSet(NetBoxModelViewSet):
    """Read-only API viewset for SentNotification (sent/delivered only)."""

    queryset = SentNotification.objects.select_related(
        "template",
        "approved_by",
    ).prefetch_related(
        "contacts",
        "tags",
    )
    serializer_class = SentNotificationSerializer
    filterset_class = PreparedNotificationFilterSet
    http_method_names = ["get", "head", "options"]  # Read-only
