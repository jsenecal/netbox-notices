# Templates

A `NotificationTemplate` is the Jinja source for an outgoing notification, together with the rules that decide when it applies and who it goes to. Templates are managed under **Notices > Messaging > Notification Templates**.

This page covers the model, the rendering context, and how templates become notification kinds, override each other and merge. For the states a rendered notification moves through, see [Approval Workflow](workflow.md). For how contacts are found, see [Recipient Discovery](recipient-discovery.md).

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
| `highest_impact` | The worst level across `impacts`, ranked `OUTAGE`, `DEGRADED`, `REDUCED-REDUNDANCY`, `NO-IMPACT`. Missing or unrecognised levels are ignored; `NO-IMPACT` when there are no impacts. |

Present only when the notification is linked to an event:

| Variable | Value |
|---|---|
| `maintenance` or `outage` | The event, under a key named for its model |
| `tenant_impacts` | `impacts` narrowed to those whose target belongs to `tenant`. Falls back to the full list when no tenant is given. |

The event key is named after the model, so a maintenance is available as `{{ maintenance }}` and an outage as `{{ outage }}`. There is no generic `event` variable. A template with `event_type = both` has to handle both names:

```jinja
{% set event = maintenance if maintenance is defined else outage %}
```

`build_context()` accepts arbitrary keyword arguments and merges them in last, so a caller generating notifications can inject anything else a template needs. iCal rendering uses this to add `message_sequence`, which is therefore available in an `ical_template` but not in a body template. See [Outgoing Notifications](../outgoing-notifications.md).

`netbox_url` is empty unless `BASE_URL` is set in `configuration.py`. Absolute links in a template need it, so set it before relying on them:

```jinja
View details: {{ netbox_url }}{{ maintenance.get_absolute_url() }}
```

## Syntax and filters

Templates are standard Jinja2. The environment runs with `autoescape=False`, which suits Markdown and plain text bodies but means an HTML template is responsible for escaping anything that could contain markup. Provider-supplied fields such as `summary` and `impact` are the ones to watch.

Unlike Django templates, Jinja does not call methods for you: a model method needs parentheses, as in `{{ maintenance.get_absolute_url() }}` or `{% if maintenance.has_timezone_difference() %}`. Without them the expression renders the bound method's representation, and an `if` on it is always true.

### Sandbox

Templates are written by users, so they render in Jinja's [sandboxed environment](https://jinja.palletsprojects.com/en/stable/sandbox/) (`SandboxedEnvironment`). Ordinary attribute access and method calls on the context objects work as shown on this page, but the sandbox blocks what could reach into Python internals or change data:

- Attributes whose names start with an underscore (such as `__class__` or `_meta`) are unsafe. Printed on their own they come out as an undefined value (empty, and false in an `if`); reading an attribute of one or calling it raises a security error.
- Calling an unsafe callable raises a security error. That covers methods Django marks as modifying data (`alters_data`), such as `save()` and `delete()` on a model or `.delete()` on a related manager.

A security error fails the render like any other template error: the preview and the API report that template's notifications as failed, and nothing is written for them.

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
{% if maintenance.has_timezone_difference() %}
Times shown in {{ maintenance.original_timezone }}:
{{ maintenance.get_start_in_original_tz() }} to {{ maintenance.get_end_in_original_tz() }}
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

## Kinds, overrides and base templates

Every template that is not a base template is an independent notification *kind*: generating notifications for an event produces drafts for each kind whose `event_type` fits. A kind is a template that extends nothing, or extends a base template.

A template that extends a *non-base* template is an **override** of it. It does not produce notifications of its own; instead, for the recipient groups its scopes match, it replaces the template it extends. This lets a general "maintenance" kind carry a customised variant for one tenant:

| Template | Extends | Scopes | Role |
|---|---|---|---|
| `Maintenance` | none | none | Kind, used for every group |
| `Maintenance - Acme` | `Maintenance` | tenant Acme | Override, used for Acme only |

