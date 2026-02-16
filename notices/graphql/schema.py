from typing import List

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
    maintenance_list: List[MaintenanceType] = strawberry_django.field()

    outage: OutageType = strawberry_django.field()
    outage_list: List[OutageType] = strawberry_django.field()

    impact: ImpactType = strawberry_django.field()
    impact_list: List[ImpactType] = strawberry_django.field()

    event_notification: EventNotificationType = strawberry_django.field()
    event_notification_list: List[EventNotificationType] = strawberry_django.field()

    notification_template: NotificationTemplateType = strawberry_django.field()
    notification_template_list: List[NotificationTemplateType] = strawberry_django.field()

    prepared_notification: PreparedNotificationType = strawberry_django.field()
    prepared_notification_list: List[PreparedNotificationType] = strawberry_django.field()


schema = [NoticesQuery]
