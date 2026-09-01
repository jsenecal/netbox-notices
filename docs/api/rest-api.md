# REST API

The plugin exposes seven endpoints under NetBox's plugin API namespace. They follow NetBox conventions throughout: token authentication, `limit`/`offset` pagination, `?brief=1` for compact representations, and the same filter grammar as core.

The REST API is the primary interface. External parsers write events through it, and the outbound delivery loop reads and updates prepared notifications through it.

## Base URL and authentication

```
/api/plugins/notices/
```

Every request needs a NetBox API token:

```http
GET /api/plugins/notices/maintenance/
Authorization: Token 0123456789abcdef0123456789abcdef01234567
```

The browsable API is available at the same URLs in a logged-in browser session, and the OpenAPI schema NetBox generates at `/api/schema/` includes these endpoints.

## Endpoints

| Endpoint | Model | Methods |
|---|---|---|
| `maintenance/` | `Maintenance` | GET, POST, PUT, PATCH, DELETE |
| `outage/` | `Outage` | GET, POST, PUT, PATCH, DELETE |
| `impact/` | `Impact` | GET, POST, PUT, PATCH, DELETE |
| `eventnotification/` | `EventNotification` | GET, POST, PUT, PATCH, DELETE |
| `notification-templates/` | `NotificationTemplate` | GET, POST, PUT, PATCH, DELETE |
| `prepared-notifications/` | `PreparedNotification` | GET, POST, PUT, PATCH, DELETE |
| `sent-notifications/` | `SentNotification` | GET only |

Note the inconsistency in naming: the event endpoints are singular (`maintenance`, `outage`, `impact`, `eventnotification`) and the messaging endpoints are plural and hyphenated. This is historical and is not going to change without a major version.

## Maintenance

```
GET    /api/plugins/notices/maintenance/
POST   /api/plugins/notices/maintenance/
GET    /api/plugins/notices/maintenance/{id}/
PATCH  /api/plugins/notices/maintenance/{id}/
DELETE /api/plugins/notices/maintenance/{id}/
```

### Fields

| Field | Type | Notes |
|---|---|---|
| `name` | string | Provider event ID. Required. |
| `summary` | string | Required. |
| `provider` | nested Provider | Write by PK. Required. |
| `start` | datetime | Required. |
| `end` | datetime | Required. Must not precede `start`. |
| `status` | string | See [Maintenance Events](../events/maintenance.md). Required. |
| `status_color` | string | Read-only. Badge colour for the current status. |
| `original_timezone` | string | IANA timezone name from the provider notification. |
| `internal_ticket` | string | Your change reference. |
| `acknowledged` | boolean | |
| `replaces` | integer | PK of the maintenance this one replaces. |
| `impact` | string | Free-text impact description, distinct from `Impact` records. |
| `comments` | string | |
| `impact_count` | integer | Read-only count of linked `Impact` records. |
| `tags`, `custom_fields`, `created`, `last_updated` | | Standard NetBox fields. |

Setting `replaces` on creation moves the replaced maintenance to `RE-SCHEDULED` through a signal. Nothing in the request body reflects that; re-read the other event to see it.

The response also carries `impacts` and `notifications` keys. Both are currently always `null`, whatever the record holds, because the serializer sources them from attributes that do not exist on the model. Do not build against them. To retrieve an event's impacts, query the impact endpoint by event, as shown below.

### Filters

`id`, `name`, `summary`, `status`, `provider_id`, `start`, `end`, `original_timezone`, `internal_ticket`, `acknowledged`, `impact`, `comments`.

Plus relational filters:

| Filter | Effect |
|---|---|
| `replaces_id` | Maintenances replacing a given event |
| `has_replaces` | `true` for events that have been rescheduled, `false` for those that have not |
| `site_id` | Maintenances impacting anything in a site |
| `region_id` | Same, rolled up by region |
| `site_group_id` | Same, rolled up by site group |
| `location_id` | Same, by location |

The four site filters traverse the cached `Impact.sites` and `Impact.locations` M2Ms. A target type with no registered resolver contributes nothing to them; see [Site and Location Resolvers](../developer/resolvers.md).

`q` searches `name`, `summary`, `internal_ticket` and the free-text `impact` field.

### Example

```http
POST /api/plugins/notices/maintenance/
Authorization: Token YOUR_API_TOKEN
Content-Type: application/json

{
  "name": "PWIC-12345",
  "summary": "Planned fibre splice, Route 7",
  "provider": 7,
  "status": "CONFIRMED",
  "start": "2026-09-14T02:00:00Z",
  "end": "2026-09-14T06:00:00Z",
  "original_timezone": "America/Toronto",
  "internal_ticket": "CHG-4471"
}
```

## Outage

