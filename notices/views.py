from datetime import timedelta

from circuits.models import Provider
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Count
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseNotModified,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import View
from netbox.api.authentication import TokenAuthentication
from netbox.config import get_config
from netbox.views import generic
from rest_framework import exceptions

from . import filtersets, forms, models, tables
from .ical_utils import calculate_etag, generate_maintenance_ical
from .models import Maintenance, NotificationTemplate, Outage, PreparedNotification, SentNotification, TemplateScope
from .timeline_utils import build_timeline_item, get_timeline_changes


# Dashboard View
class DashboardView(PermissionRequiredMixin, View):
    """Summary dashboard showing event statistics and upcoming timeline."""

    permission_required = "notices.view_maintenance"
    template_name = "notices/dashboard.html"

    def get(self, request):
        now = timezone.now()
        week_end = now + timedelta(days=7)
        month_end = now + timedelta(days=30)

        # Active statuses
        maintenance_active = ["TENTATIVE", "CONFIRMED", "IN-PROCESS", "RE-SCHEDULED"]
        outage_active = ["REPORTED", "INVESTIGATING", "IDENTIFIED", "MONITORING"]

        # Stats
        maintenance_in_progress = models.Maintenance.objects.filter(status="IN-PROCESS").count()
        outage_active_count = models.Outage.objects.filter(status__in=outage_active).count()

        confirmed_this_week = models.Maintenance.objects.filter(
            status="CONFIRMED", start__gte=now, start__lte=week_end
        ).count()

        upcoming_7 = models.Maintenance.objects.filter(
            status__in=maintenance_active, start__gte=now, start__lte=week_end
        ).count()

        upcoming_30 = models.Maintenance.objects.filter(
            status__in=maintenance_active, start__gte=now, start__lte=month_end
        ).count()

        unacknowledged = (
            models.Maintenance.objects.filter(status__in=maintenance_active, acknowledged=False).count()
            + models.Outage.objects.filter(status__in=outage_active, acknowledged=False).count()
        )

        # Timeline: next 14 days of events
        timeline_end = now + timedelta(days=14)
        timeline_maintenance = (
            models.Maintenance.objects.filter(
                status__in=maintenance_active,
                start__lte=timeline_end,
                end__gte=now,
            )
            .select_related("provider")
            .annotate(impact_count=Count("impacts"))
            .order_by("start")[:20]
        )
        timeline_outages = (
            models.Outage.objects.filter(status__in=outage_active)
            .select_related("provider")
            .annotate(impact_count=Count("impacts"))
            .order_by("start")[:20]
        )

        # Upcoming by provider
        upcoming_by_provider = (
            models.Maintenance.objects.filter(
                status__in=["TENTATIVE", "CONFIRMED"],
                start__gte=now,
            )
            .select_related("provider")
            .order_by("provider__name", "start")[:50]
        )

        return render(
            request,
            self.template_name,
            {
                "maintenance_in_progress": maintenance_in_progress,
                "outage_active": outage_active_count,
                "confirmed_this_week": confirmed_this_week,
                "upcoming_7": upcoming_7,
                "upcoming_30": upcoming_30,
                "unacknowledged": unacknowledged,
                "timeline_maintenance": timeline_maintenance,
                "timeline_outages": timeline_outages,
                "upcoming_by_provider": upcoming_by_provider,
            },
        )


# Maintenance Views
class MaintenanceView(generic.ObjectView):
    queryset = models.Maintenance.objects.prefetch_related("impacts").all()

    def get_extra_context(self, request, instance):
        # Load the maintenance event impact
        impact = models.Impact.objects.filter(event_content_type__model="maintenance", event_object_id=instance.pk)

        # Load the maintenance event notifications
        notification = models.EventNotification.objects.filter(
            event_content_type__model="maintenance", event_object_id=instance.pk
        )

        # Load timeline changes
        object_changes = get_timeline_changes(instance, Maintenance, limit=20)
        timeline_items = [build_timeline_item(change, "maintenance") for change in object_changes]

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
        self.original_maintenance = get_object_or_404(models.Maintenance, pk=self.kwargs["pk"])

    def get_object(self, **kwargs):
        """
        Return a new unsaved instance pre-populated with original data.
        """
        # Create a new instance and copy data from original
        new_instance = models.Maintenance()

        # Clone all fields from original (except auto fields)
        for field in self.original_maintenance._meta.fields:
            if field.name not in ["id", "created", "last_updated"]:
                setattr(
                    new_instance,
                    field.name,
                    getattr(self.original_maintenance, field.name),
                )

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


