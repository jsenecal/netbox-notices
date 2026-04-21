import strawberry_django
from netbox.graphql.filters import PrimaryModelFilter
from strawberry.scalars import ID
from strawberry_django import FilterLookup

try:
    from strawberry_django import StrFilterLookup
except ImportError:
    StrFilterLookup = FilterLookup[str]

from notices import models

__all__ = (
    "MaintenanceFilter",
    "OutageFilter",
    "ImpactFilter",
    "EventNotificationFilter",
    "NotificationTemplateFilter",
    "PreparedNotificationFilter",
)


@strawberry_django.filter_type(models.Maintenance, lookups=True)
class MaintenanceFilter(PrimaryModelFilter):
    name: StrFilterLookup | None = strawberry_django.filter_field()
    summary: StrFilterLookup | None = strawberry_django.filter_field()
    status: StrFilterLookup | None = strawberry_django.filter_field()
    provider_id: ID | None = strawberry_django.filter_field()
    acknowledged: bool | None = strawberry_django.filter_field()


@strawberry_django.filter_type(models.Outage, lookups=True)
class OutageFilter(PrimaryModelFilter):
    name: StrFilterLookup | None = strawberry_django.filter_field()
    summary: StrFilterLookup | None = strawberry_django.filter_field()
    status: StrFilterLookup | None = strawberry_django.filter_field()
    provider_id: ID | None = strawberry_django.filter_field()
    acknowledged: bool | None = strawberry_django.filter_field()


@strawberry_django.filter_type(models.Impact, lookups=True)
class ImpactFilter(PrimaryModelFilter):
    impact: StrFilterLookup | None = strawberry_django.filter_field()
    event_object_id: ID | None = strawberry_django.filter_field()
    target_object_id: ID | None = strawberry_django.filter_field()


@strawberry_django.filter_type(models.EventNotification, lookups=True)
class EventNotificationFilter(PrimaryModelFilter):
    subject: StrFilterLookup | None = strawberry_django.filter_field()
    email_from: StrFilterLookup | None = strawberry_django.filter_field()


@strawberry_django.filter_type(models.NotificationTemplate, lookups=True)
class NotificationTemplateFilter(PrimaryModelFilter):
    name: StrFilterLookup | None = strawberry_django.filter_field()
    slug: StrFilterLookup | None = strawberry_django.filter_field()
    event_type: StrFilterLookup | None = strawberry_django.filter_field()


@strawberry_django.filter_type(models.PreparedNotification, lookups=True)
class PreparedNotificationFilter(PrimaryModelFilter):
    status: StrFilterLookup | None = strawberry_django.filter_field()
    subject: StrFilterLookup | None = strawberry_django.filter_field()
