# Outage Events

An `Outage` represents an unplanned service incident. Outages share the same `Impact` and `EventNotification` machinery as Maintenance events but have a different status workflow that mirrors a typical incident lifecycle, and they support an open-ended (`end is null`) state until the incident is resolved.

## Model

| Field | Type | Notes |
|-------|------|-------|
| `name` | CharField (100) | Provider event ID or your own outage tracker ID. Required. |
| `summary` | CharField (200) | One-line description. Required. |
| `provider` | FK -> `circuits.Provider` | Required. |
| `start` | DateTimeField (indexed) | Defaults to `timezone.now()` so newly-reported outages can be created without supplying a start. |
| `reported_at` | DateTimeField | Defaults to `timezone.now()`. When the outage was first reported (may differ from `start`). |
| `end` | DateTimeField (indexed, nullable) | Optional until status becomes `RESOLVED`, at which point it becomes required. |
| `estimated_time_to_repair` | DateTimeField (nullable) | The current ETR. Tracked through changelog so you can audit how the estimate evolved. |
| `status` | CharField (choices) | See [Status Workflow](#status-workflow). |
| `original_timezone` | CharField (63) | IANA tz name from the provider notification. |
| `internal_ticket` | CharField (100) | Your tracking ticket reference. |
| `acknowledged` | BooleanField | NOC acknowledgement. |
| `comments` | TextField | Free-form notes. |
| `impact` | TextField | Free-form impact description. |
| `tags` | M2M -> NetBox Tag | Standard tagging. |

Like `Maintenance`, `Outage` extends `BaseEvent` and adds outage-specific fields (`reported_at`, `estimated_time_to_repair`, status choices).

## Status workflow

Status values are defined in `notices/choices.py:OutageStatusChoices`. Unlike Maintenance, the workflow is a soft progression that reflects the operational state of incident response.

```
REPORTED -> INVESTIGATING -> IDENTIFIED -> MONITORING -> RESOLVED
```

You may move backward (for example, `MONITORING -> INVESTIGATING` if the fix did not stick); the plugin does not enforce a strict FSM. The only validation is that `end` is required when transitioning to `RESOLVED` -- enforced by `Outage.clean()`.

| Status | Colour | Meaning |
|--------|--------|---------|
| `REPORTED` | red | Outage detected and logged; no investigation yet. |
| `INVESTIGATING` | orange | Triage in progress; root cause not yet known. |
| `IDENTIFIED` | yellow | Root cause known; fix being prepared or applied. |
| `MONITORING` | blue | Fix applied; watching for stability. |
| `RESOLVED` | green | Service fully restored. `end` must be set. |

## ETR tracking

`estimated_time_to_repair` is a single field, but every change is captured in the standard NetBox changelog. The detail view's timeline panel shows ETR revisions chronologically with diffs, so you can see how the estimate evolved across the incident.

When the provider issues a new ETR:

1. `PATCH /api/plugins/notices/outage/<id>/` with `{"estimated_time_to_repair": "2026-04-27T15:00:00Z"}`
2. The post-save changelog entry records the old and new value.
3. The detail timeline highlights the change with a status-coloured icon.

To clear the ETR, send `null`:

```http
PATCH /api/plugins/notices/outage/42/
Content-Type: application/json

{"estimated_time_to_repair": null}
```

## Validation

`Outage.clean()` enforces:

- `end >= start` (inherited from `BaseEvent`).
- `end` is required when `status == "RESOLVED"`.

Impacts on `RESOLVED` outages are frozen by `Impact.clean()` (alongside `COMPLETED` and `CANCELLED` events).

## Open-ended outages

Because `end` is nullable, you can create an outage immediately when it's reported:

```json
POST /api/plugins/notices/outage/
{
  "name": "OUT-2026-042",
  "summary": "Fiber cut on Main Street",
  "provider": 7,
  "status": "REPORTED"
}
```

`start` defaults to "now". The outage will appear on the dashboard, calendar, and event-history widgets as ongoing. Set `end` and transition to `RESOLVED` once service is restored.

The dashboard counts an outage as active if its status is one of `REPORTED`, `INVESTIGATING`, `IDENTIFIED`, or `MONITORING`. Open-ended outages also appear in the per-object event-history widget regardless of `event_history_days`, because they are presumed ongoing.

## Detail view

The Outage detail page renders the same panel layout as Maintenance:

- Standard Edit / Clone / Delete actions (no Maintenance-specific quick actions).
- Details card with ETR and reported-at fields.
- Impacts table with sites/locations columns.
- Notifications table.
- Timeline showing all status changes and ETR revisions.

## REST API

```
GET    /api/plugins/notices/outage/
POST   /api/plugins/notices/outage/
GET    /api/plugins/notices/outage/{id}/
PATCH  /api/plugins/notices/outage/{id}/
PUT    /api/plugins/notices/outage/{id}/
DELETE /api/plugins/notices/outage/{id}/
```

Filterable fields (via `OutageFilterSet`): `id`, `name`, `summary`, `status`, `provider_id`, `start`, `end`, `reported_at`, `estimated_time_to_repair`, `original_timezone`, `internal_ticket`, `acknowledged`, plus the same `site_id` / `region_id` / `site_group_id` / `location_id` site-scoping filters as Maintenance.

## Example: creating an outage

```http
POST /api/plugins/notices/outage/
Authorization: Token YOUR_API_TOKEN
Content-Type: application/json

{
  "name": "OUT-2026-001",
  "summary": "Fiber cut on Main Street",
  "provider": 7,
  "status": "INVESTIGATING",
  "estimated_time_to_repair": "2026-04-27T18:00:00Z",
  "internal_ticket": "INC-12345"
}
```

Then attach an impact (see [Impact Tracking](impact.md) for content-type IDs):

```http
POST /api/plugins/notices/impact/
Authorization: Token YOUR_API_TOKEN
Content-Type: application/json

{
  "event_content_type": 245,
  "event_object_id": 42,
  "target_content_type": 17,
  "target_object_id": 123,
  "impact": "OUTAGE"
}
```

Resolve the outage:

```http
PATCH /api/plugins/notices/outage/42/
{
  "status": "RESOLVED",
  "end": "2026-04-27T17:42:00Z"
}
```
