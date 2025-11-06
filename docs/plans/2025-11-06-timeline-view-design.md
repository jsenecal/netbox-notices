# Timeline View Design for Maintenance and Outage Events

**Date:** 2025-11-06
**Status:** Approved Design
**Feature:** Event Change Timeline with Tabler UI

## Overview

Add a comprehensive timeline view at the bottom of maintenance and outage detail pages that displays the complete change history of events. The timeline combines NetBox's built-in change logging with intelligent categorization to highlight significant business events using Tabler UI's timeline component.

## Goals

- Provide complete audit trail of all changes to maintenance/outage events
- Highlight operationally significant changes (status, impacts, notifications, acknowledgments, time changes)
- Maintain chronological flow for understanding event progression
- Use consistent visual language (icons + colors) for quick scanning
- Leverage existing NetBox infrastructure (no new models required)

## Architecture & Data Model

### Data Sources

**Primary Source:** NetBox's `core.models.ObjectChange`
- Automatically captures all changes to Maintenance and Outage objects via `ChangeLoggingMixin`
- Provides: timestamp, user, action type (create/update/delete), pre/post change data (JSON diff)
- Already enabled on models inheriting from `NetBoxModel`

**Related Changes:** Changes to associated objects
- Impact objects (created/modified/deleted)
- EventNotification objects (created/modified/deleted)
- Linked via `related_object_type` and `related_object_id` fields

**No New Models Required:** All data already exists in NetBox's change logging system.

### Change Categories

Each `ObjectChange` record will be analyzed and categorized as one of:

1. **Status Changes** - `status` field modified
2. **Impact Changes** - Related `Impact` object created/deleted/modified
3. **Notification Arrivals** - Related `EventNotification` created
4. **Acknowledgment Toggles** - `acknowledged` field changed
5. **Time Modifications** - `start`/`end`/`estimated_time_to_repair` changed
6. **Standard Changes** - All other field modifications

## Visual Design & UX

### Timeline Placement

- Location: Bottom of detail pages (after "Received Notifications" section)
- Pages affected:
  - `vendor_notification/templates/vendor_notification/maintenance.html`
  - `vendor_notification/templates/vendor_notification/outage.html`
- Layout: Full-width card following existing Bootstrap grid pattern

### Tabler UI Timeline Structure

Using Tabler's standard timeline component pattern:

```html
<div class="row mb-3">
  <div class="col col-md-12">
    <div class="card">
      <h5 class="card-header">Event Timeline</h5>
      <div class="card-body">
        <ul class="timeline">
          <li class="timeline-event">
            <div class="timeline-event-icon bg-{color}-lt">
              <svg><!-- Icon --></svg>
            </div>
            <div class="card timeline-event-card">
              <div class="card-body">
                <div class="row">
                  <div class="col">
                    <h4 class="mb-1">{Change Title}</h4>
                    <div class="text-secondary mb-2">by {username}</div>
                  </div>
                  <div class="col-auto">
                    <div class="text-secondary">{timestamp}</div>
                  </div>
                </div>
                <div class="text-secondary">
                  {Change details}
                </div>
              </div>
            </div>
          </li>
          <!-- More timeline events -->
        </ul>
      </div>
    </div>
  </div>
</div>
```

### Visual Hierarchy by Category

| Category | Icon | Color Class | Use Case |
|----------|------|-------------|----------|
| Status Change | `check-circle` | Status-specific (green/yellow/red) | Status transitions |
| Impact Change | `alert-triangle` | `bg-yellow-lt` | Impact added/removed/modified |
| Notification | `mail` | `bg-blue-lt` | Notification received |
| Acknowledgment | `check` | `bg-green-lt` | Acknowledged toggled |
| Time Change | `clock` | `bg-orange-lt` | Start/end/ETR modified |
| Standard | `circle` | `bg-secondary-lt` | Other field changes |

### Timeline Card Content

Each timeline entry displays:

1. **Header Row:**
   - **Left:** Change title (e.g., "Status changed to CONFIRMED")
   - **Right:** Timestamp (muted, right-aligned)

2. **Attribution:** "by {username}" (muted text below title)

