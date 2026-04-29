# Maintenance Events

A `Maintenance` represents a planned, scheduled maintenance window for a provider's service. Maintenance events have a required start and end time, a status that follows a defined lifecycle, and zero or more `Impact` records linking them to affected NetBox objects.

## Model

| Field | Type | Notes |
|-------|------|-------|
| `name` | CharField (100) | Provider-supplied event ID or ticket. Required. |
| `summary` | CharField (200) | One-line description. Required. |
| `provider` | FK -> `circuits.Provider` | Required. `related_name="maintenance"`. |
| `start` | DateTimeField (indexed) | Required. |
| `end` | DateTimeField (indexed) | Required. Must be after `start`. |
| `status` | CharField (choices) | See [Status Workflow](#status-workflow) below. |
| `original_timezone` | CharField (63) | IANA tz name from the provider's notification, used for "show in original tz" display. |
| `internal_ticket` | CharField (100) | Your organisation's change reference. |
| `acknowledged` | BooleanField | Whether the event has been acknowledged by the NOC. |
| `comments` | TextField | Free-form notes. |
| `impact` | TextField | Free-form impact description (separate from the structured `Impact` records). |
| `replaces` | FK -> `Maintenance` | Self-reference for rescheduled events. Set when a new event replaces an old one; the old event's status is auto-set to `RE-SCHEDULED` via signal. |
| `tags` | M2M -> NetBox Tag | Standard NetBox tagging. |

The model inherits from `BaseEvent` (an abstract `NetBoxModel`) which contributes `name`, `summary`, `provider`, `start`, `original_timezone`, `internal_ticket`, `acknowledged`, `comments`, and `impact`. Maintenance adds `end` (required), `status`, and `replaces`.

`clone_fields` includes everything except `status` and `replaces`, so the **Clone** action in the UI gives you a fresh editable copy.

## Status workflow

Status values are defined in `notices/choices.py:MaintenanceTypeChoices` and follow the BCOP standard.

```
                 +-> CANCELLED
                 |
TENTATIVE -> CONFIRMED -> IN-PROCESS -> COMPLETED
     |                |
     |                +-> RE-SCHEDULED (set automatically when a replacement is created)
     |
     +-> UNKNOWN (used when the provider has not yet specified)
```

| Status | Colour | When to use |
|--------|--------|-------------|
| `TENTATIVE` | yellow | Initial state when a notification is parsed; provider has proposed a window. |
| `CONFIRMED` | green | Provider has confirmed the window. Acknowledge once you've reviewed it. |
| `IN-PROCESS` | orange | Maintenance has started. Set automatically only by the **Mark In Progress** quick action. |
| `COMPLETED` | indigo | Maintenance finished successfully. |
| `CANCELLED` | gray | Provider cancelled before the start time. |
| `RE-SCHEDULED` | teal | Auto-set on the original event when a new Maintenance is created with `replaces=<this event>`. |
| `UNKNOWN` | blue | Used when status cannot be determined. |

### Quick actions

The Operations dropdown on the Maintenance detail page exposes four POST-only actions and one GET form. All require `notices.change_maintenance`.

| Action | URL | Effect |
|--------|-----|--------|
| Acknowledge | `POST .../maintenance/<id>/acknowledge/` | Sets `acknowledged = True`. Idempotent. |
| Mark In Progress | `POST .../maintenance/<id>/mark-in-progress/` | Sets `status = IN-PROCESS`. Refused if already `COMPLETED` or `CANCELLED`. |
| Mark Completed | `POST .../maintenance/<id>/mark-completed/` | Sets `status = COMPLETED`. Refused if `CANCELLED`. No-op if already `COMPLETED`. |
| Cancel | `GET/POST .../maintenance/<id>/cancel/` | Shows confirmation page on GET; sets `status = CANCELLED` on POST. Refused if already `COMPLETED` or `CANCELLED`. |
| Reschedule | `GET/POST .../maintenance/<id>/reschedule/` | Opens an edit form for a *new* Maintenance pre-populated from the original; setting `replaces` automatically transitions the original to `RE-SCHEDULED` via post-save signal. |

Each quick action snapshots the object first so the changelog records the change.

### Reschedule flow

1. User clicks **Reschedule** on the original Maintenance.
2. `MaintenanceRescheduleView` builds a fresh, unsaved `Maintenance` instance, copies every field from the original except `id`/`created`/`last_updated`, sets `replaces` to the original, resets `status` to `TENTATIVE`.
3. User edits the new start/end and saves.
4. The post-save signal observes that the new event has `replaces` set and updates the original event's status to `RE-SCHEDULED`.

Both events remain in the database; you can navigate from the new event to the replaced one via the `replaces` link, and the list view exposes a `has_replaces` filter to find rescheduled events.

## Timezone handling

Provider notifications often quote times in the provider's local timezone. The plugin stores `start` and `end` in UTC (Django's standard) and additionally records `original_timezone` so the UI can display both:

- `Maintenance.get_start_in_original_tz()` returns the start time in `original_timezone` if set, otherwise falls back to `start` as-is.
- `Maintenance.get_end_in_original_tz()` is the same for `end`.
- `Maintenance.has_timezone_difference()` returns `True` only when `original_timezone` is set *and* differs from the NetBox active timezone, so the template only renders the dual display when it would actually be useful.

`original_timezone` accepts any IANA name; the form exposes the curated list in `notices/choices.py:TimeZoneChoices` (Africa, America, Asia, Australia, Europe, Pacific groups), but anything `zoneinfo.ZoneInfo()` accepts will work.

## Validation

`Maintenance.clean()` (inherited from `BaseEvent`) enforces `end >= start`.

`Impact.clean()` enforces that you cannot add or modify Impacts on a Maintenance whose status is `COMPLETED` or `CANCELLED`. Once a maintenance is finalized, its impact set is frozen for audit purposes.

## Detail view

The Maintenance detail page (`MaintenanceView`) renders four panels:

- **Operations** dropdown (the quick actions above plus standard Edit/Clone/Delete).
- **Details** card with all model fields, including the original-timezone display when applicable.
- **Impacts** table with prefetched `sites` and `locations` columns (resolved via the [resolver registry](../developer/resolvers.md)).
- **Notifications** table listing every `EventNotification` linked to this event.
- **Timeline** showing the most recent 20 changelog entries with status-coloured icons.

## REST API

The Maintenance endpoints are documented in detail in the [REST API](../api/rest-api.md) reference. Quick reference:

```
GET    /api/plugins/notices/maintenance/
POST   /api/plugins/notices/maintenance/
GET    /api/plugins/notices/maintenance/{id}/
PATCH  /api/plugins/notices/maintenance/{id}/
PUT    /api/plugins/notices/maintenance/{id}/
DELETE /api/plugins/notices/maintenance/{id}/
```

Filterable fields (via `MaintenanceFilterSet`):

- `id`, `name`, `summary`, `status`, `provider_id`, `start`, `end`, `original_timezone`, `internal_ticket`, `acknowledged`, `impact`, `comments`
- `replaces_id` (find the new event that replaces a given one)
- `has_replaces=true|false`
- `site_id`, `region_id`, `site_group_id`, `location_id` (traverse `Impact.sites` / `Impact.locations` cache)

Free-text search via `?q=` matches `name`, `summary`, `internal_ticket`, and `impact`.
