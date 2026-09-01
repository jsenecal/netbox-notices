# Templates

A `NotificationTemplate` is the Jinja source for an outgoing notification, together with the rules that decide when it applies and who it goes to. Templates are managed under **Notices > Messaging > Notification Templates**.

This page covers the model, the rendering context, and how the plugin picks a template out of several candidates. For the states a rendered notification moves through, see [Approval Workflow](workflow.md). For how contacts are found, see [Recipient Discovery](recipient-discovery.md).

## Model

| Field | Type | Notes |
|-------|------|-------|
| `name` | CharField (100) | Required. |
| `slug` | SlugField | Unique. |
| `description` | TextField | Free text. |
| `event_type` | CharField (choices) | Which event types this template applies to. |
| `granularity` | CharField (choices) | How notifications are grouped. Default `per_tenant`. |
| `subject_template` | TextField | Jinja source for the subject line. Required. |
| `body_template` | TextField | Jinja source for the body. Required. |
| `body_format` | CharField (choices) | `markdown` (default), `html` or `text`. |
| `css_template` | TextField | Styles for HTML output. |
| `headers_template` | JSONField | Per-header Jinja sources. Accepts YAML on input. |
| `include_ical` | BooleanField | Generate an iCal attachment. Maintenance only. |
| `ical_template` | TextField | Jinja source for the iCal body. |
| `contact_roles` | M2M -> `tenancy.ContactRole` | Roles to include during discovery. |
| `contact_priorities` | ArrayField | Priorities to include, for example `["primary"]`. |
| `is_base_template` | BooleanField | Marks a template as extendable. |
| `extends` | FK -> `NotificationTemplate` | Parent template for Jinja block inheritance. |
| `weight` | IntegerField | Base matching weight. Default 1000. |
| `tags` | M2M -> NetBox Tag | Standard tagging. |

### Event type

`event_type` restricts which events a template is a candidate for.

| Value | Meaning |
|---|---|
| `maintenance` | Maintenance events only |
| `outage` | Outage events only |
| `both` | Either event type |
| `none` | Standalone notifications with no linked event |

Matching treats `both` as a match for either type. A template with `none` is only ever considered when there is no event in context, so `none` templates and event templates never compete.

### Granularity

`granularity` decides how many notifications one event produces.

| Value | Result |
|---|---|
| `per_event` | One notification covering every impact |
| `per_tenant` | One notification per affected tenant, the default |
| `per_impact` | One notification per impact record |

Granularity is consumed by recipient discovery, which returns a different shape for each value. See [Recipient Discovery](recipient-discovery.md).

## Rendering context

Templates are rendered by `TemplateRenderer`, whose `build_context()` classmethod assembles the variables. Only the following are provided.

Always present:

| Variable | Value |
|---|---|
| `now` | `timezone.now()` at render time |
| `netbox_url` | Django's `BASE_URL` setting, or an empty string if unset |
| `tenant` | The target tenant, or `None` |
| `impacts` | The `Impact` records in scope, or an empty list |

Present only when the notification is linked to an event:

| Variable | Value |
|---|---|
| `maintenance` or `outage` | The event, under a key named for its model |
| `tenant_impacts` | `impacts` narrowed to those whose target belongs to `tenant`. Falls back to the full list when no tenant is given. |
| `highest_impact` | The worst level across `impacts`, ranked `OUTAGE`, `DEGRADED`, `REDUCED-REDUNDANCY`, `NO-IMPACT`. Only set when `impacts` is non-empty. |

The event key is named after the model, so a maintenance is available as `{{ maintenance }}` and an outage as `{{ outage }}`. There is no generic `event` variable. A template with `event_type = both` has to handle both names:

```jinja
{% set event = maintenance if maintenance is defined else outage %}
```

`build_context()` accepts arbitrary keyword arguments and merges them in last, so a caller generating notifications can inject anything else a template needs. iCal rendering uses this to add `message_sequence`, which is therefore available in an `ical_template` but not in a body template. See [Outgoing Notifications](../outgoing-notifications.md).

`netbox_url` is empty unless `BASE_URL` is set in `configuration.py`. Absolute links in a template need it, so set it before relying on them:

```jinja
View details: {{ netbox_url }}{{ maintenance.get_absolute_url }}
```

## Syntax and filters

Templates are standard Jinja2. The environment runs with `autoescape=False`, which suits Markdown and plain text bodies but means an HTML template is responsible for escaping anything that could contain markup. Provider-supplied fields such as `summary` and `impact` are the ones to watch.

Two custom filters are registered.

**`ical_datetime`** formats a datetime as `YYYYMMDDTHHMMSSZ` in UTC, which is what iCal expects. Naive datetimes pass through unconverted; `None` renders as an empty string.

```jinja
DTSTART:{{ maintenance.start|ical_datetime }}
```

