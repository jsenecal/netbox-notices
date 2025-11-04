from django.urls import path
from netbox.views.generic import ObjectChangeLogView

from . import models, views

urlpatterns = (
    # Maintenance URLs
    path(
        "maintenance/",
        views.MaintenanceListView.as_view(),
        name="maintenance_list",
    ),
    path(
        "maintenance/add/",
        views.MaintenanceEditView.as_view(),
        name="maintenance_add",
    ),
    path(
        "maintenance/<int:pk>/",
        views.MaintenanceView.as_view(),
        name="maintenance",
    ),
    path(
        "maintenance/<int:pk>/edit/",
        views.MaintenanceEditView.as_view(),
        name="maintenance_edit",
    ),
    path(
        "maintenance/<int:pk>/delete/",
        views.MaintenanceDeleteView.as_view(),
        name="maintenance_delete",
    ),
    path(
        "maintenance/<int:pk>/changelog/",
        ObjectChangeLogView.as_view(),
        name="maintenance_changelog",
        kwargs={"model": models.Maintenance},
    ),
    # Outage URLs
    path("outages/", views.OutageListView.as_view(), name="outage_list"),
    path("outages/add/", views.OutageEditView.as_view(), name="outage_add"),
    path("outages/<int:pk>/", views.OutageView.as_view(), name="outage"),
    path(
        "outages/<int:pk>/edit/",
        views.OutageEditView.as_view(),
        name="outage_edit",
    ),
    path(
        "outages/<int:pk>/delete/",
        views.OutageDeleteView.as_view(),
        name="outage_delete",
    ),
    path(
        "outages/<int:pk>/changelog/",
        ObjectChangeLogView.as_view(),
        name="outage_changelog",
        kwargs={"model": models.Outage},
    ),
    # Impact URLs
    path(
        "impact/add/",
        views.ImpactEditView.as_view(),
        name="impact_add",
    ),
    path(
        "impact/<int:pk>/edit/",
        views.ImpactEditView.as_view(),
        name="impact_edit",
    ),
    path(
        "impact/<int:pk>/delete/",
        views.ImpactDeleteView.as_view(),
        name="impact_delete",
    ),
    path(
        "impact/<int:pk>/changelog/",
        ObjectChangeLogView.as_view(),
        name="impact_changelog",
        kwargs={"model": models.Impact},
    ),
    # EventNotification URLs
    path(
        "notification/add/",
        views.EventNotificationEditView.as_view(),
        name="eventnotification_add",
    ),
    path(
        "notification/<int:pk>/",
        views.EventNotificationView.as_view(),
        name="eventnotification",
    ),
    # path('notification/<int:pk>/edit/', views.EventNotificationEditView.as_view(), name='eventnotification_edit'),
    path(
        "notification/<int:pk>/delete/",
        views.EventNotificationDeleteView.as_view(),
        name="eventnotification_delete",
    ),
    # Maintenance Schedule View
    path(
        "maintenanceschedule/",
        views.MaintenanceScheduleView.as_view(),
        name="maintenanceschedule",
    ),
)
