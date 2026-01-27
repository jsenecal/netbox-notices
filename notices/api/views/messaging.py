from netbox.api.viewsets import NetBoxModelViewSet

from notices.api.serializers import NotificationTemplateSerializer, PreparedNotificationSerializer
from notices.filtersets import NotificationTemplateFilterSet, PreparedNotificationFilterSet
from notices.models import NotificationTemplate, PreparedNotification

__all__ = (
    "NotificationTemplateViewSet",
    "PreparedNotificationViewSet",
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
