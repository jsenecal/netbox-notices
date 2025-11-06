"""
Timeline utilities for categorizing and formatting ObjectChange records.
"""

from django.contrib.contenttypes.models import ContentType
from core.models import ObjectChange

FIELD_DISPLAY_NAMES = {
    "name": "Event ID",
    "summary": "Summary",
    "status": "Status",
    "start": "Start Time",
    "end": "End Time",
    "estimated_time_to_repair": "Estimated Time to Repair",
    "acknowledged": "Acknowledged",
    "internal_ticket": "Internal Ticket",
    "comments": "Comments",
    "original_timezone": "Original Timezone",
    "provider": "Provider",
    "impact": "Impact Level",
}


def get_field_display_name(field_name):
    """
    Get human-readable display name for a field.

    Args:
        field_name: Database field name

    Returns:
        Human-readable field name
    """
    if field_name in FIELD_DISPLAY_NAMES:
        return FIELD_DISPLAY_NAMES[field_name]

    # Fallback: replace underscores and title case
    return field_name.replace("_", " ").title()


def categorize_change(changed_object_model, action, prechange_data, postchange_data):
    """
    Categorize an ObjectChange based on what changed.

    Priority order (if multiple fields changed):
    1. Status changes
    2. Impact/Notification changes (structural)
    3. Time changes
    4. Acknowledgment changes
    5. Other fields

    Args:
        changed_object_model: Model name (e.g., 'maintenance', 'impact')
        action: 'create', 'update', or 'delete'
        prechange_data: Dict of field values before change (or None)
        postchange_data: Dict of field values after change (or None)

    Returns:
        Category string: 'status', 'impact', 'notification', 'acknowledgment', 'time', or 'standard'
    """
    # Handle related object changes
    if changed_object_model == "impact":
        return "impact"

    if changed_object_model == "eventnotification":
        return "notification"

    # Handle field changes in maintenance/outage objects
    if action == "update" and prechange_data and postchange_data:
        # Priority 1: Status changes
        if "status" in postchange_data and prechange_data.get(
            "status"
        ) != postchange_data.get("status"):
            return "status"

        # Priority 2: Time changes
        time_fields = ["start", "end", "estimated_time_to_repair"]
        for field in time_fields:
            if field in postchange_data and prechange_data.get(
                field
            ) != postchange_data.get(field):
                return "time"

        # Priority 3: Acknowledgment changes
        if "acknowledged" in postchange_data and prechange_data.get(
            "acknowledged"
        ) != postchange_data.get("acknowledged"):
            return "acknowledgment"

    # Default: standard change
    return "standard"


CATEGORY_ICONS = {
    "status": "check-circle",
    "impact": "alert-triangle",
    "notification": "mail",
    "acknowledgment": "check",
    "time": "clock",
    "standard": "circle",
}

CATEGORY_COLORS = {
    "status": "secondary",  # Default, actual color from status value
    "impact": "yellow",
    "notification": "blue",
    "acknowledgment": "green",
    "time": "orange",
    "standard": "secondary",
}


def get_category_icon(category):
    """
    Get Tabler icon name for a change category.

    Args:
        category: Category string

    Returns:
        Icon name (e.g., 'check-circle')
    """
    return CATEGORY_ICONS.get(category, "circle")


def get_category_color(category, status_value=None):
    """
    Get color class for a change category.

    For status changes, color is determined by the status value.
    For other categories, returns predefined color.

    Args:
        category: Category string
        status_value: Optional status value for status changes

    Returns:
        Color name (e.g., 'green', 'yellow')
    """
    if category == "status" and status_value:
        # Import here to avoid circular dependency
        from .choices import MaintenanceTypeChoices, OutageStatusChoices

        # Try maintenance status first, then outage
        color = MaintenanceTypeChoices.colors.get(status_value)
        if not color:
            color = OutageStatusChoices.colors.get(status_value)

        return color or "secondary"

    return CATEGORY_COLORS.get(category, "secondary")