**`markdown`** renders Markdown to HTML with the `tables`, `fenced_code` and `nl2br` extensions enabled.

```jinja
{{ maintenance.summary|markdown }}
```

### Example

A subject line:

```jinja
[{{ maintenance.status }}] {{ maintenance.provider.name }} Maintenance: {{ maintenance.name }}
```

A Markdown body:

```jinja
# Scheduled Maintenance

**Provider:** {{ maintenance.provider.name }}
**Reference:** {{ maintenance.name }}
**Status:** {{ maintenance.status }}
**Impact:** {{ highest_impact }}

## Window

- Start: {{ maintenance.start }}
- End: {{ maintenance.end }}
{% if maintenance.has_timezone_difference %}
Times shown in {{ maintenance.original_timezone }}:
{{ maintenance.get_start_in_original_tz }} to {{ maintenance.get_end_in_original_tz }}
{% endif %}

## Affected services

{% for impact in tenant_impacts %}
- {{ impact.target }} ({{ impact.impact }})
{% endfor %}

{{ maintenance.summary }}
```

## Headers

`headers_template` is a JSON object whose values are Jinja sources, rendered per notification. The API serializer also accepts a YAML string and converts it, which is easier to write by hand:

```yaml
X-Event-Reference: "{{ maintenance.name }}"
X-Event-Status: "{{ maintenance.status }}"
Reply-To: "noc@example.com"
```

The rendered result is stored on the `PreparedNotification` and is for the delivery system to apply. The plugin does not send mail, so nothing here is validated as a real mail header.

## Inheritance

A shared layout can live in one template that others extend.

Mark the parent with `is_base_template = True` and point children at it with `extends`. Children then use Jinja block syntax:

```jinja
{% extends "base" %}

{% block content %}
Provider {{ maintenance.provider.name }} has scheduled work.
{% endblock %}
```

The literal name `base` is what `TemplateRenderer.render_with_inheritance()` registers the parent under by default.

`extends` is a plain FK with `on_delete=SET_NULL` and no cycle check, so a template pointing at itself, or two pointing at each other, is accepted by the model and fails at render time instead.

## Scopes and matching

A `TemplateScope` attaches a template to a NetBox object, in the manner of config contexts. When several templates could apply, scopes decide which wins.

| Field | Notes |
|---|---|
| `content_type` | The object type this scope matches. |
| `object_id` | A specific object, or null to match every object of that type. |
| `event_type` | Optional filter on event type. |
| `event_status` | Optional filter on event status, for example `CONFIRMED`. |
| `weight` | Added to the template's weight on a match. Default 1000. |

Scopes are edited from the parent template's page. A unique constraint on `(template, content_type, object_id, event_type, event_status)` stops the same scope being added twice.

### How a template is chosen

`TemplateMatchingService` takes a context of event, tenant and provider, and works in three steps.

First it selects candidates by event type. An event of a given type pulls templates matching that type or `both`; no event pulls templates with `none`.

Then it scores each candidate. A template with no scopes at all is a global default and always matches, at its own weight. A template with scopes matches only if at least one scope matches, and each matching scope adds its weight to the total.

Finally it sorts by score, highest first. `get_best_template()` returns the top one.

A scope matches when all of its populated filters agree:

- `event_type`, if set, must equal the context event type. A scope set to `both` matches any event but not the no-event case.
- `event_status`, if set, must equal the event's status. This check is skipped when the context has no status.
- The object must match. The service resolves the context object for the scope's content type, preferring the explicitly supplied tenant or provider, then falling back to an attribute of the same name on the event. A null `object_id` is a wildcard and matches any object of that type. When no context object can be resolved at all, only a wildcard scope matches.

So a scope on `tenancy.tenant` with no `object_id` matches every tenant, while one naming a specific tenant only matches that one, and both add their weight when they match.

### Merging

`get_merged_config()` folds every matching template into one configuration rather than using only the winner. The rules are per field, applied from highest score to lowest:

| Field | Rule |
|---|---|
| `subject_template` | First non-empty wins |
| `body_template` | First non-empty wins, and carries its `body_format` with it |
| `css_template` | First non-empty wins |
| `ical_template` | First non-empty wins |
| `extends` | First non-null wins |
| `headers_template` | Merged key by key, the higher-scored value winning per key |
| `include_ical` | True if true on any matching template |
| `contact_roles` | Union across all matching templates |
| `contact_priorities` | Union across all matching templates |

The two union fields are the ones that surprise people. A low-weight global template that adds a role or priority widens the recipient list for every notification, because the union is taken across everything that matched rather than only the winner.

## See also

- [Recipient Discovery](recipient-discovery.md)
- [Approval Workflow](workflow.md)
- [Outgoing Notifications](../outgoing-notifications.md) for the overall architecture
- [REST API](../api/rest-api.md) for the template and notification endpoints
