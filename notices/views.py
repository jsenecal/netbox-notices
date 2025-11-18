from datetime import timedelta
from django.conf import settings
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db import transaction
from django.db.models import Count
from django.http import (
    HttpResponse,
    HttpResponseForbidden,
    HttpResponseBadRequest,
    HttpResponseNotModified,
)
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.generic import View
from netbox.views import generic
from rest_framework import exceptions

from circuits.models import Provider
from netbox.api.authentication import TokenAuthentication
from netbox.config import get_config

from . import filtersets, forms, models, tables
from .ical_utils import generate_maintenance_ical, calculate_etag
from .timeline_utils import get_timeline_changes, build_timeline_item
from .models import Maintenance, Outage


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

        # Load timeline changes
        object_changes = get_timeline_changes(instance, Maintenance, limit=20)
        timeline_items = [
            build_timeline_item(change, "maintenance") for change in object_changes
        ]

        return {
            "impacts": impact,
            "notifications": notification,
            "timeline": timeline_items,
        }


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


class MaintenanceRescheduleView(generic.ObjectEditView):
    """
    Clone a maintenance and mark original as rescheduled.

    Workflow:
    1. Pre-fill form with existing maintenance data
    2. Set 'replaces' field to original maintenance
    3. On save, update original maintenance status to 'RE-SCHEDULED'
    """

    queryset = models.Maintenance.objects.all()
    form = forms.MaintenanceForm

    def setup(self, request, *args, **kwargs):
        """Store original maintenance during setup."""
        super().setup(request, *args, **kwargs)
        # Get original maintenance via URL parameter
        self.original_maintenance = get_object_or_404(
            models.Maintenance, pk=self.kwargs["pk"]
        )

    def get_object(self, **kwargs):
        """
        Return a new unsaved instance pre-populated with original data.
        """
        # Create a new instance and copy data from original
        new_instance = models.Maintenance()

        # Clone all fields from original (except auto fields)
        for field in self.original_maintenance._meta.fields:
            if field.name not in ["id", "created", "last_updated"]:
                setattr(new_instance, field.name, getattr(self.original_maintenance, field.name))

        # Set replaces to original and reset status
        new_instance.replaces = self.original_maintenance
        new_instance.status = "TENTATIVE"

        return new_instance

    def get_initial(self):
        """
        Additional initial data for the form.
        """
        initial = super().get_initial()
        # The object already has the data, but ensure replaces is set in initial too
        initial["replaces"] = self.original_maintenance.pk
        return initial

    def form_valid(self, form):
        """
        Save new maintenance.

        Note: The original maintenance status is automatically updated to RE-SCHEDULED
        via a post_save signal handler when a new maintenance with replaces field is saved.
        """
        return super().form_valid(form)

    def get_extra_context(self, request, instance):
        """Add original maintenance to context."""
        context = super().get_extra_context(request, instance)
        context["original_maintenance"] = self.original_maintenance
        return context


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

        # Load timeline changes
        object_changes = get_timeline_changes(instance, Outage, limit=20)
        timeline_items = [
            build_timeline_item(change, "outage") for change in object_changes
        ]

        return {
            "impacts": impact,
            "notifications": notification,
            "timeline": timeline_items,
        }


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
class EventNotificationListView(generic.ObjectListView):
    queryset = models.EventNotification.objects.all()
    table = tables.EventNotificationTable
    filterset = filtersets.EventNotificationFilterSet


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

    permission_required = "notices.view_maintenance"
    template_name = "notices/calendar.html"

    def get(self, request):
        from netbox.config import get_config

        config = get_config()
        token_placeholder = config.PLUGINS_CONFIG.get("notices", {}).get(
            "ical_token_placeholder", "changeme"
        )

        return render(
            request,
            self.template_name,
            {
                "title": "Maintenance Calendar",
                "ical_token_placeholder": token_placeholder,
            },
        )