3. **Change Details:**
   - Field changes listed with old → new format
   - Example: `Status: TENTATIVE → CONFIRMED`
   - Multiple fields shown when changed together
   - Links to related objects (Impacts, Notifications)

4. **Complete Information:**
   - ALL field changes in an ObjectChange are displayed
   - Visual styling uses highest-priority change (see Priority section)
   - Description contains complete list of modifications

### Default Behavior

- **Display:** Most recent 20 changes by default
- **Order:** Reverse chronological (newest first)
- **Pagination:** "Load more" button if additional history exists (future enhancement)
- **Empty State:** "No changes recorded" message if no history

## Implementation Details

### Files to Create/Modify

**New File:**
- `vendor_notification/timeline_utils.py` - Timeline categorization and formatting logic

**Modified Files:**
- `vendor_notification/views.py` - Add timeline data to context
- `vendor_notification/templates/vendor_notification/maintenance.html` - Add timeline section
- `vendor_notification/templates/vendor_notification/outage.html` - Add timeline section

### Query Strategy

```python
from django.contrib.contenttypes.models import ContentType
from core.models import ObjectChange

def get_timeline_changes(instance, model_class, limit=20):
    """
    Fetch ObjectChange records for an event and its related objects.

    Args:
        instance: Maintenance or Outage object
        model_class: Maintenance or Outage class
        limit: Maximum number of changes to return

    Returns:
        List of ObjectChange records, sorted by time descending
    """
    content_type = ContentType.objects.get_for_model(model_class)

    # Direct changes to this object
    direct_changes = ObjectChange.objects.filter(
        changed_object_type=content_type,
        changed_object_id=instance.pk
    ).select_related('user')

    # Changes to related Impact/EventNotification objects
    related_changes = ObjectChange.objects.filter(
        related_object_type=content_type,
        related_object_id=instance.pk
    ).select_related('user')

    # Combine and sort
    all_changes = sorted(
        list(direct_changes) + list(related_changes),
        key=lambda x: x.time,
        reverse=True
    )

    return all_changes[:limit]
```

### Timeline Item Enrichment

Each `ObjectChange` is transformed into a timeline item dictionary:

```python
{
    'time': datetime,
    'user': User object or username string,
    'category': str,  # 'status', 'impact', 'notification', 'acknowledgment', 'time', 'standard'
    'icon': str,      # Tabler icon name
    'color': str,     # Bootstrap/Tabler color class
    'title': str,     # Human-readable change title
    'changes': [      # List of all field changes
        {
            'field': str,
            'old_value': str,
            'new_value': str,
            'display_name': str  # Human-readable field name
        }
    ],
    'related_object': dict or None,  # Optional link to Impact/Notification
    'action': str     # 'create', 'update', 'delete'
}
```

### Timeline Categorization Logic

#### 1. Status Changes
```python
if 'status' in postchange_data and prechange_data.get('status') != postchange_data.get('status'):
    category = 'status'
    icon = 'check-circle'
    old_status = prechange_data.get('status', 'N/A')
    new_status = postchange_data.get('status', 'N/A')

    # Use status-specific color
    if model_class == Maintenance:
        color = MaintenanceTypeChoices.colors.get(new_status, 'secondary')
    else:
        color = OutageStatusChoices.colors.get(new_status, 'secondary')

    title = f"Status changed to {new_status.replace('_', ' ').title()}"
```

#### 2. Impact Changes
```python
if change.changed_object_type.model == 'impact':
    category = 'impact'
    icon = 'alert-triangle'
    color = 'yellow'

    if change.action == ObjectChangeActionChoices.ACTION_CREATE:
        title = f"Impact added: {change.object_repr}"
    elif change.action == ObjectChangeActionChoices.ACTION_DELETE:
        title = f"Impact removed: {change.object_repr}"
    else:
        title = f"Impact updated: {change.object_repr}"
```

#### 3. Notification Changes
```python
if change.changed_object_type.model == 'eventnotification':
    category = 'notification'
    icon = 'mail'
    color = 'blue'

    if change.action == ObjectChangeActionChoices.ACTION_CREATE:
        subject = postchange_data.get('subject', 'Unknown')
        title = f"Notification received: {subject}"
```

