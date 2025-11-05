# Calendar FullCalendar Redesign

**Date:** 2025-11-05
**Status:** Approved
**Pattern:** FullCalendar.js with NetBox REST API

## Overview

Replace the custom Python HTMLCalendar implementation with FullCalendar.js to properly display multi-day maintenance events. The current calendar only shows events on their first and last days, not the days in between. FullCalendar natively handles multi-day event rendering and provides better UX with modals for event details.

## Problem Statement

**Current Issues:**
1. Events spanning multiple days only appear on start day and end day (not days 2-4 of a 5-day event)
2. Custom Python calendar code (~110 lines) is hard to maintain
3. Clicking events navigates away (no quick preview)
4. Limited interaction capabilities

**Root Cause:**
```python
# views.py:152 - only matches start or end day
events_from_day = events.filter(Q(start__day=day) | Q(end__day=day))
```

## Design Goals

1. **Proper multi-day rendering** - Events appear on all days they span
2. **Modal preview** - Click events to see details without navigation
3. **Follow NetBox patterns** - Use existing REST API with standard filterset operators
4. **Simplify maintenance** - Replace custom Python calendar with proven library
5. **Bundle dependencies** - Include FullCalendar.js files with plugin (no CDN)

## Architecture Overview

### High-Level Architecture

**Component Flow:**
1. User navigates to `/plugins/vendor-notification/maintenance/calendar/`
2. Django view renders template with empty `<div id="calendar"></div>` and modal container
3. JavaScript initializes FullCalendar with API configuration
4. FullCalendar makes GET request to `/api/plugins/vendor-notification/maintenance/?end__gte=YYYY-MM-DD&start__lte=YYYY-MM-DD&limit=0`
5. API returns JSON array of maintenance events (uses existing serializer + status_color field)
6. JavaScript transforms response to FullCalendar event format
7. FullCalendar renders events spanning multiple days automatically
8. User clicks event → JavaScript opens Bootstrap modal with event details
9. User navigates months → FullCalendar automatically fetches new date range

**Key Benefits:**
- FullCalendar handles multi-day event rendering natively
- Uses NetBox's built-in `__gte` and `__lte` operators (no custom filterset code)
- Automatic API calls on navigation
- Clean separation: API provides data, FullCalendar handles UI

### Technology Stack

- **Frontend Library:** FullCalendar v6.x (bundled with plugin)
- **Modal Framework:** Bootstrap 5 (already in Tabler/NetBox)
- **API Pattern:** NetBox REST API with existing MaintenanceViewSet
- **Date Filtering:** NetBox's built-in DateTimeField operators (`__gte`, `__lte`)

## Implementation Details

### 1. API Layer - No Changes to FilterSet Needed

**Existing FilterSet:**
```python
# vendor_notification/filtersets.py
class MaintenanceFilterSet(NetBoxModelFilterSet):
    class Meta:
        model = Maintenance
        fields = (
            "id", "name", "summary", "status", "provider",
            "start",  # Automatically provides start__gte, start__lte, etc.
            "end",    # Automatically provides end__gte, end__lte, etc.
            ...
        )
```

NetBox automatically provides these operators for DateTimeField:
- `start__gte` - events starting on or after date
- `start__lte` - events starting on or before date
- `end__gte` - events ending on or after date
- `end__lte` - events ending on or before date

**Query Pattern for Overlap Detection:**
```
GET /api/plugins/vendor-notification/maintenance/?end__gte=2025-11-01&start__lte=2025-11-30&limit=0
```

Returns events where:
- `end >= 2025-11-01` (events ending on or after range start)
- AND `start <= 2025-11-30` (events starting on or before range end)

**Serializer Enhancement:**

Add `status_color` field to expose `get_status_color()` method:

```python
# vendor_notification/api/serializers.py
class MaintenanceSerializer(NetBoxModelSerializer):
    status_color = serializers.CharField(
        source='get_status_color',
        read_only=True
    )

    class Meta:
        model = models.Maintenance
        fields = [
            'id', 'url', 'display', 'name', 'summary', 'provider',
            'start', 'end', 'status', 'status_color',  # Add status_color
            'original_timezone', 'internal_ticket', 'acknowledged',
            'comments', 'tags', 'created', 'last_updated'
        ]
```

