from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Count
from django.shortcuts import render
from django.views.generic import View
from netbox.views import generic

from . import filtersets, forms, models, tables


# Maintenance Views
class MaintenanceView(generic.ObjectView):
    queryset = models.Maintenance.objects.prefetch_related("impacts").all()

    def get_extra_context(self, request, instance):
        # Load the maintenance event impact
        impact = models.Impact.objects.filter(
            event_content_type__model="maintenance", event_object_id=instance.pk
        )

        # Load the maintenance event notifications
        notification = models.EventNotification.objects.filter(
            event_content_type__model="maintenance", event_object_id=instance.pk
        )

        return {"impacts": impact, "notifications": notification}


class MaintenanceListView(generic.ObjectListView):
    queryset = models.Maintenance.objects.annotate(impact_count=Count("impacts"))
    table = tables.MaintenanceTable
    filterset = filtersets.MaintenanceFilterSet
    filterset_form = forms.MaintenanceFilterForm


class MaintenanceEditView(generic.ObjectEditView):
    queryset = models.Maintenance.objects.all()
    form = forms.MaintenanceForm


class MaintenanceDeleteView(generic.ObjectDeleteView):
    queryset = models.Maintenance.objects.all()


# Outage Views
class OutageListView(generic.ObjectListView):
    queryset = models.Outage.objects.all()
    table = tables.OutageTable
    filterset = filtersets.OutageFilterSet
    filterset_form = forms.OutageFilterForm


class OutageView(generic.ObjectView):
    queryset = models.Outage.objects.all()

    def get_extra_context(self, request, instance):
        # Load the outage event impact
        impact = models.Impact.objects.filter(
            event_content_type__model="outage", event_object_id=instance.pk
        )

        # Load the outage event notifications
        notification = models.EventNotification.objects.filter(
            event_content_type__model="outage", event_object_id=instance.pk
        )

        return {"impacts": impact, "notifications": notification}


class OutageEditView(generic.ObjectEditView):
    queryset = models.Outage.objects.all()
    form = forms.OutageForm


class OutageDeleteView(generic.ObjectDeleteView):
    queryset = models.Outage.objects.all()


# Impact views
class ImpactEditView(generic.ObjectEditView):
    queryset = models.Impact.objects.all()
    form = forms.ImpactForm


class ImpactDeleteView(generic.ObjectDeleteView):
    queryset = models.Impact.objects.all()


# Event Notification views
class EventNotificationEditView(generic.ObjectEditView):
    queryset = models.EventNotification.objects.all()
    form = forms.EventNotificationForm


class EventNotificationDeleteView(generic.ObjectDeleteView):
    queryset = models.EventNotification.objects.all()


class EventNotificationView(generic.ObjectView):
    queryset = models.EventNotification.objects.all()


# MaintenanceCalendar
class MaintenanceCalendarView(PermissionRequiredMixin, View):
    """
    Display maintenance events in an interactive FullCalendar view.
    Event data is loaded via AJAX from the REST API.
    """

    permission_required = "vendor_notification.view_maintenance"
    template_name = "vendor_notification/calendar.html"

    def get(self, request):
        return render(request, self.template_name, {"title": "Maintenance Calendar"})