class MaintenanceAcknowledgeView(PermissionRequiredMixin, View):
    """Quick action to acknowledge a maintenance."""

    permission_required = "notices.change_maintenance"

    def post(self, request, pk):
        maintenance = get_object_or_404(models.Maintenance, pk=pk)

        # Take a snapshot for change logging
        if hasattr(maintenance, "snapshot"):
            maintenance.snapshot()

        maintenance.acknowledged = True
        maintenance.save(update_fields=["acknowledged"])
        messages.success(request, f"Maintenance {maintenance.name} acknowledged.")

        # Redirect to return_url or maintenance detail
        return_url = request.POST.get("return_url") or request.GET.get("return_url") or maintenance.get_absolute_url()
        return redirect(return_url)


class MaintenanceCancelView(PermissionRequiredMixin, View):
    """Quick action to cancel a maintenance."""

    permission_required = "notices.change_maintenance"

    def get(self, request, pk):
        # Show confirmation page
        maintenance = get_object_or_404(models.Maintenance, pk=pk)
        return_url = request.GET.get("return_url") or maintenance.get_absolute_url()

        return render(
            request,
            "notices/maintenance_cancel.html",
            {
                "object": maintenance,
                "return_url": return_url,
            },
        )

    def post(self, request, pk):
        maintenance = get_object_or_404(models.Maintenance, pk=pk)

        # Don't allow cancelling already completed or cancelled maintenances
        if maintenance.status in ["COMPLETED", "CANCELLED"]:
            messages.error(
                request,
                f"Cannot cancel maintenance {maintenance.name} - it is already {maintenance.get_status_display()}.",
            )
        else:
            # Take a snapshot for change logging
            if hasattr(maintenance, "snapshot"):
                maintenance.snapshot()

            maintenance.status = "CANCELLED"
            maintenance.save(update_fields=["status"])
            messages.success(request, f"Maintenance {maintenance.name} cancelled.")

        # Redirect to return_url or maintenance detail
        return_url = request.POST.get("return_url") or request.GET.get("return_url") or maintenance.get_absolute_url()
        return redirect(return_url)


class MaintenanceMarkInProgressView(PermissionRequiredMixin, View):
    """Quick action to mark a maintenance as in-progress."""

    permission_required = "notices.change_maintenance"

    def post(self, request, pk):
        maintenance = get_object_or_404(models.Maintenance, pk=pk)

        # Don't allow marking completed or cancelled maintenances as in-progress
        if maintenance.status in ["COMPLETED", "CANCELLED"]:
            messages.error(
                request,
                f"Cannot mark maintenance {maintenance.name} as in-progress - "
                f"it is already {maintenance.get_status_display()}.",
            )
        else:
            # Take a snapshot for change logging
            if hasattr(maintenance, "snapshot"):
                maintenance.snapshot()

            maintenance.status = "IN-PROCESS"
            maintenance.save(update_fields=["status"])
            messages.success(request, f"Maintenance {maintenance.name} marked as in-progress.")

        # Redirect to return_url or maintenance detail
        return_url = request.POST.get("return_url") or request.GET.get("return_url") or maintenance.get_absolute_url()
        return redirect(return_url)