**Benefits:**
- Single source of truth for colors (Python model method)
- No duplicate color mapping in JavaScript
- Consistent with existing badge colors

### 2. Static File Organization

**Directory Structure:**
```
vendor_notification/static/vendor_notification/
├── js/
│   ├── fullcalendar/
│   │   ├── index.global.min.js  (FullCalendar v6.x core, ~250KB)
│   │   └── LICENSE.txt
│   └── calendar.js  (our custom calendar initialization)
└── css/
    └── fullcalendar/
        └── index.min.css  (FullCalendar styles)
```

**FullCalendar Files:**
- Download from: https://github.com/fullcalendar/fullcalendar/releases
- Use `index.global.min.js` (includes all views)
- Include LICENSE.txt for MIT license compliance

### 3. JavaScript Implementation

**File:** `vendor_notification/static/vendor_notification/js/calendar.js`

```javascript
// Initialize FullCalendar when page loads
document.addEventListener('DOMContentLoaded', function() {
    const calendarEl = document.getElementById('calendar');

    const calendar = new FullCalendar.Calendar(calendarEl, {
        // Basic settings
        initialView: 'dayGridMonth',
        headerToolbar: {
            left: 'prev,next today',
            center: 'title',
            right: 'dayGridMonth,dayGridWeek'
        },

        // Event data source - FullCalendar handles the API calls automatically
        events: {
            url: '/api/plugins/vendor-notification/maintenance/',
            extraParams: function(fetchInfo) {
                return {
                    // Use NetBox's built-in operators for date range filtering
                    end__gte: fetchInfo.startStr.split('T')[0],    // Events ending on or after range start
                    start__lte: fetchInfo.endStr.split('T')[0],    // Events starting on or before range end
                    limit: 0  // No pagination, get all events in range
                };
            },
            success: function(data) {
                // Transform NetBox API response to FullCalendar event format
                return data.results.map(event => ({
                    id: event.id,
                    title: `${event.name} - ${event.provider.display}`,
                    start: event.start,
                    end: event.end,
                    backgroundColor: `var(--tblr-${event.status_color})`,  // Use Tabler CSS variables
                    borderColor: `var(--tblr-${event.status_color})`,
                    extendedProps: {
                        status: event.status,
                        provider: event.provider.display,
                        summary: event.summary,
                        comments: event.comments,
                        url: event.url
                    }
                }));
            }
        },

        // Click handler - opens modal instead of navigating
        eventClick: function(info) {
            info.jsEvent.preventDefault(); // Don't follow URL
            showEventModal(info.event);
        },

        // Display multi-day events properly
        displayEventTime: true,
        displayEventEnd: true
    });

    calendar.render();
});

// Show event details in Bootstrap modal
function showEventModal(event) {
    const modal = new bootstrap.Modal(document.getElementById('eventModal'));

    // Populate modal fields
    document.getElementById('eventModalTitle').textContent = event.title;
    document.getElementById('eventModalProvider').textContent = event.extendedProps.provider;
    document.getElementById('eventModalSummary').textContent = event.extendedProps.summary;

    // Format dates
    document.getElementById('eventModalStart').textContent =
        new Date(event.start).toLocaleString();
    document.getElementById('eventModalEnd').textContent =
        new Date(event.end).toLocaleString();

    // Status badge with color from backend
    const statusBadge = document.getElementById('eventModalStatus');
    statusBadge.textContent = event.extendedProps.status;
    statusBadge.className = `badge bg-${event.backgroundColor.replace('var(--tblr-', '').replace(')', '')}`;

    // Comments (optional field)
    const commentsRow = document.getElementById('eventModalCommentsRow');
    if (event.extendedProps.comments) {
        document.getElementById('eventModalComments').textContent = event.extendedProps.comments;
        commentsRow.style.display = 'flex';
    } else {
        commentsRow.style.display = 'none';
    }

    // Link to full detail page
    document.getElementById('eventModalViewLink').href = event.extendedProps.url;

    modal.show();
}
```

**Key Features:**
- FullCalendar automatically manages date range and makes API calls when navigating months
- Transform function maps NetBox API response to FullCalendar's expected format
- Multi-day events automatically span across days (FullCalendar handles rendering)
- Event click opens modal instead of navigating
- Uses backend `status_color` with Tabler CSS variables for consistency

