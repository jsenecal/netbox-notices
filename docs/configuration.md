# Configuration

All plugin behaviour is configured through the `PLUGINS_CONFIG["notices"]` dict in `configuration.py`. Every key has a default, so an empty dict is a valid configuration. NetBox must be restarted after any change.

## Settings reference

| Key | Default | Description |
|-----|---------|-------------|
| `allowed_content_types` | `["circuits.Circuit", "dcim.Device", "dcim.PowerFeed", "dcim.Site"]` | Content types that may be the target of an `Impact`. Format: `app_label.ModelName`. |
| `ical_past_days_default` | `30` | How many days of past events to include in the iCal feed when the request does not specify `past_days`. |
| `ical_cache_max_age` | `900` | `Cache-Control: max-age` (seconds) sent with the iCal subscription feed. |
| `ical_token_placeholder` | `"changeme"` | Placeholder string shown in the calendar UI's iCal subscription URL. Cosmetic only; the user replaces it with their own API token. |
| `event_history_days` | `30` | Window (days, looking back from now) for the event-history widgets shown on Provider, Circuit, Device, etc detail pages. |

The settings are declared in `notices/__init__.py` as the `default_settings` dict on `NoticesConfig`. The defaults for `allowed_content_types` come from `notices/constants.py:DEFAULT_ALLOWED_CONTENT_TYPES`.

## Example: full configuration

```python
PLUGINS_CONFIG = {
    "notices": {
        "allowed_content_types": [
            "circuits.Circuit",
            "dcim.Device",
            "dcim.Interface",
            "dcim.PowerFeed",
            "dcim.PowerPanel",
            "dcim.Rack",
            "dcim.Site",
            "ipam.IPAddress",
            "ipam.Prefix",
            "virtualization.VirtualMachine",
            "virtualization.VMInterface",
        ],
        "ical_past_days_default": 14,
        "ical_cache_max_age": 600,
        "event_history_days": 60,
    },
}
```

## allowed_content_types

This is the most important setting. It controls which NetBox object types can be linked to an event via the `Impact` model.

### Behaviour

- Forms (`ImpactForm`) only offer object types from this list.
- The REST API rejects `POST /api/plugins/notices/impact/` requests where `target_content_type` is not in the list. Validation happens in `Impact.clean()`.
- Object detail pages render the "Maintenance and Outage History" widget only when their type is in the list (the widget is registered dynamically per allowed type at app startup, see `notices/template_content.py`).
- The list is case-insensitive at validation time, but the canonical form is `app_label.ModelName` with the model name in lowercase as Django stores content types.

### Adding a new content type

When you add a new content type to the list:

1. **Restart NetBox.** Template extensions are registered at app-ready time and will not pick up the new type until restart.
2. **Register a site/location resolver** for the new type (see [Site and Location Resolvers](developer/resolvers.md)). Without a resolver, the plugin emits a system check warning at startup, and impacts on objects of that type will not be findable via the site/region/location filters on the maintenance and outage list views.

### Common content types

| Content type | Notes |
|--------------|-------|
| `circuits.Circuit` | Built-in resolver maps to the circuit's terminations -> sites. |
| `dcim.Device` | Built-in resolver returns the device's site (and location, if set). |
| `dcim.PowerFeed` | Built-in resolver walks `PowerPanel.site` / `PowerPanel.location`. |
| `dcim.Site` | Built-in resolver returns the site itself. |
| `dcim.Interface` | Needs a custom resolver (resolves through `Interface.device`). |
| `dcim.Rack` | Needs a custom resolver (resolves through `Rack.site` / `Rack.location`). |
| `virtualization.VirtualMachine` | Needs a custom resolver (resolves through `VM.site` or `VM.cluster.site`). |
| `ipam.Prefix` / `ipam.IPAddress` | Needs a custom resolver (typically scoped via `vrf` -> `tenant` rather than site). |

## iCal feed settings

Three settings shape the iCal feed behaviour:

- `ical_past_days_default` is the default for the `?past_days=` query parameter. The view caps the user-provided value at 365 days.
- `ical_cache_max_age` controls the `Cache-Control: public, max-age=<n>` header on subscription responses. ETag and `Last-Modified` are always sent and are derived from the maintenance queryset's `last_updated` aggregate. Set lower for fresher feeds, higher to reduce server load.
- `ical_token_placeholder` is shown verbatim in the calendar template's "Subscribe" link. Replace it with a string that hints to your users they need to drop in their own token (for example `your-api-token-here`).

The cache headers, ETag computation, and download-vs-subscribe handshake are documented in [Calendar and iCal Feed](events/calendar-and-ical.md).

## event_history_days

Controls the time window for the per-object event widgets injected onto NetBox detail pages by `notices.template_content`:

- `ProviderEventsExtension` ("Maintenance and Outage Events" on Provider pages).
- The dynamic per-content-type extensions ("Maintenance and Outage History" on Device, Circuit, Site, etc).

Events are included if they meet any of:

- `start >= now - event_history_days`, or
- `end >= now` (still active or scheduled in the future), or
- `end is null` (open-ended Outage with no resolution time).

Lowering this value declutters busy detail pages; raising it gives historical context.

## Settings precedence and changes

Settings are read at app load time and merged with `default_settings`. Restart NetBox (`netbox` and `netbox-rq`) after any change.

Per-tenant or per-deployment overrides (for example, different `allowed_content_types` for staging vs production) are typically managed by templating `configuration.py` from your config-management system; the plugin itself does not provide a runtime override mechanism.
