"""Utility functions for iCal feed generation."""

import hashlib
import json


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
