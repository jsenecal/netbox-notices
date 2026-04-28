import strawberry
import strawberry_django

from .types import (
    EventNotificationType,
    ImpactType,
    MaintenanceType,
    NotificationTemplateType,
    OutageType,
    PreparedNotificationType,
)


@strawberry.type(name="Query")
class NoticesQuery:
    maintenance: MaintenanceType = strawberry_django.field()
    maintenance_list: list[MaintenanceType] = strawberry_django.field()

    outage: OutageType = strawberry_django.field()
    outage_list: list[OutageType] = strawberry_django.field()

    impact: ImpactType = strawberry_django.field()
    impact_list: list[ImpactType] = strawberry_django.field()

    event_notification: EventNotificationType = strawberry_django.field()
    event_notification_list: list[EventNotificationType] = strawberry_django.field()

    notification_template: NotificationTemplateType = strawberry_django.field()
    notification_template_list: list[NotificationTemplateType] = strawberry_django.field()

    prepared_notification: PreparedNotificationType = strawberry_django.field()
    prepared_notification_list: list[PreparedNotificationType] = strawberry_django.field()


schema = [NoticesQuery]