class MaintenanceMarkCompletedView(PermissionRequiredMixin, View):
    """Quick action to mark a maintenance as completed."""

    permission_required = "notices.change_maintenance"

    def post(self, request, pk):
        maintenance = get_object_or_404(models.Maintenance, pk=pk)

        # Don't allow marking cancelled maintenances as completed
        if maintenance.status == "CANCELLED":
            messages.error(
                request,
                f"Cannot mark maintenance {maintenance.name} as completed - it is cancelled.",
            )
        elif maintenance.status == "COMPLETED":
            messages.info(request, f"Maintenance {maintenance.name} is already completed.")
        else:
            # Take a snapshot for change logging
            if hasattr(maintenance, "snapshot"):
                maintenance.snapshot()

            maintenance.status = "COMPLETED"
            maintenance.save(update_fields=["status"])
            messages.success(request, f"Maintenance {maintenance.name} completed.")

        # Redirect to return_url or maintenance detail
        return_url = request.POST.get("return_url") or request.GET.get("return_url") or maintenance.get_absolute_url()
        return redirect(return_url)


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
        impact = models.Impact.objects.filter(event_content_type__model="outage", event_object_id=instance.pk)

        # Load the outage event notifications
        notification = models.EventNotification.objects.filter(
            event_content_type__model="outage", event_object_id=instance.pk
        )

        # Load timeline changes
        object_changes = get_timeline_changes(instance, Outage, limit=20)
        timeline_items = [build_timeline_item(change, "outage") for change in object_changes]

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
    filterset_form = forms.EventNotificationFilterForm


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
        token_placeholder = config.PLUGINS_CONFIG.get("notices", {}).get("ical_token_placeholder", "changeme")

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
        latest_modified = queryset.order_by("-last_updated").values_list("last_updated", flat=True).first()

        # Calculate ETag
        etag = calculate_etag(count=count, latest_modified=latest_modified, params=params)

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
            response["Last-Modified"] = latest_modified.strftime("%a, %d %b %Y %H:%M:%S GMT")
            return response

        # Generate iCal
        ical = generate_maintenance_ical(queryset, request)

        # Create response
        response = HttpResponse(ical.to_ical(), content_type="text/calendar; charset=utf-8")

        # Handle download vs subscription mode
        if request.GET.get("download", "").lower() in ("true", "1", "yes"):
            # Download mode: trigger file download with date-stamped filename
            filename = f"netbox-maintenance-{timezone.now().strftime('%Y-%m-%d')}.ics"
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
        else:
            # Subscription mode: set caching headers for feed readers
            config = get_config()
            cache_max_age = config.PLUGINS_CONFIG.get("notices", {}).get("ical_cache_max_age", 900)

            response["Cache-Control"] = f"public, max-age={cache_max_age}"
            response["ETag"] = etag

            if latest_modified:
                response["Last-Modified"] = latest_modified.strftime("%a, %d %b %Y %H:%M:%S GMT")

        return response

    def _authenticate_request(self, request):
        """
        Authenticate request using token (URL/header) or session.

        Returns authenticated user or None.
        """
        # Try 1: Token in URL parameter
        token_value = request.GET.get("token")
        if token_value:
            try:
                token = self._validate_url_token(token_value)
                return token.user
            except exceptions.AuthenticationFailed:
                return None

        # Try 2: Authorization header
        if not request.user.is_authenticated:
            try:
                authenticator = TokenAuthentication()
                auth_info = authenticator.authenticate(request)
                if auth_info:
                    return auth_info[0]
            except exceptions.AuthenticationFailed:
                return None

        # Try 3: Session authentication
        if request.user.is_authenticated:
            return request.user

        # No authentication
        if not settings.LOGIN_REQUIRED:
            # Allow anonymous if LOGIN_REQUIRED=False
            return request.user

        return None

    @staticmethod
    def _validate_url_token(token_value):
        """Validate a token passed as a URL query parameter.

        Supports both v1 (plaintext) and v2 (nbt_<key>.<plaintext>) formats.
        """
        from users.constants import TOKEN_PREFIX
        from users.models import Token

        qs = Token.objects.prefetch_related("user")

        if token_value.startswith(TOKEN_PREFIX):
            # v2 token: nbt_<key>.<plaintext>
            auth_value = token_value.removeprefix(TOKEN_PREFIX)
            try:
                key, plaintext = auth_value.split(".", 1)
            except ValueError:
                raise exceptions.AuthenticationFailed("Invalid token format")
            try:
                token = qs.get(version=2, key=key)
            except Token.DoesNotExist:
                raise exceptions.AuthenticationFailed("Invalid token")
            if not token.validate(plaintext):
                raise exceptions.AuthenticationFailed("Invalid token")
        else:
            # v1 token: direct plaintext lookup
            try:
                token = qs.get(version=1, plaintext=token_value)
            except Token.DoesNotExist:
                raise exceptions.AuthenticationFailed("Invalid token")

        if not token.enabled:
            raise exceptions.AuthenticationFailed("Token disabled")
        if token.is_expired:
            raise exceptions.AuthenticationFailed("Token expired")
        if not token.user.is_active:
            raise exceptions.AuthenticationFailed("User inactive")

        return token

    def _parse_query_params(self, request):
        """Parse and validate query parameters."""
        params = {}

        # past_days
        config = get_config()
        default_past_days = config.PLUGINS_CONFIG.get("notices", {}).get("ical_past_days_default", 30)

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


