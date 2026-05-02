# Calendar and iCal Feed

The plugin ships two complementary calendar features:

- An **interactive calendar view** in the NetBox UI (Plugins -> Notices -> Calendar) backed by FullCalendar and the REST API.
- An **iCal feed** at `/api/plugins/notices/ical/` for subscription from any external calendar app (Google Calendar, Outlook, Apple Calendar, Thunderbird, etc).

## Interactive calendar

Reach it from the menu under **Notices -> Events -> Calendar**, or directly at `/plugins/notices/maintenance/calendar/`.

The view uses FullCalendar with month, week, and day modes. Events are colour-coded by type and status (Maintenance: status colour from `MaintenanceTypeChoices`; Outage: status colour from `OutageStatusChoices`). Clicking an event opens a quick summary modal with status, provider, timing, and a deep link to the full detail view. The page also shows a "Subscribe" link with a URL template using `ical_token_placeholder` from the plugin settings, so users know where to paste their token.

The calendar requires `notices.view_maintenance` and renders Maintenance events; Outages are not currently represented in the FullCalendar view (they appear in the dashboard timeline and the iCal feed if you add them later -- track upstream).

## iCal feed

The feed endpoint is:

```
https://your-netbox/api/plugins/notices/ical/
```

It returns a `text/calendar; charset=utf-8` response containing every Maintenance event matching the query parameters.

### Authentication

The view tries three authentication methods in order:

1. **URL token** -- `?token=<plaintext>`. Supports both v1 plaintext tokens and v2 `nbt_<key>.<plaintext>` tokens. This is the only mode that works with most calendar apps, since they cannot send custom headers on a subscription URL.
2. **`Authorization` header** -- `Authorization: Token <plaintext>`. Useful for cron jobs and `curl` scripts.
3. **Session cookie** -- works when you open the URL in a logged-in browser.

If `LOGIN_REQUIRED = False` is set in NetBox configuration, anonymous requests are also accepted (the queryset is then unrestricted).

The token's user must have `notices.view_maintenance`. Disabled tokens, expired tokens, and inactive users are rejected with `403 Forbidden`.

### Query parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `token` | -- | API token (see above). |
| `past_days` | `ical_past_days_default` (default 30) | Include events with `start >= now - past_days days`. Capped at 365. |
| `provider` | -- | Filter by provider slug. Mutually exclusive with `provider_id`. |
| `provider_id` | -- | Filter by provider PK. |
| `status` | -- | Comma-separated status list (case-insensitive). Invalid statuses are silently dropped; if all are invalid, no status filter is applied. |
| `download` | `false` | If truthy (`true`/`1`/`yes`), set `Content-Disposition: attachment; filename="netbox-maintenance-YYYY-MM-DD.ics"` so browsers download instead of subscribe. |

Unknown parameters are ignored.

### Examples

Subscribe to all events in the last 30 days and beyond:

```
https://netbox.example.com/api/plugins/notices/ical/?token=YOUR_TOKEN
```

Only confirmed events from a specific provider, last 7 days:

```
https://netbox.example.com/api/plugins/notices/ical/?token=YOUR_TOKEN&provider=zayo&status=CONFIRMED&past_days=7
```

Multiple statuses:

```
.../ical/?token=YOUR_TOKEN&status=CONFIRMED,IN-PROCESS
```

Download as a one-off file:

```
.../ical/?token=YOUR_TOKEN&download=true
```

### Subscription URL guidelines

| Calendar | Where to paste the URL |
|----------|------------------------|
| Google Calendar | Settings -> Add calendar -> From URL |
| Outlook (web) | Calendar -> Add calendar -> Subscribe from web |
| Apple Calendar (macOS / iOS) | File -> New Calendar Subscription |
| Thunderbird | Calendar -> New Calendar -> On the network |

Most clients refresh on their own schedule (Google: every few hours; Apple: configurable). The plugin caches its response for 15 minutes by default (`ical_cache_max_age`), so back-to-back fetches don't query the database repeatedly.

### Caching and conditional requests

The view computes a deterministic ETag from `(query parameters, latest last_updated, count)` of the matching queryset. The response always includes:

- `ETag: <md5 hex>` -- conditional request validator.
- `Last-Modified: <RFC 1123 date>` -- the most recent `last_updated` of any matching maintenance.
- `Cache-Control: public, max-age=<ical_cache_max_age>` -- only on subscription mode (not when `download=true`).

If the client sends `If-None-Match: <etag>`, the view returns `304 Not Modified` with no body. Same for `If-Modified-Since`.

### Format details

The feed conforms to RFC 5545 with these conventions:

- Calendar metadata: `PRODID: -//NetBox Vendor Notification Plugin//EN`, `VERSION: 2.0`, `CALSCALE: GREGORIAN`, `X-WR-CALNAME: NetBox Maintenance Events`, `X-WR-TIMEZONE: UTC`.
- Each event: `UID: maintenance-<id>@<host>`, `DTSTAMP: now`, `DTSTART/DTEND` from the maintenance window, `SUMMARY` is `<name> - <summary>`, `LOCATION` is the provider name, `CATEGORIES` is the maintenance status.
- `STATUS` is mapped from the maintenance status:

| Maintenance status | iCal STATUS |
|--------------------|-------------|
| `TENTATIVE` | TENTATIVE |
| `CONFIRMED`, `IN-PROCESS`, `COMPLETED` | CONFIRMED |
| `CANCELLED`, `RE-SCHEDULED` | CANCELLED |
| `UNKNOWN` (or anything else) | TENTATIVE |

- `DESCRIPTION` includes `Provider: ...`, `Status: ...`, optional `Internal Ticket: ...`, the affected-objects list (`<target> (<impact>)`) when the maintenance has impacts, and the `comments` field if non-empty.
- `URL` points at the maintenance detail page using the request's scheme and `Host` header.

The mapping logic lives in `notices/ical_utils.py`. Outages are not currently emitted in the iCal feed; the feed is Maintenance-only by design (calendar apps want bounded windows, and Outages may be open-ended).

## See also

- [Outgoing Notifications](../outgoing-notifications.md) -- a separate, different feature that *generates* iCal attachments for outbound notifications using a customizable BCOP-compliant template per `NotificationTemplate`.
- [REST API](../api/rest-api.md) for the underlying maintenance / outage / impact endpoints.
