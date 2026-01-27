from netbox.api.viewsets import NetBoxModelViewSet

from notices.api.serializers import MessageTemplateSerializer, PreparedMessageSerializer
from notices.filtersets import MessageTemplateFilterSet, PreparedMessageFilterSet
from notices.models import MessageTemplate, PreparedMessage

__all__ = (
    "MessageTemplateViewSet",
    "PreparedMessageViewSet",
)


class MessageTemplateViewSet(NetBoxModelViewSet):
    """API viewset for MessageTemplate."""

    queryset = MessageTemplate.objects.prefetch_related(
        "scopes",
        "contact_roles",
        "tags",
    )
    serializer_class = MessageTemplateSerializer
    filterset_class = MessageTemplateFilterSet


class PreparedMessageViewSet(NetBoxModelViewSet):
    """API viewset for PreparedMessage."""

    queryset = PreparedMessage.objects.select_related(
        "template",
        "approved_by",
    ).prefetch_related(
        "contacts",
        "tags",
    )
    serializer_class = PreparedMessageSerializer
    filterset_class = PreparedMessageFilterSet