# NotificationTemplate Views
class NotificationTemplateListView(generic.ObjectListView):
    queryset = NotificationTemplate.objects.prefetch_related("scopes", "contact_roles")
    table = tables.NotificationTemplateTable
    filterset = filtersets.NotificationTemplateFilterSet
    filterset_form = forms.NotificationTemplateFilterForm


class NotificationTemplateView(generic.ObjectView):
    queryset = NotificationTemplate.objects.prefetch_related("scopes", "contact_roles", "children")

    def get_extra_context(self, request, instance):
        # Load scopes for this template
        scopes = instance.scopes.select_related("content_type").all()

        # Load child templates (if this is a base template)
        children = instance.children.all() if instance.is_base_template else []

        # Load prepared notifications using this template
        prepared_notifications = instance.prepared_notifications.select_related("approved_by").order_by("-created")[:10]

        return {
            "scopes": scopes,
            "children": children,
            "prepared_notifications": prepared_notifications,
        }


class NotificationTemplateEditView(generic.ObjectEditView):
    queryset = NotificationTemplate.objects.all()
    form = forms.NotificationTemplateForm


class NotificationTemplateDeleteView(generic.ObjectDeleteView):
    queryset = NotificationTemplate.objects.all()


# PreparedNotification Views
class PreparedNotificationListView(generic.ObjectListView):
    queryset = PreparedNotification.objects.select_related("template", "approved_by")
    table = tables.PreparedNotificationTable
    filterset = filtersets.PreparedNotificationFilterSet
    filterset_form = forms.PreparedNotificationFilterForm


class SentNotificationListView(generic.ObjectListView):
    """List view for sent/delivered notifications."""

    queryset = SentNotification.objects.select_related("template", "approved_by")
    table = tables.SentNotificationTable
    filterset = filtersets.PreparedNotificationFilterSet
    filterset_form = forms.SentNotificationFilterForm
    template_name = "notices/sent_list.html"


class SentNotificationView(generic.ObjectView):
    """Detail view for a sent notification."""

    queryset = SentNotification.objects.select_related("template", "approved_by").prefetch_related("contacts")
    template_name = "notices/preparednotification.html"

    def get_extra_context(self, request, instance):
        contacts = instance.contacts.all()
        return {
            "contacts": contacts,
        }


class PreparedNotificationView(generic.ObjectView):
    queryset = PreparedNotification.objects.select_related("template", "approved_by").prefetch_related("contacts")

    def get_extra_context(self, request, instance):
        # Load contacts
        contacts = instance.contacts.all()

        return {
            "contacts": contacts,
        }


class PreparedNotificationEditView(generic.ObjectEditView):
    queryset = PreparedNotification.objects.all()
    form = forms.PreparedNotificationForm


class PreparedNotificationDeleteView(generic.ObjectDeleteView):
    queryset = PreparedNotification.objects.all()


class PreparedNotificationBulkEditView(generic.BulkEditView):
    queryset = PreparedNotification.objects.all()
    filterset = filtersets.PreparedNotificationFilterSet
    table = tables.PreparedNotificationTable
    form = forms.PreparedNotificationBulkEditForm


class PreparedNotificationBulkDeleteView(generic.BulkDeleteView):
    queryset = PreparedNotification.objects.all()
    filterset = filtersets.PreparedNotificationFilterSet
    table = tables.PreparedNotificationTable


# TemplateScope Views
class TemplateScopeEditView(generic.ObjectEditView):
    """Add or edit a TemplateScope."""

    queryset = TemplateScope.objects.all()
    form = forms.TemplateScopeForm
    template_name = "notices/templatescope_edit.html"

    def alter_object(self, obj, request, url_args, url_kwargs):
        """Pre-populate template from URL parameter when adding new scope."""
        if not obj.pk and "template" in request.GET:
            template_id = request.GET.get("template")
            obj.template = get_object_or_404(NotificationTemplate, pk=template_id)
        return obj

    def get_return_url(self, request, obj=None):
        """Return to the parent NotificationTemplate after save."""
        if obj and obj.template:
            return obj.template.get_absolute_url()
        return super().get_return_url(request, obj)


class TemplateScopeDeleteView(generic.ObjectDeleteView):
    """Delete a TemplateScope."""

    queryset = TemplateScope.objects.all()

    def get_return_url(self, request, obj=None):
        """Return to the parent NotificationTemplate after delete."""
        if obj and obj.template:
            return obj.template.get_absolute_url()
        return super().get_return_url(request, obj)