```
GET    /api/plugins/notices/outage/
POST   /api/plugins/notices/outage/
GET    /api/plugins/notices/outage/{id}/
PATCH  /api/plugins/notices/outage/{id}/
DELETE /api/plugins/notices/outage/{id}/
```

Same shape as Maintenance, with `end` optional and three extra fields: `reported_at`, `estimated_time_to_repair`, and a status from the outage set. `end` becomes required once `status` is `RESOLVED`.

Filters match Maintenance minus the reschedule ones, plus `reported_at` and `estimated_time_to_repair`. The four site filters behave identically.

See [Outage Events](../events/outage.md) for worked examples.

## Impact

```
GET    /api/plugins/notices/impact/
POST   /api/plugins/notices/impact/
GET    /api/plugins/notices/impact/{id}/
PATCH  /api/plugins/notices/impact/{id}/
DELETE /api/plugins/notices/impact/{id}/
```

Both ends of an `Impact` are generic foreign keys, so writes take a content type and an object ID for each.

| Field | Type | Notes |
|---|---|---|
| `event_content_type` | integer | ContentType PK. Limited to `notices.maintenance` and `notices.outage`. |
| `event_object_id` | integer | PK of the event. |
| `event` | object | Read-only. Nested maintenance or outage, whichever applies. |
| `target_content_type` | integer | ContentType PK. Must be in `allowed_content_types`. |
| `target_object_id` | integer | PK of the affected object. |
| `target` | object | Read-only. Full circuit representation for circuits, a basic `{id, name, type}` otherwise. |
| `impact` | string | `NO-IMPACT`, `REDUCED-REDUNDANCY`, `DEGRADED` or `OUTAGE`. Nullable. |

The write fields take numeric ContentType PKs, which differ between deployments. Look them up first:

```http
GET /api/extras/content-types/?app_label=notices&model=maintenance
GET /api/extras/content-types/?app_label=dcim&model=device
```

Filters accept the dotted form instead, which is easier to use by hand. `event_content_type` and `target_content_type` are `ContentTypeFilter` fields, so this works:

```http
GET /api/plugins/notices/impact/?event_content_type=notices.maintenance&event_object_id=42
```

That is the supported way to list an event's impacts, given that the `impacts` key on the event serializers is not usable.

Other filters: `id`, `event_object_id`, `target_object_id`, `impact`, `site_id`, `region_id`, `site_group_id`, `location_id`.

Three validation rules apply on write, all from `Impact.clean()`:

1. `target_content_type` must appear in `allowed_content_types`.
2. `event_content_type` must be `notices.maintenance` or `notices.outage`.
3. The parent event must not be closed. Impacts cannot be created or changed on a maintenance in `COMPLETED` or `CANCELLED`, or an outage in `RESOLVED`.

A `unique_together` constraint on the four generic FK columns prevents the same event being linked to the same target twice.

## Event notifications

```
GET    /api/plugins/notices/eventnotification/
POST   /api/plugins/notices/eventnotification/
GET    /api/plugins/notices/eventnotification/{id}/
DELETE /api/plugins/notices/eventnotification/{id}/
```

Stores the provider email that produced an event. This is the endpoint a parser posts to after creating the event itself.

| Field | Type | Notes |
|---|---|---|
| `event_content_type` | integer | ContentType PK, maintenance or outage. |
| `event_object_id` | integer | PK of the event. |
| `event` | object | Read-only nested event. |
| `subject` | string | Max 100 characters. |
| `email_from` | email | |
| `email_received` | datetime | |
| `email_body` | string | Rendered on the detail page after sanitisation. |

The model also has a binary `email` field holding the raw MIME message. It is not exposed through the serializer.

Filters: `id`, `event_content_type`, `event_object_id`, `subject`, `email_from`, `email_received`, `email_body`. `q` searches subject, body and sender.

## Notification templates

```
GET    /api/plugins/notices/notification-templates/
POST   /api/plugins/notices/notification-templates/
GET    /api/plugins/notices/notification-templates/{id}/
PATCH  /api/plugins/notices/notification-templates/{id}/
DELETE /api/plugins/notices/notification-templates/{id}/
```

Field reference is in [Templates](../messaging/templates.md). Two API-specific behaviours:

**`headers_template` accepts YAML.** Send a YAML string and the serializer parses it into the stored JSON object. Sending a JSON object directly also works.

```json
{
  "headers_template": "X-Event-Reference: \"{{ maintenance.name }}\"\nReply-To: \"noc@example.com\""
}
```

**`scopes` is writable inline.** Scopes are nested in the template payload rather than having an endpoint of their own, and `content_type` there is the model name as a slug, not a PK:

