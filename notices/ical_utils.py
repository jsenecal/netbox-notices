"""Utility functions for iCal feed generation."""

import hashlib
import json
from datetime import UTC, datetime, timedelta

from core.choices import ObjectChangeActionChoices
from core.models import ObjectChange
from django.contrib.contenttypes.models import ContentType
from django.db.models import Max
from django.utils import timezone
from icalendar import Calendar, Event


def get_ical_status(maintenance_status):
    """
    Map NetBox maintenance status to iCal STATUS property.

    Args:
        maintenance_status: NetBox maintenance status string

    Returns:
        iCal STATUS value (TENTATIVE, CONFIRMED, or CANCELLED)
    """
    if not maintenance_status:
        return "TENTATIVE"

    status_map = {
        "TENTATIVE": "TENTATIVE",
        "CONFIRMED": "CONFIRMED",
        "CANCELLED": "CANCELLED",
        "IN-PROCESS": "CONFIRMED",
        "COMPLETED": "CONFIRMED",
        "UNKNOWN": "TENTATIVE",
        "RE-SCHEDULED": "CANCELLED",
    }

    return status_map.get(maintenance_status, "TENTATIVE")


def calculate_etag(count, latest_modified, params, impact_count=0):
    """
    Calculate ETag for cache validation.

    Args:
        count: Number of maintenances in queryset
        latest_modified: Most recent last_updated datetime
        params: Dictionary of query parameters
        impact_count: Number of impacts on those maintenances -- impacts are
            rendered into the feed body, so adding or removing one must change
            the tag even when no maintenance row moved

    Returns:
        MD5 hash string for ETag header
    """
    # Sort params for deterministic hashing
    params_str = json.dumps(params, sort_keys=True)

    # Format datetime as ISO string or use 'none'
    modified_str = latest_modified.isoformat() if latest_modified else "none"

    # Combine all components
    etag_source = f"{params_str}-{modified_str}-{count}-{impact_count}"

    # Generate MD5 hash
    return hashlib.md5(etag_source.encode()).hexdigest()


def maintenance_window_cutoff(past_days):
    """
    The instant separating in-window from aged-out maintenances.

    Single source of the past_days membership rule: the feed queryset keeps
    events with start at or after this instant, and feed_last_modified treats
    everything before it as having exited the window.
    """
    return timezone.now() - timedelta(days=past_days)


def feed_last_modified(queryset, past_days):
    """
    Latest instant at which the feed body could have changed.

    A maintenance row's own last_updated is not enough: the feed also renders
    each event's impacts (DESCRIPTION) and provider (LOCATION), rows leave the
    feed when deleted, and rows age out of the past_days window with no data
    change at all. Each of those moments contributes a candidate here so the
    advertised Last-Modified never moves backwards when the body changed:

    - the matching maintenances', their impacts', and their providers'
      last_updated;
    - the latest logged deletion of a Maintenance or Impact (any deletion, not
      just ones matching this feed's filters: one spurious full download beats
      indefinite staleness, and the changelog does not record enough to scope
      it);
    - the latest window exit -- an event with start S leaves the feed at
      S + past_days, so the most recent exit is max(start) over the already
      excluded rows plus the window.

    Args:
        queryset: The filtered Maintenance queryset backing the feed
        past_days: The feed's window size in days

    Returns:
        An aware datetime, or None when nothing has ever been in the feed
    """
    from .models import Impact, Maintenance

    candidates = [
        value
        for value in queryset.aggregate(
            Max("last_updated"),
            Max("impacts__last_updated"),
            Max("provider__last_updated"),
        ).values()
        if value is not None
    ]

    content_types = ContentType.objects.get_for_models(Maintenance, Impact).values()
    latest_delete = ObjectChange.objects.filter(
        changed_object_type__in=list(content_types),
        action=ObjectChangeActionChoices.ACTION_DELETE,
    ).aggregate(Max("time"))["time__max"]
    if latest_delete is not None:
        candidates.append(latest_delete)

    latest_excluded_start = Maintenance.objects.filter(start__lt=maintenance_window_cutoff(past_days)).aggregate(
        Max("start")
    )["start__max"]
    if latest_excluded_start is not None:
        candidates.append(latest_excluded_start + timedelta(days=past_days))

    return max(candidates) if candidates else None


def generate_maintenance_ical(maintenances, request):
    """
    Generate iCalendar object from maintenance queryset.

    Args:
        maintenances: QuerySet or list of Maintenance objects
        request: Django request object for building URLs

    Returns:
        icalendar.Calendar object
    """
    # Create calendar
    cal = Calendar()
    cal.add("prodid", "-//NetBox Vendor Notification Plugin//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("x-wr-calname", "NetBox Maintenance Events")
    cal.add("x-wr-timezone", "UTC")
    cal.add("x-wr-caldesc", "Vendor maintenance events from NetBox")

    # Get domain for UID
    domain = request.META.get("HTTP_HOST", "netbox.local")

    # Add events
    for maintenance in maintenances:
        event = Event()

        # Required fields
        event.add("uid", f"maintenance-{maintenance.id}@{domain}")
        event.add("dtstamp", datetime.now(UTC))
        event.add("dtstart", maintenance.start)
        event.add("dtend", maintenance.end)
        event.add("summary", f"{maintenance.name} - {maintenance.summary}")

        # Status
        ical_status = get_ical_status(maintenance.status)
        event.add("status", ical_status)

        # Location (provider name)
        event.add("location", maintenance.provider.name)

        # Categories
        event.add("categories", [maintenance.status])

        # Description
        description_parts = [
            f"Provider: {maintenance.provider.name}",
            f"Status: {maintenance.status}",
        ]

        if maintenance.internal_ticket:
            description_parts.append(f"Internal Ticket: {maintenance.internal_ticket}")

        # Add impacts if available
        if hasattr(maintenance, "impacts") and maintenance.impacts.exists():
            description_parts.append("")
            description_parts.append("Affected Objects:")
            for impact in maintenance.impacts.all():
                impact_level = impact.impact or "UNKNOWN"
                description_parts.append(f"- {impact.target} ({impact_level})")

        # Add comments
        if maintenance.comments:
            description_parts.append("")
            description_parts.append("Comments:")
            description_parts.append(maintenance.comments)

        event.add("description", "\n".join(description_parts))

        # URL to maintenance detail page
        scheme = "https" if request.is_secure() else "http"
        url = f"{scheme}://{domain}{maintenance.get_absolute_url()}"
        event.add("url", url)

        cal.add_component(event)

    return cal
