"""Utility functions for iCal feed generation."""


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
