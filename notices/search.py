from netbox.search import SearchIndex, register_search

from . import models


@register_search
class MaintenanceIndex(SearchIndex):
    model = models.Maintenance
    fields = (
        ("name", 100),
        ("summary", 500),
        ("internal_ticket", 300),
        ("comments", 5000),
    )
    display_attrs = ("provider", "status", "summary")


@register_search
class OutageIndex(SearchIndex):
    model = models.Outage
    fields = (
        ("name", 100),
        ("summary", 500),
        ("internal_ticket", 300),
        ("comments", 5000),
    )
    display_attrs = ("provider", "status", "summary")


@register_search
class EventNotificationIndex(SearchIndex):
    model = models.EventNotification
    fields = (
        ("subject", 100),
        ("email_from", 300),
    )
    display_attrs = ("subject", "email_from", "email_received")


@register_search
class NotificationTemplateIndex(SearchIndex):
    model = models.NotificationTemplate
    fields = (
        ("name", 100),
        ("slug", 110),
        ("description", 500),
    )
    display_attrs = ("description", "event_type", "granularity")


@register_search
class PreparedNotificationIndex(SearchIndex):
    model = models.PreparedNotification
    fields = (
        ("subject", 100),
        ("body_text", 5000),
    )
    display_attrs = ("subject", "status", "template")