### 4. Template Implementation

**File:** `vendor_notification/templates/vendor_notification/calendar.html`

```django
{% extends 'generic/_base.html' %}
{% load static %}

{% block title %}Maintenance Calendar{% endblock %}

{% block css %}
<link href="{% static 'vendor_notification/css/fullcalendar/index.min.css' %}" rel="stylesheet">
{% endblock %}

{% block content %}
<div id="calendar"></div>

<!-- Event Detail Modal (Tabler/Bootstrap pattern) -->
<div class="modal modal-blur fade" id="eventModal" tabindex="-1" role="dialog" aria-hidden="true">
    <div class="modal-dialog modal-lg modal-dialog-centered" role="document">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title" id="eventModalTitle"></h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
                <div class="row mb-3">
                    <div class="col-12">
                        <span id="eventModalStatus" class="badge"></span>
                    </div>
                </div>
                <div class="row mb-2">
                    <div class="col-4"><strong>Provider:</strong></div>
                    <div class="col-8" id="eventModalProvider"></div>
                </div>
                <div class="row mb-2">
                    <div class="col-4"><strong>Start:</strong></div>
                    <div class="col-8" id="eventModalStart"></div>
                </div>
                <div class="row mb-2">
                    <div class="col-4"><strong>End:</strong></div>
                    <div class="col-8" id="eventModalEnd"></div>
                </div>
                <div class="row mb-2">
                    <div class="col-4"><strong>Summary:</strong></div>
                    <div class="col-8" id="eventModalSummary"></div>
                </div>
                <div class="row mb-2" id="eventModalCommentsRow" style="display: none;">
                    <div class="col-4"><strong>Comments:</strong></div>
                    <div class="col-8" id="eventModalComments"></div>
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                <a id="eventModalViewLink" href="#" class="btn btn-primary">View Full Details</a>
            </div>
        </div>
    </div>
</div>
{% endblock %}

{% block javascript %}
<script src="{% static 'vendor_notification/js/fullcalendar/index.global.min.js' %}"></script>
<script src="{% static 'vendor_notification/js/calendar.js' %}"></script>
{% endblock %}
```

**Modal Features:**
- Uses Bootstrap 5 modal (included in Tabler/NetBox)
- Shows: name, provider, status (with color badge), times, summary, comments (if present)
- "View Full Details" button links to maintenance detail page
- Follows Tabler modal pattern

### 5. Django View Simplification

**File:** `vendor_notification/views.py`

**Remove:**
- `Calendar` class (lines 102-211) - custom HTMLCalendar implementation
- `MaintenanceScheduleView` complex logic

**Replace with:**
```python
class MaintenanceCalendarView(PermissionRequiredMixin, View):
    """
    Display maintenance events in an interactive FullCalendar view.
    Event data is loaded via AJAX from the REST API.
    """
    permission_required = 'vendor_notification.view_maintenance'
    template_name = 'vendor_notification/calendar.html'

    def get(self, request):
        return render(request, self.template_name, {
            'title': 'Maintenance Calendar'
        })
```

**Benefits:**
- Remove ~110 lines of custom Python calendar rendering code
- View becomes a simple template renderer
- All calendar logic handled client-side by FullCalendar
- Much easier to maintain

### 6. URL Configuration

**File:** `vendor_notification/urls.py`

```python
urlpatterns = [
    # ... existing patterns ...

    # Calendar view
    path('maintenance/calendar/', views.MaintenanceCalendarView.as_view(), name='maintenance_calendar'),

    # ... other patterns ...
]
```

**URL:** `/plugins/vendor-notification/maintenance/calendar/`

### 7. Navigation Menu

**File:** `vendor_notification/navigation.py`

Ensure calendar link exists in menu:

```python
from netbox.plugins import PluginMenuItem

menu_items = (
    PluginMenuItem(
        link='plugins:vendor_notification:maintenance_list',
        link_text='Maintenances',
        permissions=['vendor_notification.view_maintenance']
    ),
    PluginMenuItem(
        link='plugins:vendor_notification:maintenance_calendar',
        link_text='Calendar',
        permissions=['vendor_notification.view_maintenance']
    ),
    # ... other menu items ...
)
```

## Data Flow

### Page Load Sequence