```json
{
  "name": "Customer maintenance notice",
  "slug": "customer-maintenance",
  "event_type": "maintenance",
  "granularity": "per_tenant",
  "subject_template": "[{{ maintenance.status }}] Maintenance {{ maintenance.name }}",
  "body_template": "...",
  "scopes": [
    {"content_type": "tenant", "object_id": null, "event_type": "maintenance", "weight": 1500}
  ]
}
```

A PATCH that includes `scopes` deletes every existing scope on the template and recreates the list from the payload. It is a replace, not a merge, so partial scope updates are not possible. Omit the key entirely to leave scopes alone.

`contact_roles` behaves the same way: supplying it replaces the whole set.

Filters: `id`, `name`, `slug`, `event_type`, `granularity`, `is_base_template`. `event_type` and `granularity` accept multiple values. `q` searches name, slug and description.

## Prepared notifications

```
GET    /api/plugins/notices/prepared-notifications/
POST   /api/plugins/notices/prepared-notifications/
GET    /api/plugins/notices/prepared-notifications/{id}/
PATCH  /api/plugins/notices/prepared-notifications/{id}/
DELETE /api/plugins/notices/prepared-notifications/{id}/
```

This endpoint is the outbound queue, and status changes here are the only way to drive the state machine. The web UI does not expose the field.

| Field | Type | Notes |
|---|---|---|
| `template` | nested | Read-only. Write with `template_id`. |
| `template_id` | integer | Write-only. Required on create. |
| `event_content_type`, `event_id` | integer | Optional link to a maintenance or outage. |
| `status` | string | See below. |
| `contacts` | nested list | Read-only. Write with `contact_ids`. |
| `contact_ids` | list of integers | Write-only. |
| `recipients` | JSON | Read-only. Snapshot taken at approval. |
| `subject`, `body_text`, `body_html`, `headers`, `css`, `ical_content` | | Rendered content. |
| `approved_by`, `approved_at`, `sent_at`, `delivered_at`, `viewed_at` | | Read-only. Set by the state machine. |
| `message` | string | Write-only. Creates a journal entry for the transition. |
| `timestamp` | datetime | Write-only. Real time of the transition. |

### Status rules

A create must use `draft`. Any other value is rejected:

```json
{"status": ["A notification is always created as 'draft'. Create it first, then PATCH it to 'ready'."]}
```

An update must follow the transition graph. `draft` to `ready` to `sent` to `delivered`, with `sent` also able to reach `failed`, and `failed` able to return to `ready`. An invalid move names the valid ones:

```json
{"status": ["Cannot transition from 'draft' to 'sent'. Valid: ready"]}
```

The `timestamp` field lets a batching delivery system record when something actually happened rather than when it got round to reporting it. It cannot be in the future, `sent_at` cannot precede `approved_at`, and `delivered_at` cannot precede `sent_at`.

Read `recipients`, not `contacts`, when delivering. The full rationale, side effects and a polling loop are in [Approval Workflow](../messaging/workflow.md).

Filters: `id`, `status`, `template_id`. `status` accepts multiple values. `q` searches subject and body text.

## Sent notifications

```
GET /api/plugins/notices/sent-notifications/
GET /api/plugins/notices/sent-notifications/{id}/
```

A read-only view of the same table, filtered by its manager to `sent` and `delivered`. Every field is read-only and only `GET`, `HEAD` and `OPTIONS` are accepted. It exists so an audit consumer can read the delivery log without any possibility of writing to it.

## iCal feed

The calendar feed is not part of the REST API and is not a DRF endpoint, but it accepts the same tokens:

```
GET /plugins/notices/ical/maintenances.ics
```

It supports a `token` query parameter in addition to the `Authorization` header, because calendar clients cannot set headers. It also honours ETag and `If-None-Match`. See [Calendar and iCal Feed](../events/calendar-and-ical.md) for parameters and caching behaviour.

## GraphQL

Read-only GraphQL queries are registered for maintenance, outage, impact, event notification, notification template and prepared notification, in both single and list form, at NetBox's usual `/graphql/` endpoint.

```graphql
query {
  maintenance_list(filters: {status: "CONFIRMED"}) {
    id
    name
    provider { name }
    start
    end
  }
}
```

There are no GraphQL mutations. Writes go through REST.

## Permissions

Endpoints enforce the standard NetBox model permissions, `notices.view_maintenance`, `notices.add_impact` and so on, including object-level constraints. `sent-notifications/` checks `notices.view_preparednotification`, since the proxy shares the underlying model.

See [Permissions](../permissions.md) for the full matrix and recommended role bindings.

## See also

- [Maintenance Events](../events/maintenance.md)
- [Outage Events](../events/outage.md)
- [Impact Tracking](../events/impact.md)
- [Approval Workflow](../messaging/workflow.md)
- [Using a parser](../parsers.md)
