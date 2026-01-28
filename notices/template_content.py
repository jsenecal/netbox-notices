"""Dynamic template extensions for event history."""

from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils import timezone
from netbox.config import get_config
from netbox.plugins import PluginTemplateExtension

from .models import Impact, Maintenance, Outage
from .utils import get_allowed_content_types


def _create_event_history_extensions():
    """
    Dynamically create PluginTemplateExtension classes for all
    allowed_content_types to show event history tables.

    Returns list of extension classes to register.
    """
    allowed_types = get_allowed_content_types()
    extensions = []

    def right_page_method(self):
        return render_event_history(self.context["object"])

    for content_type_str in allowed_types:
        app_label, model = content_type_str.lower().split(".")
        model_name = f"{app_label}.{model}"

        # Create extension class dynamically
        extension_class = type(
            f"{model.capitalize()}EventHistory",
            (PluginTemplateExtension,),
            {"models": [model_name], "right_page": right_page_method},
        )
        extensions.append(extension_class)

    return extensions


def render_event_history(obj):
    """
    Render event history for a given object.
    Queries maintenances and outages that impact this object.
    """
    config = get_config()
    days = config.PLUGINS_CONFIG.get("notices", {}).get("event_history_days", 30)
    cutoff_date = timezone.now() - timedelta(days=days)

    obj_ct = ContentType.objects.get_for_model(obj)

    # Get impacts for this object
    impacts = (
        Impact.objects.filter(target_content_type=obj_ct, target_object_id=obj.pk)
        .select_related("event_content_type")
        .prefetch_related("event")
    )

    # Filter to recent/future events
    maintenances = []
    outages = []

    for impact in impacts:
        event = impact.event
        if not event:
            continue

        # Include if: starts after cutoff OR ends in future OR has no end date
        include_event = False
        if event.start >= cutoff_date:
            include_event = True
        elif hasattr(event, "end") and event.end:
            if event.end >= timezone.now():
                include_event = True
        elif hasattr(event, "end") and not event.end:
            # Events with no end date (ongoing) should be included
            include_event = True

        if include_event:
            if impact.event_content_type.model == "maintenance":
                maintenances.append({"event": event, "impact": impact})
            elif impact.event_content_type.model == "outage":
                outages.append({"event": event, "impact": impact})

    # Only render if there are events to show
    if not maintenances and not outages:
        return ""

    return render_to_string(
        "notices/event_history_tabs.html",
        {
            "maintenances": maintenances,
            "outages": outages,
            "object": obj,
            "event_history_days": days,
        },
    )


def render_provider_events(provider):
    """
    Render maintenance and outage events for a provider.
    Shows all events linked to this provider.
    """
    config = get_config()
    days = config.PLUGINS_CONFIG.get("notices", {}).get("event_history_days", 30)
    cutoff_date = timezone.now() - timedelta(days=days)

    # Build filter: recent events OR future events OR ongoing (no end date)
    time_filter = Q(start__gte=cutoff_date) | Q(end__gte=timezone.now()) | Q(end__isnull=True)

    maintenances = list(
        Maintenance.objects.filter(provider=provider).filter(time_filter).order_by("-start").prefetch_related("impacts")
    )

    outages = list(
        Outage.objects.filter(provider=provider).filter(time_filter).order_by("-start").prefetch_related("impacts")
    )

    # Only render if there are events
    if not maintenances and not outages:
        return ""

    return render_to_string(
        "notices/provider_events.html",
        {
            "maintenances": maintenances,
            "outages": outages,
            "provider": provider,
            "event_history_days": days,
        },
    )


class ProviderEventsExtension(PluginTemplateExtension):
    """Show maintenance and outage events on Provider detail pages."""

    models = ["circuits.provider"]

    def right_page(self):
        return render_provider_events(self.context["object"])


# Create template extensions at module import time
# NetBox will auto-discover this via DEFAULT_RESOURCE_PATHS
template_extensions = _create_event_history_extensions() + [ProviderEventsExtension]
