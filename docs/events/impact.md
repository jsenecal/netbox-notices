# Impact Tracking

The `Impact` model is what turns a Maintenance or Outage event from a free-form notice into structured data. Each `Impact` row is a (event, target object, impact level) tuple. Both ends use Django's `GenericForeignKey`, so a single Impact model handles every supported pair: Maintenance-on-Circuit, Maintenance-on-Device, Outage-on-Site, etc.

## Model

| Field | Type | Notes |
|-------|------|-------|
| `event_content_type` | FK -> `ContentType` | Limited to `notices.maintenance` and `notices.outage`. |
| `event_object_id` | PositiveInteger (indexed) | PK of the linked event. |
| `event` | GenericForeignKey | Resolved Maintenance or Outage instance. |
| `target_content_type` | FK -> `ContentType` | Must be in `allowed_content_types`. |
| `target_object_id` | PositiveInteger (indexed) | PK of the affected NetBox object. |
| `target` | GenericForeignKey | Resolved target instance (Circuit, Device, Site, ...). |
| `impact` | CharField (choices, nullable) | Severity level. See [Impact Levels](#impact-levels). |
| `sites` | M2M -> `dcim.Site` | Cached site membership of the target. Populated by `refresh_sites()`. |
| `locations` | M2M -> `dcim.Location` | Cached location membership of the target. |
| `tags` | M2M -> NetBox Tag | Standard tagging. |

A `unique_together` constraint on `(event_content_type, event_object_id, target_content_type, target_object_id)` prevents linking the same event to the same target more than once.

## Impact levels

Defined in `notices/choices.py:ImpactTypeChoices` (BCOP standard).

| Level | Colour | Meaning |
|-------|--------|---------|
| `NO-IMPACT` | green | Maintenance affects this object's path but no observable degradation. |
| `REDUCED-REDUNDANCY` | yellow | Object remains in service but with one or more redundant paths offline. |
| `DEGRADED` | orange | Object is in service but not at full capacity / quality. |
| `OUTAGE` | red | Object will be entirely down. |

Impact level may be `null` (no level recorded yet); the `Impact` table sorts by level so unknowns appear first by default.

## Allowed target types

Validation in `Impact.clean()` rejects any `target_content_type` that is not present in `PLUGINS_CONFIG["notices"]["allowed_content_types"]`. The check is case-insensitive but stores the canonical lowercase form. Forms only offer types from this list.

If you change `allowed_content_types`, restart NetBox so the dynamically-registered template extensions and form choices update.

## Site and location cache

Filtering "show me every maintenance affecting any device in site X" naively requires walking every Impact's `target` GenericForeignKey, then dispatching to model-specific code to resolve a Site. That doesn't scale and you can't index it.

The plugin solves this with two cached M2M fields on `Impact`:

- `Impact.sites` -- the set of Sites the target belongs to.
- `Impact.locations` -- the set of Locations the target belongs to.

Both are populated by `Impact.refresh_sites()`, which calls into the **resolver registry** in `notices/resolvers.py` -- a per-content-type lookup of small functions that know how to extract Site/Location PKs from an instance of that type.

`refresh_sites()` is called automatically by `notices.signals` whenever:

- An Impact is saved.
- A target object is saved (so a Device moving to a new Site updates every Impact pointing at it).
- A target object is deleted (cascade clears the M2M).

The list filters on Maintenance and Outage (`site_id`, `region_id`, `site_group_id`, `location_id`) traverse these cached M2Ms, which makes them fast, indexable, and capable of region/site-group rollups for free.

### Adding new content types

If you add a content type to `allowed_content_types` that does not have a resolver registered, `notices.checks` emits a startup warning, and impacts on objects of that type will have empty `sites`/`locations` -- they will be invisible to the site-scoped filters.

See [Site and Location Resolvers](../developer/resolvers.md) for how to register a resolver for a custom type.

## Validation rules

`Impact.clean()` enforces:

1. `target_content_type` must be in `allowed_content_types`.
2. `event_content_type` must be `notices.maintenance` or `notices.outage`.
3. The parent event must not be in a frozen state. You cannot add or modify Impacts on Maintenance with status `COMPLETED`/`CANCELLED` or Outage with status `RESOLVED`.

Rule 3 is the audit-integrity guarantee: once an event is closed, its impact ledger is immutable.

## Audit trail

`Impact.to_objectchange()` overrides NetBox's default to set `related_object` to the parent event. This causes Impact changes to appear in the **event's** changelog, so the maintenance or outage detail page shows a unified timeline of "added impact for Circuit XYZ at 14:32, removed impact for Device ABC at 14:35".

The same trick is used for `EventNotification.to_objectchange()`.

## REST API

```
GET    /api/plugins/notices/impact/
POST   /api/plugins/notices/impact/
GET    /api/plugins/notices/impact/{id}/
PATCH  /api/plugins/notices/impact/{id}/
PUT    /api/plugins/notices/impact/{id}/
DELETE /api/plugins/notices/impact/{id}/
```

### Creating an Impact

The serializer requires the content-type integers, not the model name strings, on input. Resolve them once at parser startup:

```python
import requests

response = requests.get(
    "https://netbox.example.com/api/extras/content-types/?app_label=notices&model=maintenance",
    headers={"Authorization": f"Token {token}"},
)
maintenance_ct = response.json()["results"][0]["id"]
```

Then create the Impact:

```http
POST /api/plugins/notices/impact/
Authorization: Token YOUR_API_TOKEN
Content-Type: application/json

{
  "event_content_type": 245,
  "event_object_id": 17,
  "target_content_type": 12,
  "target_object_id": 412,
  "impact": "OUTAGE"
}
```

The response includes nested representations for both `event` and `target`:

```json
{
  "id": 88,
  "url": "https://.../api/plugins/notices/impact/88/",
  "event": { "id": 17, "name": "MAINT-2026-001", "status": "CONFIRMED", ... },
  "target": { "id": 412, "cid": "ZAYO/CKT/12345", ... },
  "impact": "OUTAGE",
  "tags": [],
  "created": "2026-04-27T13:01:55Z",
  "last_updated": "2026-04-27T13:01:55Z"
}
```

When the target is a Circuit, the full `CircuitSerializer` is used; for other types, a minimal `{id, name, type}` shape is returned (per `ImpactSerializer.get_target`).

## Filtering Impacts

The `ImpactFilterSet` filters on `id`, `event_content_type`, `event_object_id`, `target_content_type`, `target_object_id`, and `impact` level. To find every impact attached to maintenance #17, filter on `event_object_id=17` and `event_content_type=<maintenance ct>`.

The richer site-scoped filters live on the parent event filtersets (`MaintenanceFilterSet`, `OutageFilterSet`) and traverse the `Impact.sites` / `Impact.locations` cache; see [Maintenance](maintenance.md) and [Outage](outage.md).

## UI behaviour

There is no top-level "Impacts" list view; impacts are managed in the context of their parent event:

- **Maintenance / Outage detail page** shows the impact table with Sites and Locations columns derived from the cached M2M.
- **+ Add Impact** opens `ImpactEditView` with the parent event pre-filled.
- **Object detail pages** (Device, Circuit, Site, ...) show the inverse: a "Maintenance and Outage History" widget listing every event that has ever impacted this object within the `event_history_days` window.

The per-object widget is registered dynamically: at app-ready time, `notices.template_content` reads `allowed_content_types` and creates one `PluginTemplateExtension` subclass per type.
