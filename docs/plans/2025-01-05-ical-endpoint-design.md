# iCal Endpoint Design

**Date:** 2025-01-05
**Status:** Approved

## Overview

Provide an iCal (RFC 5545) feed of maintenance events that calendar applications can subscribe to, enabling users to see vendor maintenances in their preferred calendar tools (Apple Calendar, Google Calendar, Outlook, etc.).

## URL Structure

**Endpoint:** `/plugins/vendor-notification/ical/maintenances.ics`

**Query Parameters:**
- `token` (required for calendar clients): NetBox API token for authentication
- `past_days` (optional, default 30): Number of days in the past to include
- `provider` or `provider_id` (optional): Filter by provider slug or ID
- `status` (optional): Comma-separated status list (e.g., `CONFIRMED,IN-PROCESS`)

**Example URLs:**
```
# Global feed with token
/plugins/vendor-notification/ical/maintenances.ics?token=abc123

# AWS maintenances only
/plugins/vendor-notification/ical/maintenances.ics?token=abc123&provider=aws

# Active maintenances only
/plugins/vendor-notification/ical/maintenances.ics?token=abc123&status=CONFIRMED,IN-PROCESS

# Custom time range (60 days past)
/plugins/vendor-notification/ical/maintenances.ics?token=abc123&past_days=60
```

## Authentication

Calendar clients don't support Authorization headers or session cookies, so we support three authentication methods:

1. **Token in URL** (primary - for calendar clients)
   - Extract from `request.GET.get('token')`
   - Authenticate using `TokenAuthentication().authenticate_credentials(key)`

2. **Authorization header** (for API/scripts)
   - Standard DRF approach: `Authorization: Token <key>`

3. **Session auth** (for browser preview)
   - If user is logged into NetBox UI

**Permission Required:** `vendor_notification.view_maintenance`

## Data Filtering

**Time Range:**
```python
cutoff_date = timezone.now() - timedelta(days=past_days_setting)
maintenances = Maintenance.objects.filter(start__gte=cutoff_date)
```
This gives us: all events starting within past N days OR any time in the future.

**Provider Filter:**
- Accept both `provider` (slug) and `provider_id` (integer)
- Use `Provider.objects.get()` to resolve slug to ID
- Apply: `.filter(provider_id=resolved_id)`

**Status Filter:**
- Parse comma-separated string: `"CONFIRMED,IN-PROCESS"` → `["CONFIRMED", "IN-PROCESS"]`
- Validate against `MaintenanceTypeChoices`
- Apply: `.filter(status__in=status_list)`

**Query Optimization:**
```python
queryset = Maintenance.objects.select_related('provider').prefetch_related('impacts')
```

## iCal Format

**Library:** `icalendar>=5.0.0` (RFC 5545 compliant)

**Calendar Structure:**
```
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//NetBox Vendor Notification Plugin//EN
CALSCALE:GREGORIAN
X-WR-CALNAME:NetBox Maintenance Events
X-WR-TIMEZONE:UTC
X-WR-CALDESC:Vendor maintenance events from NetBox

BEGIN:VEVENT
UID:maintenance-{maintenance.id}@{domain}
DTSTAMP:{now in UTC}
DTSTART:{start in UTC with Z suffix}
DTEND:{end in UTC with Z suffix}
SUMMARY:{maintenance.name} - {maintenance.summary}
DESCRIPTION:{detailed description}
LOCATION:{provider.name}
STATUS:{mapped status}
URL:{absolute URL to maintenance detail page}
CATEGORIES:{maintenance.status}
END:VEVENT

END:VCALENDAR
```

**Timezone Handling:**
- All events in UTC with Z suffix (e.g., `20250115T140000Z`)
- Simple, unambiguous, works universally

**Status Mapping:**
- `TENTATIVE` → `STATUS:TENTATIVE`
- `CONFIRMED` → `STATUS:CONFIRMED`
- `CANCELLED` → `STATUS:CANCELLED`
- `IN-PROCESS` → `STATUS:CONFIRMED`
- `COMPLETED` → `STATUS:CONFIRMED`
- `UNKNOWN` → `STATUS:TENTATIVE`
- `RE-SCHEDULED` → `STATUS:CANCELLED`

