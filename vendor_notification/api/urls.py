from netbox.api.routers import NetBoxRouter

from . import views

app_name = "vendor_notification"

router = NetBoxRouter()
router.register("maintenance", views.MaintenanceViewSet)
router.register("outage", views.OutageViewSet)
router.register("impact", views.ImpactViewSet)
router.register("eventnotification", views.EventNotificationViewSet)

urlpatterns = router.urls
