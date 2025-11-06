"""Utility functions for iCal feed generation."""

import hashlib
import json
from datetime import datetime, timezone as dt_timezone
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


def calculate_etag(count, latest_modified, params):
    """
    Calculate ETag for cache validation.

    Args:
        count: Number of maintenances in queryset
        latest_modified: Most recent last_updated datetime
        params: Dictionary of query parameters

    Returns:
        MD5 hash string for ETag header
    """
    # Sort params for deterministic hashing
    params_str = json.dumps(params, sort_keys=True)

    # Format datetime as ISO string or use 'none'
    modified_str = latest_modified.isoformat() if latest_modified else "none"

    # Combine all components
    etag_source = f"{params_str}-{modified_str}-{count}"

    # Generate MD5 hash
    return hashlib.md5(etag_source.encode()).hexdigest()


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
        event.add("dtstamp", datetime.now(dt_timezone.utc))
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
