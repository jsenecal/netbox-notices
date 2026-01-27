from netbox.api.routers import NetBoxRouter

from . import views

app_name = "notices"

router = NetBoxRouter()
router.register("maintenance", views.MaintenanceViewSet)
router.register("outage", views.OutageViewSet)
router.register("impact", views.ImpactViewSet)
router.register("eventnotification", views.EventNotificationViewSet)
router.register("message-templates", views.MessageTemplateViewSet)
router.register("prepared-messages", views.PreparedMessageViewSet)

urlpatterns = router.urls
