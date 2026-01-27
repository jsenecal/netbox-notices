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
    # MessageTemplate URLs
    path(
        "message-templates/",
        views.MessageTemplateListView.as_view(),
        name="messagetemplate_list",
    ),
    path(
        "message-templates/add/",
        views.MessageTemplateEditView.as_view(),
        name="messagetemplate_add",
    ),
    path(
        "message-templates/<int:pk>/",
        views.MessageTemplateView.as_view(),
        name="messagetemplate",
    ),
    path(
        "message-templates/<int:pk>/edit/",
        views.MessageTemplateEditView.as_view(),
        name="messagetemplate_edit",
    ),
    path(
        "message-templates/<int:pk>/delete/",
        views.MessageTemplateDeleteView.as_view(),
        name="messagetemplate_delete",
    ),
    path(
        "message-templates/<int:pk>/changelog/",
        ObjectChangeLogView.as_view(),
        name="messagetemplate_changelog",
        kwargs={"model": models.MessageTemplate},
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
    # Outbound Messages (sent/delivered)
    path(
        "outbound/",
        views.OutboundMessageListView.as_view(),
        name="outbound_list",
    ),
    # PreparedMessage URLs
    path(
        "prepared-messages/",
        views.PreparedMessageListView.as_view(),
        name="preparedmessage_list",
    ),
    path(
        "prepared-messages/add/",
        views.PreparedMessageEditView.as_view(),
        name="preparedmessage_add",
    ),
    path(
        "prepared-messages/<int:pk>/",
        views.PreparedMessageView.as_view(),
        name="preparedmessage",
    ),
    path(
        "prepared-messages/<int:pk>/edit/",
        views.PreparedMessageEditView.as_view(),
        name="preparedmessage_edit",
    ),
    path(
        "prepared-messages/<int:pk>/delete/",
        views.PreparedMessageDeleteView.as_view(),
        name="preparedmessage_delete",
    ),
    path(
        "prepared-messages/<int:pk>/changelog/",
        ObjectChangeLogView.as_view(),
        name="preparedmessage_changelog",
        kwargs={"model": models.PreparedMessage},
    ),
    path(
        "prepared-messages/edit/",
        views.PreparedMessageBulkEditView.as_view(),
        name="preparedmessage_bulk_edit",
    ),
    path(
        "prepared-messages/delete/",
        views.PreparedMessageBulkDeleteView.as_view(),
        name="preparedmessage_bulk_delete",
    ),
)