**Description Field:**
```
Provider: {provider.name}
Status: {maintenance.status}
Internal Ticket: {maintenance.internal_ticket}

Affected Objects:
- {impact.target} ({impact.impact})
[...more impacts...]

Comments:
{maintenance.comments}
```

## HTTP Caching

**Strategy:** HTTP headers only (no server-side cache)

**Cache-Control:**
```
Cache-Control: public, max-age=900
```
- `public`: Allows proxies/CDNs to cache
- `max-age=900`: 15 minutes TTL (configurable)

**ETag Generation:**
```python
etag_source = f"{params_hash}-{latest_modified}-{count}"
etag = hashlib.md5(etag_source.encode()).hexdigest()
```

**Last-Modified:**
```python
Last-Modified: {most_recent_maintenance.last_updated}
```

**Conditional Requests:**
- If `If-None-Match` matches ETag → 304 Not Modified
- If `If-Modified-Since` and no changes → 304 Not Modified
- Otherwise → Generate full iCal response

## Configuration

**Plugin Settings:**
```python
# In vendor_notification/__init__.py
default_settings = {
    "allowed_content_types": DEFAULT_ALLOWED_CONTENT_TYPES,
    "ical_past_days_default": 30,        # Days in past to include
    "ical_cache_max_age": 900,           # Cache TTL in seconds
}
```

## Error Handling

**Invalid Parameters:**
- Invalid `provider` → 400 Bad Request with plain text error
- Invalid `status` values → Silently ignore, use valid ones only
- Invalid `past_days` → Use default setting
- Invalid `token` → 403 Forbidden

**Empty Results:**
- Return valid empty iCal calendar (not 404)

**Authentication/Permission:**
- No/invalid auth → 403 Forbidden
- Missing permission → 403 Forbidden

**Security:**
- Validate `past_days` range (max 365 days)
- Escape text fields in DESCRIPTION
- Sanitize all query parameters

## Implementation Structure

**Files to Create:**
- `vendor_notification/ical_utils.py` - iCal generation helpers

**Files to Modify:**
- `vendor_notification/views.py` - Add `MaintenanceICalView`
- `vendor_notification/urls.py` - Add ical route
- `vendor_notification/__init__.py` - Update `default_settings`
- `pyproject.toml` - Add `icalendar>=5.0.0` dependency

**Test Files:**
- `tests/test_ical_view.py` - Integration tests
- `tests/test_ical_utils.py` - Unit tests

**View Class:**
```python
class MaintenanceICalView(View):
    """Generate iCal feed with HTTP caching and flexible authentication"""

    def get(self, request):
        # 1. Authenticate (token in URL / header / session)
        # 2. Check permissions
        # 3. Parse and validate query parameters
        # 4. Build filtered queryset
        # 5. Check ETag/If-Modified-Since for 304
        # 6. Generate iCal calendar
        # 7. Set caching headers
        # 8. Return HttpResponse(content_type='text/calendar')
```

**Helper Functions:**
```python
# In ical_utils.py
def generate_maintenance_ical(maintenances, request):
    """Generate iCalendar object from maintenance queryset"""

def calculate_etag(queryset, params):
    """Calculate ETag for cache validation"""

def get_ical_status(maintenance_status):
    """Map maintenance status to iCal STATUS property"""
```

## Testing Strategy

**Unit Tests:**
- Test iCal generation functions
- Test status mapping
- Test ETag calculation
- Test time range filtering

**Integration Tests:**
- Test endpoint with token in URL
- Test endpoint with Authorization header
- Test endpoint with session auth
- Test 304 Not Modified responses
- Test authentication failures (401/403)
- Test empty results
- Test provider filtering
- Test status filtering
- Test invalid parameters

**Manual Testing:**
- Subscribe in Apple Calendar
- Subscribe in Google Calendar
- Subscribe in Outlook
- Verify events display correctly
- Modify maintenance, verify updates propagate after cache expiry

## Benefits

- **Universal compatibility:** Works with all major calendar clients
- **Performance:** HTTP caching reduces server load
- **Flexibility:** Filter by provider, status, time range
- **Security:** Token-based authentication, permission checks
- **Standard compliant:** RFC 5545 iCal format