#### 4. Acknowledgment Changes
```python
if 'acknowledged' in postchange_data and prechange_data.get('acknowledged') != postchange_data.get('acknowledged'):
    category = 'acknowledgment'
    icon = 'check'
    color = 'green'

    old_val = prechange_data.get('acknowledged', False)
    new_val = postchange_data.get('acknowledged', False)
    title = "Event acknowledged" if new_val else "Acknowledgment removed"
```

#### 5. Time/Date Changes
```python
time_fields = ['start', 'end', 'estimated_time_to_repair']
changed_time_fields = [f for f in time_fields if f in postchange_data]

if changed_time_fields:
    category = 'time'
    icon = 'clock'
    color = 'orange'

    if len(changed_time_fields) == 1:
        field = changed_time_fields[0]
        title = f"{field.replace('_', ' ').title()} time updated"
    else:
        title = "Event times updated"
```

#### 6. Standard Changes
All other field modifications fall into this category with neutral styling.

### Multi-Field Change Handling

When a single `ObjectChange` contains multiple field modifications:

**Priority Order (for visual styling):**
1. Status changes (highest priority)
2. Impact/Notification changes (structural)
3. Time changes
4. Acknowledgment changes
5. Other fields

**Display Strategy:**
- **Icon/Color:** Based on highest-priority change
- **Title:** Reflects primary change
- **Description:** Lists ALL changed fields with old → new values
- **No Information Lost:** Every field change is displayed

Example output for a change with status + acknowledged + comments:
```
Title: "Status changed to CONFIRMED"
Icon: check-circle (status icon)
Color: green (CONFIRMED color)
Details:
  - Status: TENTATIVE → CONFIRMED
  - Acknowledged: False → True
  - Comments: Updated with vendor response
```

### Field Display Names

Map database field names to human-readable labels:

```python
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
}
```

### Date/Time Formatting

- Use NetBox's standard date formatting helpers
- Show relative times for recent changes (e.g., "2 hours ago")
- Include absolute timestamp on hover
- Respect user's timezone preferences

## Testing Considerations

### Manual Testing Scenarios

1. **Create maintenance/outage** - Verify creation event appears
2. **Update status** - Verify status change highlighted correctly
3. **Add/remove impacts** - Verify impact events appear with links
4. **Receive notifications** - Verify notification events appear
5. **Toggle acknowledgment** - Verify acknowledgment events
6. **Modify times** - Verify time change events
7. **Multi-field update** - Verify all fields shown, correct priority
8. **No changes** - Verify empty state message

### Edge Cases

- **No user attribution** - Handle system-generated changes
- **Deleted related objects** - Show object_repr when actual object deleted
- **Very long field values** - Truncate with ellipsis
- **Null/empty values** - Display as "Not set" or "(empty)"
- **Timeline with 100+ changes** - Performance considerations for large histories

## Future Enhancements

**Phase 2 Potential Features:**
- Filtering by change category (show only status changes, etc.)
- Ajax-based "Load more" pagination
- Export timeline to PDF/CSV
- Real-time updates via WebSockets
- Timeline comparison between two events
- Bulk operation tracking (multiple events modified together)

## Security & Permissions

- Timeline visibility controlled by existing object view permissions
- User information displayed per NetBox's privacy settings
- No new permission checks required
- Change log data respects NetBox's changelog retention settings

## Performance Considerations

- Limit to 20 changes by default to avoid slow page loads
- Use `select_related('user')` for efficient queries
- Consider adding index on ObjectChange.related_object_type/related_object_id if query performance issues arise
- Template caching for icon SVG generation

## Documentation Updates

After implementation, update:
- Plugin README with timeline feature description
- User guide with timeline screenshots
- Developer docs with timeline_utils API reference

## Success Metrics

Implementation is successful when:
- All ObjectChange records display in timeline
- Highlighted categories use correct icons and colors
- Multi-field changes show complete information
- Timeline loads in < 500ms for typical events
- UI matches Tabler timeline component standards
- No regression in existing detail page functionality
