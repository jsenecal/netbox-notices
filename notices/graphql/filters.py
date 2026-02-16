import strawberry_django
from netbox.graphql.filter_mixins import PrimaryModelFilterMixin
from strawberry.scalars import ID
from strawberry_django import FilterLookup

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
class MaintenanceFilter(PrimaryModelFilterMixin):
    name: FilterLookup[str] | None = strawberry_django.filter_field()
    summary: FilterLookup[str] | None = strawberry_django.filter_field()
    status: FilterLookup[str] | None = strawberry_django.filter_field()
    provider_id: ID | None = strawberry_django.filter_field()
    acknowledged: bool | None = strawberry_django.filter_field()


@strawberry_django.filter_type(models.Outage, lookups=True)
class OutageFilter(PrimaryModelFilterMixin):
    name: FilterLookup[str] | None = strawberry_django.filter_field()
    summary: FilterLookup[str] | None = strawberry_django.filter_field()
    status: FilterLookup[str] | None = strawberry_django.filter_field()
    provider_id: ID | None = strawberry_django.filter_field()
    acknowledged: bool | None = strawberry_django.filter_field()


@strawberry_django.filter_type(models.Impact, lookups=True)
class ImpactFilter(PrimaryModelFilterMixin):
    impact: FilterLookup[str] | None = strawberry_django.filter_field()
    event_object_id: ID | None = strawberry_django.filter_field()
    target_object_id: ID | None = strawberry_django.filter_field()


@strawberry_django.filter_type(models.EventNotification, lookups=True)
class EventNotificationFilter(PrimaryModelFilterMixin):
    subject: FilterLookup[str] | None = strawberry_django.filter_field()
    email_from: FilterLookup[str] | None = strawberry_django.filter_field()


@strawberry_django.filter_type(models.NotificationTemplate, lookups=True)
class NotificationTemplateFilter(PrimaryModelFilterMixin):
    name: FilterLookup[str] | None = strawberry_django.filter_field()
    slug: FilterLookup[str] | None = strawberry_django.filter_field()
    event_type: FilterLookup[str] | None = strawberry_django.filter_field()


@strawberry_django.filter_type(models.PreparedNotification, lookups=True)
class PreparedNotificationFilter(PrimaryModelFilterMixin):
    status: FilterLookup[str] | None = strawberry_django.filter_field()
    subject: FilterLookup[str] | None = strawberry_django.filter_field()
