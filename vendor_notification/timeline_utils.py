"""
Timeline utilities for categorizing and formatting ObjectChange records.
"""

FIELD_DISPLAY_NAMES = {
    'name': 'Event ID',
    'summary': 'Summary',
    'status': 'Status',
    'start': 'Start Time',
    'end': 'End Time',
    'estimated_time_to_repair': 'Estimated Time to Repair',
    'acknowledged': 'Acknowledged',
    'internal_ticket': 'Internal Ticket',
    'comments': 'Comments',
    'original_timezone': 'Original Timezone',
    'provider': 'Provider',
    'impact': 'Impact Level',
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
    return field_name.replace('_', ' ').title()


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
    if changed_object_model == 'impact':
        return 'impact'

    if changed_object_model == 'eventnotification':
        return 'notification'

    # Handle field changes in maintenance/outage objects
    if action == 'update' and prechange_data and postchange_data:
        # Priority 1: Status changes
        if 'status' in postchange_data and prechange_data.get('status') != postchange_data.get('status'):
            return 'status'

        # Priority 2: Time changes
        time_fields = ['start', 'end', 'estimated_time_to_repair']
        for field in time_fields:
            if field in postchange_data and prechange_data.get(field) != postchange_data.get(field):
                return 'time'

        # Priority 3: Acknowledgment changes
        if 'acknowledged' in postchange_data and prechange_data.get('acknowledged') != postchange_data.get('acknowledged'):
            return 'acknowledgment'

    # Default: standard change
    return 'standard'