def build_timeline_item(object_change, event_model_name):
    """
    Build enriched timeline item from ObjectChange record.

    Args:
        object_change: ObjectChange instance
        event_model_name: 'maintenance' or 'outage'

    Returns:
        Dict with timeline item data
    """
    changed_model = object_change.changed_object_type.model
    action = object_change.action
    prechange = object_change.prechange_data or {}
    postchange = object_change.postchange_data or {}

    # Categorize the change
    category = categorize_change(changed_model, action, prechange, postchange)

    # Get icon and color
    icon = get_category_icon(category)

    # For status changes, get color from new status value
    if category == "status":
        new_status = postchange.get("status")
        color = get_category_color(category, new_status)
    else:
        color = get_category_color(category)

    # Build title based on category and action
    title = _build_title(
        category,
        action,
        changed_model,
        object_change.object_repr,
        prechange,
        postchange,
    )

    # Extract all field changes
    changes = _extract_field_changes(prechange, postchange)

    # Get user info
    user = object_change.user
    user_name = (
        object_change.user_name
        if object_change.user_name
        else (user.username if user else "System")
    )

    return {
        "time": object_change.time,
        "user": user,
        "user_name": user_name,
        "category": category,
        "icon": icon,
        "color": color,
        "title": title,
        "changes": changes,
        "action": action,
        "object_repr": object_change.object_repr,
    }


def _build_title(category, action, model, object_repr, prechange, postchange):
    """Build human-readable title for timeline item."""
    if category == "status":
        new_status = postchange.get("status", "").replace("_", " ").title()
        return f"Status changed to {new_status}"

    elif category == "impact":
        if action == "create":
            return f"Impact added: {object_repr}"
        elif action == "delete":
            return f"Impact removed: {object_repr}"
        else:
            return f"Impact updated: {object_repr}"

    elif category == "notification":
        if action == "create":
            subject = postchange.get("subject", "Unknown")
            return f"Notification received: {subject}"
        return f"Notification {action}d"

    elif category == "acknowledgment":
        new_val = postchange.get("acknowledged", False)
        return "Event acknowledged" if new_val else "Acknowledgment removed"

    elif category == "time":
        time_fields = ["start", "end", "estimated_time_to_repair"]
        changed = [
            f
            for f in time_fields
            if f in postchange and prechange.get(f) != postchange.get(f)
        ]
        if len(changed) == 1:
            field_name = get_field_display_name(changed[0])
            return f"{field_name} updated"
        return "Event times updated"

    else:  # standard
        if action == "create":
            return f"{model.title()} created"
        elif action == "delete":
            return f"{model.title()} deleted"
        else:
            return "Event updated"


def _extract_field_changes(prechange, postchange):
    """
    Extract list of field changes from pre/post data.

    Returns:
        List of dicts with field, old_value, new_value, display_name
    """
    changes = []

    # Get all fields that changed
    all_fields = set(prechange.keys()) | set(postchange.keys())

    for field in sorted(all_fields):
        old_value = prechange.get(field)
        new_value = postchange.get(field)

        # Only include if actually changed
        if old_value != new_value:
            changes.append(
                {
                    "field": field,
                    "old_value": str(old_value) if old_value is not None else "Not set",
                    "new_value": str(new_value) if new_value is not None else "Not set",
                    "display_name": get_field_display_name(field),
                }
            )

    return changes


def get_timeline_changes(instance, model_class, limit=20):
    """
    Fetch ObjectChange records for an event and its related objects.

    Retrieves changes to the event itself (Maintenance or Outage) plus
    changes to related Impact and EventNotification objects.

    Args:
        instance: Maintenance or Outage instance
        model_class: Maintenance or Outage class
        limit: Maximum number of changes to return (default 20)

    Returns:
        List of ObjectChange records, sorted by time descending
    """
    content_type = ContentType.objects.get_for_model(model_class)

    # Direct changes to this object
    direct_changes = ObjectChange.objects.filter(
        changed_object_type=content_type, changed_object_id=instance.pk
    ).select_related("user")

    # Changes to related Impact/EventNotification objects
    # These have related_object pointing to our event
    related_changes = ObjectChange.objects.filter(
        related_object_type=content_type, related_object_id=instance.pk
    ).select_related("user")

    # Combine and sort by time
    all_changes = list(direct_changes) + list(related_changes)
    all_changes.sort(key=lambda x: x.time, reverse=True)

    return all_changes[:limit]
