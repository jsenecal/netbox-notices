from django.urls import include, path
from utilities.urls import get_model_urls

from . import views


def _impact_object_urls():
    """Impact's per-object URLs, minus the changelog and journal tabs -- keep them excluded.

    Both tabs render through `generic/object.html`, which builds a breadcrumb from the model's
    list URL; Impact has neither a list nor a detail view, so either tab 500s. `register_models()`
    gives every NetBoxModel both views and there is no unregister API, hence the filter here.
    Nothing is lost: `Impact.to_objectchange()` files changes against the parent event.
    """
    excluded = {"impact_changelog", "impact_journal"}
    return [route for route in get_model_urls("notices", "impact") if route.name not in excluded]


# Adding a view? Decorate it with @register_model_view in views.py -- this file only mounts.
# Each model needs two entries below: one for its list-level views, one for its per-object
# views. Changelog and journal views register automatically via PluginConfig.ready().
urlpatterns = (
    # Dashboard -- not a model view
    path("", views.DashboardView.as_view(), name="dashboard"),
    # iCal feed -- not nested under a model's path
    path(
        "ical/maintenances.ics",
        views.MaintenanceICalView.as_view(),
        name="ical_maintenances",
    ),
    # Maintenance (list path is singular, unlike every other model here)
    path("maintenance/", include(get_model_urls("notices", "maintenance", detail=False))),
    path("maintenance/<int:pk>/", include(get_model_urls("notices", "maintenance"))),
    # Outage
    path("outages/", include(get_model_urls("notices", "outage", detail=False))),
    path("outages/<int:pk>/", include(get_model_urls("notices", "outage"))),
    # Impact -- child of an event: no list, detail, changelog or journal view (see
    # _impact_object_urls)
    path("impact/", include(get_model_urls("notices", "impact", detail=False))),
    path("impact/<int:pk>/", include(_impact_object_urls())),
    # EventNotification -- list is plural, per-object paths are singular. "add" sits under the
    # singular path, so it cannot ride the list bucket and is declared by hand.
    path(
        "notification/add/",
        views.EventNotificationEditView.as_view(),
        name="eventnotification_add",
    ),
    path("notifications/", include(get_model_urls("notices", "eventnotification", detail=False))),
    path("notification/<int:pk>/", include(get_model_urls("notices", "eventnotification"))),
    # NotificationTemplate
    path(
        "notification-templates/",
        include(get_model_urls("notices", "notificationtemplate", detail=False)),
    ),
    path(
        "notification-templates/<int:pk>/",
        include(get_model_urls("notices", "notificationtemplate")),
    ),
    # TemplateScope -- child of a template, edited via its parent's page
    path("template-scope/", include(get_model_urls("notices", "templatescope", detail=False))),
    path("template-scope/<int:pk>/", include(get_model_urls("notices", "templatescope"))),
    # PreparedNotification
    path(
        "prepared-notifications/",
        include(get_model_urls("notices", "preparednotification", detail=False)),
    ),
    path(
        "prepared-notifications/<int:pk>/",
        include(get_model_urls("notices", "preparednotification")),
    ),
    # SentNotification -- proxy over PreparedNotification, read-only
    path("sent-notifications/", include(get_model_urls("notices", "sentnotification", detail=False))),
    path("sent-notifications/<int:pk>/", include(get_model_urls("notices", "sentnotification"))),
)
