from django.urls import path
from netbox.views.generic import ObjectChangeLogView

from . import models, views

urlpatterns = (
    # Dashboard
    path("", views.DashboardView.as_view(), name="dashboard"),
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
        "maintenance/<int:pk>/reschedule/",
        views.MaintenanceRescheduleView.as_view(),
        name="maintenance_reschedule",
    ),
    path(
        "maintenance/<int:pk>/acknowledge/",
        views.MaintenanceAcknowledgeView.as_view(),
        name="maintenance_acknowledge",
    ),
    path(
        "maintenance/<int:pk>/cancel/",
        views.MaintenanceCancelView.as_view(),
        name="maintenance_cancel",
    ),
    path(
        "maintenance/<int:pk>/mark-in-progress/",
        views.MaintenanceMarkInProgressView.as_view(),
        name="maintenance_mark_in_progress",
    ),
    path(
        "maintenance/<int:pk>/mark-completed/",
        views.MaintenanceMarkCompletedView.as_view(),
        name="maintenance_mark_completed",
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
        "notifications/",
        views.EventNotificationListView.as_view(),
        name="eventnotification_list",
    ),
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
    # Maintenance Calendar View
    path(
        "maintenance/calendar/",
        views.MaintenanceCalendarView.as_view(),
        name="maintenance_calendar",
    ),
    # iCal Feed
    path(
        "ical/maintenances.ics",
        views.MaintenanceICalView.as_view(),
        name="ical_maintenances",
    ),
    # NotificationTemplate URLs
    path(
        "notification-templates/",
        views.NotificationTemplateListView.as_view(),
        name="notificationtemplate_list",
    ),
    path(
        "notification-templates/add/",
        views.NotificationTemplateEditView.as_view(),
        name="notificationtemplate_add",
    ),
    path(
        "notification-templates/<int:pk>/",
        views.NotificationTemplateView.as_view(),
        name="notificationtemplate",
    ),
    path(
        "notification-templates/<int:pk>/edit/",
        views.NotificationTemplateEditView.as_view(),
        name="notificationtemplate_edit",
    ),
    path(
        "notification-templates/<int:pk>/delete/",
        views.NotificationTemplateDeleteView.as_view(),
        name="notificationtemplate_delete",
    ),
    path(
        "notification-templates/<int:pk>/changelog/",
        ObjectChangeLogView.as_view(),
        name="notificationtemplate_changelog",
        kwargs={"model": models.NotificationTemplate},
    ),
    # TemplateScope URLs
    path(
        "template-scope/add/",
        views.TemplateScopeEditView.as_view(),
        name="templatescope_add",
    ),
    path(
        "template-scope/<int:pk>/edit/",
        views.TemplateScopeEditView.as_view(),
        name="templatescope_edit",
    ),
    path(
        "template-scope/<int:pk>/delete/",
        views.TemplateScopeDeleteView.as_view(),
        name="templatescope_delete",
    ),
    # Sent Notifications (sent/delivered)
    path(
        "sent-notifications/",
        views.SentNotificationListView.as_view(),
        name="sentnotification_list",
    ),
    path(
        "sent-notifications/<int:pk>/",
        views.SentNotificationView.as_view(),
        name="sentnotification",
    ),
    path(
        "sent-notifications/<int:pk>/changelog/",
        ObjectChangeLogView.as_view(),
        name="sentnotification_changelog",
        kwargs={"model": models.PreparedNotification},
    ),
    # PreparedNotification URLs
    path(
        "prepared-notifications/",
        views.PreparedNotificationListView.as_view(),
        name="preparednotification_list",
    ),
    path(
        "prepared-notifications/add/",
        views.PreparedNotificationEditView.as_view(),
        name="preparednotification_add",
    ),
    path(
        "prepared-notifications/<int:pk>/",
        views.PreparedNotificationView.as_view(),
        name="preparednotification",
    ),
    path(
        "prepared-notifications/<int:pk>/edit/",
        views.PreparedNotificationEditView.as_view(),
        name="preparednotification_edit",
    ),
    path(
        "prepared-notifications/<int:pk>/delete/",
        views.PreparedNotificationDeleteView.as_view(),
        name="preparednotification_delete",
    ),
    path(
        "prepared-notifications/<int:pk>/changelog/",
        ObjectChangeLogView.as_view(),
        name="preparednotification_changelog",
        kwargs={"model": models.PreparedNotification},
    ),
    path(
        "prepared-notifications/edit/",
        views.PreparedNotificationBulkEditView.as_view(),
        name="preparednotification_bulk_edit",
    ),
    path(
        "prepared-notifications/delete/",
        views.PreparedNotificationBulkDeleteView.as_view(),
        name="preparednotification_bulk_delete",
    ),
)
