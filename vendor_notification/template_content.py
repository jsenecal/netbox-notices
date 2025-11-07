"""Dynamic template extensions for event history."""

from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.template.loader import render_to_string
from django.utils import timezone
from netbox.config import get_config
from netbox.plugins import PluginTemplateExtension

from .models import Impact
from .utils import get_allowed_content_types


def create_event_history_extensions():
    """
    Dynamically create PluginTemplateExtension classes for all
    allowed_content_types to show event history tables.

    Returns list of extension classes to register.
    """
    allowed_types = get_allowed_content_types()
    extensions = []

    for content_type_str in allowed_types:
        app_label, model = content_type_str.lower().split(".")
        model_name = f"{app_label}.{model}"

        # Create a wrapper function to capture the model_name in closure
        def make_left_page_method(model_name):
            def left_page_method(self):
                return render_event_history(self.context["object"])

            return left_page_method

        # Create extension class dynamically
        extension_class = type(
            f"{model.capitalize()}EventHistory",
            (PluginTemplateExtension,),
            {"model": model_name, "left_page": make_left_page_method(model_name)},
        )
        extensions.append(extension_class)

    return extensions


def render_event_history(obj):
    """
    Render event history for a given object.
    Queries maintenances and outages that impact this object.
    """
    config = get_config()
    days = config.PLUGINS_CONFIG.get("vendor_notification", {}).get(
        "event_history_days", 30
    )
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
        "vendor_notification/event_history_tabs.html",
        {
            "maintenances": maintenances,
            "outages": outages,
            "object": obj,
            "event_history_days": days,
        },
    )