1. **User navigates to calendar URL**
   - Browser requests: `GET /plugins/vendor-notification/maintenance/calendar/`

2. **Django renders template**
   - Loads FullCalendar CSS and JS libraries
   - Renders empty `<div id="calendar"></div>`
   - Renders hidden modal HTML structure
   - Loads custom `calendar.js`

3. **JavaScript initializes**
   - `DOMContentLoaded` event fires
   - FullCalendar.Calendar instantiated with config
   - `calendar.render()` called

4. **FullCalendar fetches data**
   - Makes AJAX request: `GET /api/plugins/vendor-notification/maintenance/?end__gte=2025-11-01&start__lte=2025-11-30&limit=0`
   - API returns JSON with `results` array

5. **Data transformation**
   - `success` callback transforms each event to FullCalendar format
   - Applies colors from backend `status_color` field
   - Stores extra data in `extendedProps`

6. **Calendar renders**
   - FullCalendar displays events spanning multiple days
   - Events color-coded by status

### User Interaction Flow

**Month Navigation:**
1. User clicks prev/next month
2. FullCalendar automatically calculates new date range
3. Makes new API call with updated `end__gte` and `start__lte` params
4. Transforms and renders new events

**Event Click:**
1. User clicks event
2. `eventClick` callback fires
3. `preventDefault()` stops navigation
4. `showEventModal()` function called
5. Modal populated with event data from `extendedProps`
6. Bootstrap modal displayed
7. User can click "View Full Details" to navigate to detail page

## Migration Path

### Backward Compatibility

**No Breaking Changes:**
- Existing API endpoints unchanged
- Existing serializers extended (additive change)
- New view, doesn't replace any existing functionality
- Menu adds new item, doesn't remove existing links

### Deprecation

**Files to Remove:**
- Old `Calendar` class in `views.py` (lines 102-211)
- Old `MaintenanceScheduleView` if different from new one

**Files to Keep:**
- All existing models, serializers, filtersets
- All other views and templates

### Migration Steps

1. Add `status_color` field to serializer
2. Add static files (FullCalendar library + custom JS)
3. Create new template with modal
4. Replace view class
5. Update URL routing (keep same name `maintenance_calendar`)
6. Test calendar rendering and API calls
7. Deploy

No database migrations required - all changes are frontend/API.

## Testing Strategy

### Manual Testing Checklist

1. **Calendar Rendering**
   - [ ] Calendar loads without errors
   - [ ] Current month displayed by default
   - [ ] Navigation buttons (prev/next/today) work
   - [ ] Multi-day events span all days correctly
   - [ ] Single-day events display properly

2. **API Integration**
   - [ ] API calls made with correct parameters (`end__gte`, `start__lte`, `limit=0`)
   - [ ] Events filtered correctly by date range
   - [ ] Status colors match existing badge colors
   - [ ] All event fields populated correctly

