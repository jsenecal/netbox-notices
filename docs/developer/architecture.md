# Architecture

This page describes how netbox-notices is put together: the module layout, the model layer, and the NetBox registries the plugin hooks into. It is aimed at people modifying the plugin or extending it from another plugin.

## Two halves

The plugin does two separate jobs that share a data model but are otherwise independent.

**Event tracking.** A provider announces a maintenance window or an outage. That becomes a `Maintenance` or `Outage` record, plus one `Impact` row per affected NetBox object, plus the raw provider email as an `EventNotification`. Everything here is inbound.

**Outgoing notifications.** Your organisation tells its own customers about that event. A `NotificationTemplate` is rendered against the event into a `PreparedNotification`, which an external delivery system collects over the REST API. Everything here is outbound.

The plugin never sends mail in either direction. Inbound parsing is done by external parsers that POST to the REST API (see [Using a parser](../parsers.md)); outbound delivery is done by an external system that polls the API (see [Approval Workflow](../messaging/workflow.md)). What lives here is the storage, validation, rendering, and state tracking in between.

## Module map

```
notices/
  __init__.py           NoticesConfig(PluginConfig); default_settings; ready() imports
                        checks, resolvers, signals, widgets so their registries populate
  constants.py          DEFAULT_ALLOWED_CONTENT_TYPES
  choices.py            Every ChoiceSet: statuses, impact levels, timezones,
                        template event types, granularity, body format
  utils.py              get_allowed_content_types()
  checks.py             Django system check notices.W001 (resolver coverage)

  models/
    events.py           BaseEvent (abstract), Maintenance, Outage, Impact,
                        EventNotification
    messaging.py        NotificationTemplate, TemplateScope, PreparedNotification,
                        SentNotification (proxy)

  resolvers.py          Site/Location resolver registry for Impact targets
  signals.py            Reschedule side effect; Impact site cache maintenance
  validators.py         PreparedNotificationStateMachine and VALID_TRANSITIONS

  services/
    template_matching.py    Scope matching and weighted merge
    template_renderer.py    Jinja environment, custom filters, context builder
    recipient_discovery.py  Tenant -> ContactAssignment -> Contact traversal
    ical_generation.py      BCOP iCal bodies for notification attachments

  api/
    serializers/        events.py, messaging.py
    views/              events.py, messaging.py
    urls.py             NetBoxRouter registrations

  graphql/              Strawberry types, filters, schema
  filtersets.py         List and API filtering
  forms.py              Model, filter, bulk-edit and import forms
  tables.py             django-tables2 definitions
  views.py              Dashboard, model views, quick actions, calendar, iCal feed
  urls.py               Mounts views registered with @register_model_view
  navigation.py         Plugin menu
  search.py             Global search indexes
  widgets.py            NetBox dashboard widget
  template_content.py   PluginTemplateExtension classes injected into core pages
  templatetags/         sanitize_html filter for provider email bodies
  ical_utils.py         Feed generation, status mapping, ETag calculation
  timeline_utils.py     ObjectChange categorisation for detail-page timelines
  management/commands/  refresh_impact_sites
```

## Model layer

### Events

`BaseEvent` is an abstract `NetBoxModel` holding what a maintenance and an outage have in common: `name`, `summary`, `provider`, `start`, `original_timezone`, `internal_ticket`, `acknowledged`, `comments`, and a free-text `impact` description. Its `clean()` enforces one rule, that `end` is not before `start`, and it reads `end` with `getattr` because the field is defined by the subclass.

`Maintenance` adds a required `end`, a `status` from `MaintenanceTypeChoices`, and `replaces`, a self-referencing FK used for rescheduling.

`Outage` adds `reported_at`, an optional `end`, `estimated_time_to_repair`, and a `status` from `OutageStatusChoices`. Its `clean()` requires `end` once the status is `RESOLVED`.

Both subclasses declare `provider` again rather than inheriting it, because `BaseEvent` uses a `%(class)s_events` related name and `Maintenance` needs the plain `maintenance` accessor for backward compatibility.

### Impact

`Impact` is the join between an event and an affected object, and it is generic on both ends:

- `event_content_type` / `event_object_id` / `event`, restricted by `limit_choices_to` to `notices.maintenance` and `notices.outage`.
- `target_content_type` / `target_object_id` / `target`, restricted at validation time to `allowed_content_types`.

A generic FK cannot be joined against, so filtering "every maintenance affecting site X" cannot walk `target` in SQL. `Impact` therefore carries two cached M2M fields, `sites` and `locations`, populated from `target` by `refresh_sites()` through the [resolver registry](resolvers.md). The list filters on `Maintenance`, `Outage` and `Impact` traverse those caches, which is what makes region and site-group rollups possible.

Two `Impact` methods exist to keep NetBox from breaking on edge cases:

