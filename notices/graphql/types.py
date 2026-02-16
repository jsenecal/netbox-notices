from typing import TYPE_CHECKING, Annotated

import strawberry
import strawberry_django
from netbox.graphql.types import NetBoxObjectType

from notices import models

from .filters import (
    EventNotificationFilter,
    ImpactFilter,
    MaintenanceFilter,
    NotificationTemplateFilter,
    OutageFilter,
    PreparedNotificationFilter,
)

if TYPE_CHECKING:
    from circuits.graphql.types import ProviderType

__all__ = (
    "MaintenanceType",
    "OutageType",
    "ImpactType",
    "EventNotificationType",
    "NotificationTemplateType",
    "PreparedNotificationType",
)


@strawberry_django.type(
    models.Maintenance,
    fields="__all__",
    filters=MaintenanceFilter,
    pagination=True,
)
class MaintenanceType(NetBoxObjectType):
    provider: Annotated["ProviderType", strawberry.lazy("circuits.graphql.types")]


@strawberry_django.type(
    models.Outage,
    fields="__all__",
    filters=OutageFilter,
    pagination=True,
)
class OutageType(NetBoxObjectType):
    provider: Annotated["ProviderType", strawberry.lazy("circuits.graphql.types")]


@strawberry_django.type(
    models.Impact,
    fields="__all__",
    filters=ImpactFilter,
    pagination=True,
)
class ImpactType(NetBoxObjectType):
    pass


@strawberry_django.type(
    models.EventNotification,
    exclude=["email"],
    filters=EventNotificationFilter,
    pagination=True,
)
class EventNotificationType(NetBoxObjectType):
    pass


@strawberry_django.type(
    models.NotificationTemplate,
    fields="__all__",
    filters=NotificationTemplateFilter,
    pagination=True,
)
class NotificationTemplateType(NetBoxObjectType):
    pass


@strawberry_django.type(
    models.PreparedNotification,
    fields="__all__",
    filters=PreparedNotificationFilter,
    pagination=True,
)
class PreparedNotificationType(NetBoxObjectType):
    pass