Overrides can nest (an override of an override); at each level the highest-scoring matching override wins. Two rules are validated on save:

- An override must use the same granularity as the template it extends.
- `extends` cycles are rejected.

A **base template** (`is_base_template = True`) is only a layout. It never produces notifications on its own and is not a kind; kinds and overrides extend it to share blocks and fallback fields.

### Block inheritance

Children use Jinja block syntax:

```jinja
{% extends "base" %}

{% block content %}
Provider {{ maintenance.provider.name }} has scheduled work.
{% endblock %}
```

`"base"` always means the template's own immediate parent in the `extends` chain, at every level. In a three-level chain each template's `{% extends "base" %}` resolves to the one above it, never to itself. The full rendering context is available inside every level.

### Body format

`body_format` decides how the rendered body is stored:

| Format | `body_text` | `body_html` |
|---|---|---|
| `markdown` | The rendered Markdown, as written | The Markdown converted to HTML |
| `html` | The rendered HTML with tags stripped | The rendered HTML |
| `text` | The rendered text | Empty |

The format used is the one on the template whose body is rendered, which is the most specific template in the chain with a non-empty body.

## Scopes and matching

A `TemplateScope` attaches a template to a NetBox object, in the manner of config contexts. When several overrides could apply, scopes decide which wins.

| Field | Notes |
|---|---|
| `content_type` | The object type this scope matches. |
| `object_id` | A specific object, or null to match every object of that type. |
| `event_type` | Optional filter on event type. |
| `event_status` | Optional filter on event status, for example `CONFIRMED`. |
| `weight` | Added to the template's weight on a match. Default 1000. |

Scopes are edited from the parent template's page. A unique constraint on `(template, content_type, object_id, event_type, event_status)` stops the same scope being added twice.

### How a group is matched

For each recipient group, `TemplateMatchingService` scores a template against the group's context (event, tenant, provider). A template with no scopes always applies, at its own `weight`. A template with scopes applies only if at least one scope matches, and its score is its `weight` plus the weight of every matching scope. A kind that does not apply to a group produces nothing for it.

A scope matches when all of its populated filters agree:

- `event_type`, if set, must equal the context event type. A scope set to `both` matches any event but not the no-event case.
- `event_status`, if set, must equal the event's status. This check is skipped when the context has no status.
- The object must match. The service resolves the context object for the scope's content type, preferring the explicitly supplied tenant or provider, then falling back to an attribute of the same name on the event. A null `object_id` is a wildcard and matches any object of that type. When no context object can be resolved at all, only a wildcard scope matches.

So a scope on `tenancy.tenant` with no `object_id` matches every tenant, while one naming a specific tenant only matches that one, and both add their weight when they match.

Starting at the kind, the generator then descends into the highest-scoring override that applies to the group, repeatedly. The result is the group's *chain*: the chosen overrides, most specific first, then the kind, then its base templates.

### Merging

The chain is folded into one configuration, field by field, from the most specific template to the least:

| Field | Rule |
|---|---|
| `subject_template` | First non-empty wins |
| `body_template` | First non-empty wins, and carries its `body_format` with it |
| `css_template` | First non-empty wins |
| `ical_template` | First non-empty wins |
| `headers_template` | Merged key by key, the more specific value winning per key |
| `include_ical` | True if true on any template in the chain |
| `contact_roles` | Union across the chain |
| `contact_priorities` | Union across the chain |
| `granularity` | Taken from the kind, not from an override |

Merging follows the `extends` chain only. Other templates that happen to match the same event do not contribute: they are separate kinds. The two union fields still widen the recipient list, so a base template that adds a role or priority applies it to every kind that extends it.

## See also

- [Recipient Discovery](recipient-discovery.md)
- [Approval Workflow](workflow.md)
- [Outgoing Notifications](../outgoing-notifications.md) for the overall architecture
- [REST API](../api/rest-api.md) for the template and notification endpoints