- `to_objectchange()` reassigns the change's `related_object` to the parent event, so impact edits show up in the event's changelog rather than nowhere.
- `get_absolute_url()` must never raise, because NetBox calls it from table columns and serializers where one bad row would take down a whole list page. A generic FK has no database-level cascade, so an impact can outlive its event; the method falls back to the parent type's list view, then to the dashboard.

`Impact` has no list or detail view. Its changelog and journal routes are filtered out in `urls.py` because both render through `generic/object.html`, which builds a breadcrumb from the model's list URL.

### Messaging

`NotificationTemplate` holds the Jinja sources plus the matching and recipient configuration. `TemplateScope` attaches a template to a NetBox object with a weight, in the manner of config contexts. `PreparedNotification` is a rendered snapshot with a status. `SentNotification` is a proxy over `PreparedNotification` whose manager filters to `sent` and `delivered`, which is how the "Sent" list stays read-only without a second table.

## Registries

The plugin populates several NetBox registries. `NoticesConfig.ready()` imports `checks`, `resolvers`, `signals` and `widgets` purely for their import side effects; the rest are discovered by NetBox from conventional module names.

| Registry | Module | Populated by |
|---|---|---|
| Site/location resolvers | `resolvers.py` | `@register_site_resolver`, `@register_location_resolver` |
| Django system checks | `checks.py` | `@register()` |
| Signal handlers | `signals.py` | `@receiver` |
| Dashboard widgets | `widgets.py` | `@register_widget` |
| Global search | `search.py` | `@register_search` |
| Template extensions | `template_content.py` | module-level `template_extensions` list |
| Model views | `views.py` | `@register_model_view`, mounted by `urls.py` |
| REST API | `api/urls.py` | `NetBoxRouter.register` |
| GraphQL | `graphql/schema.py` | `graphql_schema` on the PluginConfig |

`urls.py` only mounts; every view is registered with `@register_model_view` in `views.py`. Each model needs two entries, one for its list-level routes and one for its per-object routes. Changelog and journal views register themselves through `PluginConfig.ready()`.

## Signals

`signals.py` carries two unrelated concerns.

The first is the reschedule side effect: when a `Maintenance` is created with `replaces` set, the replaced event is snapshotted and moved to `RE-SCHEDULED`. The snapshot is what makes the transition appear in the changelog.

The second is impact cache maintenance. Each handler answers one question: given that this upstream object changed, which impacts need their `sites` and `locations` rebuilt? Handlers exist for `Impact` itself, `Site`, `Device`, `PowerFeed`, `PowerPanel`, `Circuit` and `CircuitTermination`. The `PowerPanel` and `CircuitTermination` handlers exist because those models sit between the target and its site, so a change there is invisible to a handler on the target itself.

This handler list maps one to one onto the default resolver registry. Registering a resolver for a new content type without adding the matching signals leaves the cache to drift silently. There is no check for that case; `notices.W001` only catches a missing resolver, not missing signals.

## Services

The four modules under `services/` are plain classes with no Django view or model dependencies, which makes them callable from a script, a management command, or another plugin.

`TemplateMatchingService` scores templates against a context of event, tenant and provider, and `merge_templates()` folds a scored list into one configuration dict with field-level precedence. See [Templates](../messaging/templates.md).

`TemplateRenderer` owns a Jinja `Environment` with `autoescape=False` and two custom filters, `ical_datetime` and `markdown`. Its `build_context()` classmethod assembles the variables a template sees.

`RecipientDiscoveryService` walks impacts to tenants to contact assignments. See [Recipient Discovery](../messaging/recipient-discovery.md).

`ical_generation` builds BCOP-compliant iCal bodies for notification attachments. It is distinct from `ical_utils.py`, which serves the subscribable calendar feed.

## Request paths worth knowing

**The iCal feed** (`MaintenanceICalView`) is not a model view and is mounted directly at `ical/maintenances.ics`. It accepts three authentication methods, in order: a `token` query parameter, an `Authorization` header, then session auth. The query-parameter path exists because calendar clients cannot set headers, and it validates both v1 and v2 NetBox token formats by hand. The view computes an ETag from the result count, the newest `last_updated`, and the query parameters, so feed readers polling every fifteen minutes mostly get a 304.

**The dashboard** (`DashboardView`) is a plain `View`, not an `ObjectListView`, and runs a fixed set of aggregate queries. See [Dashboard](../events/dashboard.md).

**Status changes on a prepared notification** are REST-API-only. The web UI deliberately does not expose the field, because a direct write would skip the recipient snapshot and the approval stamps that the state machine applies. See [Approval Workflow](../messaging/workflow.md).

## Extending from another plugin

Two extension points are supported and covered on their own pages:

- Register a site and location resolver so a new target type becomes filterable. See [Site and Location Resolvers](resolvers.md).
- Add your content type to `allowed_content_types` so impacts can point at it, which also gives it an event history panel. See [Template Extensions](template-extensions.md).

Both need a NetBox restart to take effect, since the resolver registry and the generated template extension classes are built at import time.