class MaintenanceICalView(View):
    """
    Generate iCal feed of maintenance events.

    Supports three authentication methods:
    1. Token in URL (?token=xxx)
    2. Authorization header (Token xxx)
    3. Session authentication (browser)

    Query parameters:
    - token: API token for authentication
    - past_days: Days in past to include (default from settings)
    - provider: Provider slug to filter by
    - provider_id: Provider ID to filter by
    - status: Comma-separated status list
    """

    def get(self, request):
        # Authenticate user
        user = self._authenticate_request(request)
        if not user:
            return HttpResponseForbidden("Authentication required")

        # Check permission
        if not user.has_perm("notices.view_maintenance"):
            return HttpResponseForbidden("Permission denied")

        # Parse and validate query parameters
        try:
            params = self._parse_query_params(request)
        except ValueError as e:
            return HttpResponseBadRequest(str(e))

        # Build filtered queryset
        try:
            queryset = self._build_queryset(params)
        except ValueError as e:
            return HttpResponseBadRequest(str(e))

        # Get cache-related info
        count = queryset.count()
        latest_modified = (
            queryset.order_by("-last_updated")
            .values_list("last_updated", flat=True)
            .first()
        )

        # Calculate ETag
        etag = calculate_etag(
            count=count, latest_modified=latest_modified, params=params
        )

        # Check If-None-Match (ETag)
        if request.META.get("HTTP_IF_NONE_MATCH") == etag:
            response = HttpResponseNotModified()
            response["ETag"] = etag
            return response

        # Check If-Modified-Since
        if latest_modified and "HTTP_IF_MODIFIED_SINCE" in request.META:
            # Parse If-Modified-Since header (simplified)
            # In production, use proper HTTP date parsing
            response = HttpResponseNotModified()
            response["ETag"] = etag
            response["Last-Modified"] = latest_modified.strftime(
                "%a, %d %b %Y %H:%M:%S GMT"
            )
            return response

        # Generate iCal
        ical = generate_maintenance_ical(queryset, request)

        # Create response
        response = HttpResponse(
            ical.to_ical(), content_type="text/calendar; charset=utf-8"
        )

        # Handle download vs subscription mode
        if request.GET.get("download", "").lower() in ("true", "1", "yes"):
            # Download mode: trigger file download with date-stamped filename
            filename = f"netbox-maintenance-{timezone.now().strftime('%Y-%m-%d')}.ics"
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
        else:
            # Subscription mode: set caching headers for feed readers
            config = get_config()
            cache_max_age = config.PLUGINS_CONFIG.get("notices", {}).get(
                "ical_cache_max_age", 900
            )

            response["Cache-Control"] = f"public, max-age={cache_max_age}"
            response["ETag"] = etag

            if latest_modified:
                response["Last-Modified"] = latest_modified.strftime(
                    "%a, %d %b %Y %H:%M:%S GMT"
                )

        return response

    def _authenticate_request(self, request):
        """
        Authenticate request using token (URL/header) or session.

        Returns authenticated user or None.
        """
        # Try 1: Token in URL parameter
        token_key = request.GET.get("token")
        if token_key:
            try:
                authenticator = TokenAuthentication()
                user, token = authenticator.authenticate_credentials(token_key)
                return user
            except exceptions.AuthenticationFailed:
                return None

        # Try 2: Authorization header
        if not request.user.is_authenticated:
            authenticator = TokenAuthentication()
            auth_info = authenticator.authenticate(request)
            if auth_info:
                return auth_info[0]

        # Try 3: Session authentication
        if request.user.is_authenticated:
            return request.user

        # No authentication
        if not settings.LOGIN_REQUIRED:
            # Allow anonymous if LOGIN_REQUIRED=False
            return request.user

        return None

    def _parse_query_params(self, request):
        """Parse and validate query parameters."""
        params = {}

        # past_days
        config = get_config()
        default_past_days = config.PLUGINS_CONFIG.get("notices", {}).get(
            "ical_past_days_default", 30
        )

        try:
            past_days = int(request.GET.get("past_days", default_past_days))
            if past_days < 0:
                past_days = default_past_days
            if past_days > 365:
                raise ValueError("past_days cannot exceed 365")
            params["past_days"] = past_days
        except (ValueError, TypeError):
            params["past_days"] = default_past_days

        # provider / provider_id
        if "provider" in request.GET:
            params["provider"] = request.GET["provider"]
        elif "provider_id" in request.GET:
            params["provider_id"] = request.GET["provider_id"]

        # status
        if "status" in request.GET:
            params["status"] = request.GET["status"]

        return params

    def _build_queryset(self, params):
        """Build filtered Maintenance queryset."""
        # Base queryset with time filter
        cutoff_date = timezone.now() - timedelta(days=params["past_days"])
        queryset = models.Maintenance.objects.filter(start__gte=cutoff_date)

        # Optimize queries
        queryset = queryset.select_related("provider").prefetch_related("impacts")

        # Filter by provider
        if "provider" in params:
            try:
                provider = Provider.objects.get(slug=params["provider"])
                queryset = queryset.filter(provider=provider)
            except Provider.DoesNotExist:
                raise ValueError(f"Provider not found: {params['provider']}")

        elif "provider_id" in params:
            try:
                provider_id = int(params["provider_id"])
                queryset = queryset.filter(provider_id=provider_id)
            except (ValueError, TypeError):
                raise ValueError(f"Invalid provider_id: {params['provider_id']}")

        # Filter by status
        if "status" in params:
            from .choices import MaintenanceTypeChoices

            status_list = [s.strip().upper() for s in params["status"].split(",")]
            # Validate statuses
            valid_statuses = [choice[0] for choice in MaintenanceTypeChoices.CHOICES]
            filtered_statuses = [s for s in status_list if s in valid_statuses]

            if filtered_statuses:
                queryset = queryset.filter(status__in=filtered_statuses)

        return queryset