3. **Event Interaction**
   - [ ] Click event opens modal (doesn't navigate)
   - [ ] Modal shows all fields: name, provider, status, times, summary
   - [ ] Comments field hidden when empty
   - [ ] Status badge color matches event color
   - [ ] "View Full Details" link navigates to maintenance detail page

4. **Edge Cases**
   - [ ] Month with no events displays empty calendar
   - [ ] Events spanning month boundaries display correctly
   - [ ] Very long event names truncate/wrap appropriately
   - [ ] Multiple events on same day display stacked

5. **Browser Compatibility**
   - [ ] Chrome/Edge (modern)
   - [ ] Firefox (modern)
   - [ ] Safari (modern)

6. **Permissions**
   - [ ] Users without `view_maintenance` permission cannot access calendar
   - [ ] Calendar link hidden in menu for users without permission

### Automated Testing

**API Tests:**
```python
# Test date range filtering
response = self.client.get(
    '/api/plugins/vendor-notification/maintenance/',
    {'end__gte': '2025-11-01', 'start__lte': '2025-11-30', 'limit': 0}
)
self.assertEqual(response.status_code, 200)
# Verify events overlap the range

# Test serializer includes status_color
maintenance = Maintenance.objects.create(...)
serializer = MaintenanceSerializer(maintenance)
self.assertIn('status_color', serializer.data)
self.assertEqual(serializer.data['status_color'], 'yellow')
```

**View Tests:**
```python
# Test calendar view accessible
response = self.client.get('/plugins/vendor-notification/maintenance/calendar/')
self.assertEqual(response.status_code, 200)
self.assertContains(response, 'id="calendar"')
self.assertContains(response, 'fullcalendar')
```

## Performance Considerations

### API Performance

**Query Optimization:**
- Date range filtering uses indexed `start` and `end` fields
- `limit=0` removes pagination overhead for small datasets
- Consider adding `select_related('provider')` to queryset if not already present

**Expected Load:**
- Typical month: 10-50 maintenance events
- Response size: ~5-20KB JSON
- One API call per month navigation

**Optimization for Large Datasets:**
If calendar becomes slow with many events (>1000 per month):
1. Add pagination back and implement FullCalendar's lazy loading
2. Add database indexes on `start` and `end` if not already present
3. Cache API responses by month

### Frontend Performance

**FullCalendar Bundle Size:**
- `index.global.min.js`: ~250KB (gzipped: ~70KB)
- `index.min.css`: ~40KB (gzipped: ~8KB)
- `calendar.js`: ~5KB
- Total: ~295KB (~80KB gzipped)

**Initial Load Time:**
- First visit: ~300KB download + API call (~5-20KB)
- Subsequent visits: Cached assets + API call only

**Rendering Performance:**
- FullCalendar efficiently handles 100+ events per month
- Browser caching reduces repeat visit load time

## Security Considerations

### API Security

**Existing Protection (via NetBox):**
- Authentication required (NetBox session/token)
- Permission check: `vendor_notification.view_maintenance`
- CSRF protection on state-changing requests (N/A for GET)

**No New Vulnerabilities:**
- Read-only API access (GET requests only)
- No new endpoints (uses existing REST API)
- No user input processed server-side

### Frontend Security

**XSS Prevention:**
- Event data inserted using DOM methods (`textContent`, not `innerHTML`)
- No `eval()` or dangerous HTML construction
- FullCalendar library handles user data safely

**Modal Content:**
All dynamic content uses safe insertion:
```javascript
element.textContent = event.title;  // Safe - no HTML rendering
```

## Future Enhancements

### Potential Additions

1. **Filter Controls**
   - Add UI filters for provider, status
   - Update FullCalendar `extraParams` with filter values

2. **Event Creation**
   - Double-click empty day to create maintenance
   - Modal form for quick creation

3. **Drag-and-Drop Rescheduling**
   - Enable FullCalendar's `editable: true`
   - PATCH API call on event drop

4. **Outage Events**
   - Add toggle to show/hide outage events
   - Different color scheme for outages

5. **ICS Export**
   - Add "Export to Calendar" button
   - Generate ICS file from filtered events

6. **Timezone Support**
   - Display times in user's timezone
   - Show original timezone in modal if different

### Non-Goals

- Calendar view for Outage events (separate implementation if needed)
- Inline editing of events (use detail page)
- Complex filtering UI (use list view for advanced filtering)
- Print-friendly view (not primary use case)

## Implementation Checklist

- [ ] Add `status_color` field to `MaintenanceSerializer`
- [ ] Download and add FullCalendar files to `static/vendor_notification/`
- [ ] Create `calendar.js` with FullCalendar initialization
- [ ] Create new `calendar.html` template with modal
- [ ] Replace `Calendar` class and view in `views.py`
- [ ] Update URL routing in `urls.py`
- [ ] Verify navigation menu links to calendar
- [ ] Test calendar rendering and multi-day events
- [ ] Test modal opens with correct data
- [ ] Test month navigation and API calls
- [ ] Test permissions and access control
- [ ] Verify static files collected in production
- [ ] Update documentation with calendar usage

## References

- **FullCalendar Documentation:** https://fullcalendar.io/docs
- **FullCalendar Events Source:** https://fullcalendar.io/docs/events-json-feed
- **Tabler UI Examples:** https://preview.tabler.io/fullcalendar.html
- **NetBox FilterSet Documentation:** https://docs.netbox.dev/en/stable/plugins/development/filtersets/
- **NetBox API Guide:** https://docs.netbox.dev/en/stable/integrations/rest-api/
- **Bootstrap Modal Documentation:** https://getbootstrap.com/docs/5.0/components/modal/
