# Outgoing Notifications

This document describes the outgoing notification system in netbox-notices for composing and preparing messages based on maintenance and outage events.

## Overview

The outgoing notifications feature provides a complete message composition system that:

- **Composes messages** from Jinja2 templates with full access to event and impact data
- **Discovers recipients** automatically from NetBox contacts via tenant relationships
- **Generates iCal attachments** for maintenance events following the BCOP standard
- **Tracks message lifecycle** from draft through delivery with full audit trail

This is a **content/delivery separation** architecture:

- **This plugin handles:** Templates, recipient discovery, message composition, and state tracking
- **External systems handle:** Actual delivery (SMTP, Slack, Teams, webhooks, etc.)

## Architecture

```
                                    ┌─────────────────────┐
                                    │   Maintenance or    │
                                    │   Outage Event      │
                                    └──────────┬──────────┘
                                               │
                    ┌──────────────────────────┼──────────────────────────┐
                    │                          │                          │
                    ▼                          ▼                          ▼
           ┌────────────────┐        ┌────────────────┐        ┌────────────────┐
           │ MessageTemplate│        │  TemplateScope │        │   Contacts     │
           │   (Jinja2)     │◄───────│   (Matching)   │        │  (Recipients)  │
           └────────┬───────┘        └────────────────┘        └────────┬───────┘
                    │                                                   │
                    └──────────────────┬────────────────────────────────┘
                                       │
                                       ▼
                              ┌────────────────┐
                              │PreparedMessage │
                              │  (Rendered)    │
                              └────────┬───────┘
                                       │
                                       ▼
                              ┌────────────────┐
                              │   REST API     │
                              │ (Pull Model)   │
                              └────────┬───────┘
                                       │
                                       ▼
                              ┌────────────────┐
                              │ External       │
                              │ Delivery       │
                              │ System         │
                              └────────────────┘
```

## Models

### MessageTemplate

A Jinja template for generating outgoing notifications. Templates can be scoped to specific objects (tenants, providers, sites, etc.) via TemplateScope assignments, similar to Config Contexts.

| Field | Type | Description |
|-------|------|-------------|
| `name` | CharField | Human-readable template name |
| `slug` | SlugField | URL-safe identifier (unique) |
| `description` | TextField | Optional description |
| `event_type` | CharField | Which events this applies to: `maintenance`, `outage`, `both`, or `none` |
| `granularity` | CharField | Message grouping: `per_event`, `per_tenant`, or `per_impact` |
| `subject_template` | TextField | Jinja template for email subject |
| `body_template` | TextField | Jinja template for message body |
| `body_format` | CharField | Output format: `markdown`, `html`, or `text` |
| `css_template` | TextField | CSS styles for HTML output |
| `headers_template` | JSONField | Email headers as Jinja templates |
| `include_ical` | BooleanField | Generate iCal attachment (Maintenance only) |
| `ical_template` | TextField | Jinja template for iCal content |
| `contact_roles` | M2M | Contact roles to include in recipient discovery |
| `contact_priorities` | ArrayField | Contact priorities: `primary`, `secondary`, `tertiary` |
| `is_base_template` | BooleanField | Whether this can be extended by other templates |
| `extends` | ForeignKey | Parent template for Jinja block inheritance |
| `weight` | IntegerField | Base weight for template matching (higher wins) |

### TemplateScope

Links a MessageTemplate to NetBox objects for Config Context-like matching. When generating messages, templates with matching scopes are selected and merged by weight.

| Field | Type | Description |
|-------|------|-------------|
| `template` | ForeignKey | Parent MessageTemplate |
| `content_type` | ForeignKey | Type of object (e.g., Tenant, Provider, Site) |
| `object_id` | BigIntegerField | Specific object ID, or null for all of that type |
| `event_type` | CharField | Filter by event type (optional) |
| `event_status` | CharField | Filter by event status (optional) |
| `weight` | IntegerField | Weight for merge priority (higher wins) |

### PreparedMessage

A rendered message ready for delivery. Stores a snapshot of rendered content and recipients at generation time. Status transitions are validated via state machine.

| Field | Type | Description |
|-------|------|-------------|
| `template` | ForeignKey | Source MessageTemplate |
| `event_content_type` | ForeignKey | Type of linked event (optional) |
| `event_id` | BigIntegerField | ID of linked event (optional) |
| `status` | CharField | Current status: `draft`, `ready`, `sent`, `delivered`, `failed` |
| `contacts` | M2M | Contacts to receive this message |
| `recipients` | JSONField | Snapshot of recipients at approval time (read-only) |
| `subject` | CharField | Rendered subject line |
| `body_text` | TextField | Rendered plain text body |
| `body_html` | TextField | Rendered HTML body |
| `headers` | JSONField | Rendered email headers |
| `css` | TextField | Rendered CSS |
| `ical_content` | TextField | Rendered iCal attachment |
| `approved_by` | ForeignKey | User who approved the message |
| `approved_at` | DateTimeField | When the message was approved |
| `sent_at` | DateTimeField | When the message was sent |
| `delivered_at` | DateTimeField | When delivery was confirmed |
| `viewed_at` | DateTimeField | When the message was viewed |

## Template Creation

### Event Type Targeting

The `event_type` field determines which events a template can be used with:

| Value | Description |
|-------|-------------|
| `maintenance` | Only for Maintenance events |
| `outage` | Only for Outage events |
| `both` | For both Maintenance and Outage events |
| `none` | Standalone messages not linked to events |

### Granularity

The `granularity` field controls how messages are grouped when generated from events:

| Value | Description |
|-------|-------------|
| `per_event` | One message for the entire event (all impacts in one message) |
| `per_tenant` | One message per affected tenant (group impacts by tenant) |
| `per_impact` | One message per impact record (individual notifications) |

### Template Syntax

Templates use Jinja2 syntax with full support for:

- Variable interpolation: `{{ maintenance.name }}`
- Conditionals: `{% if maintenance.status == 'CONFIRMED' %}...{% endif %}`
- Loops: `{% for impact in impacts %}...{% endfor %}`
- Filters: `{{ maintenance.start|ical_datetime }}`
- Block inheritance: `{% extends "base" %}{% block content %}...{% endblock %}`

**Example subject template:**

```jinja
[{{ maintenance.status }}] {{ maintenance.provider.name }} Maintenance: {{ maintenance.name }}
```

**Example body template:**

```jinja
# Maintenance Notification

**Provider:** {{ maintenance.provider.name }}
**Maintenance ID:** {{ maintenance.name }}
**Status:** {{ maintenance.status }}

## Schedule

- **Start:** {{ maintenance.start }}
- **End:** {{ maintenance.end }}

## Affected Services

{% for impact in tenant_impacts %}
- {{ impact.target }} ({{ impact.impact }})
{% endfor %}

## Summary

{{ maintenance.summary }}

---
This is an automated notification from NetBox.
View details: {{ netbox_url }}{{ maintenance.get_absolute_url }}
```

### Context Variables

#### All Templates

| Variable | Description |
|----------|-------------|
| `now` | Current datetime |
| `netbox_url` | NetBox base URL |
| `tenant` | Target tenant (when using per_tenant granularity) |
| `impacts` | All Impact records for this message scope |
| `contacts` | List of recipient Contact objects |

#### Maintenance Event-Linked

| Variable | Description |
|----------|-------------|
| `maintenance` | The Maintenance object |
| `maintenance.provider` | Provider object |
| `maintenance.status` | Current status (TENTATIVE, CONFIRMED, etc.) |
| `maintenance.start` | Scheduled start time |
| `maintenance.end` | Scheduled end time |
| `maintenance.summary` | Maintenance summary text |
| `tenant_impacts` | Impacts filtered for current tenant |
| `highest_impact` | Worst impact level (OUTAGE > DEGRADED > REDUCED-REDUNDANCY > NO-IMPACT) |
| `message_sequence` | Notification count for this tenant+event |

#### Outage Event-Linked

| Variable | Description |
|----------|-------------|
| `outage` | The Outage object |
| `outage.reported_at` | When the outage was reported |
| `outage.estimated_time_to_repair` | ETR if known |
| `outage.status` | Current status (REPORTED, INVESTIGATING, etc.) |
| `outage.end` | Resolution time (if resolved) |

#### Per-Impact Granularity

| Variable | Description |
|----------|-------------|
| `impact` | The specific Impact record |
| `impact.target` | The impacted object |
| `object` | Alias for `impact.target` |

### Custom Filters

#### ical_datetime

Formats a datetime as an iCal-compliant datetime string (YYYYMMDDTHHMMSSZ in UTC).

```jinja
DTSTART:{{ maintenance.start|ical_datetime }}
```

Output: `DTSTART:20260122T143000Z`

#### markdown

Renders Markdown text to HTML. Supports tables, fenced code blocks, and line breaks.

```jinja
{{ maintenance.summary|markdown }}
```

## Recipient Discovery

Recipients are discovered automatically from NetBox contacts based on the template configuration:

### Flow

1. **Collect target objects** from event impacts based on granularity
2. **Resolve tenants** from impacted objects via `object.tenant`
3. **Find contacts** by querying ContactAssignments where:
   - Role is in template's `contact_roles`
   - Priority is in template's `contact_priorities`
   - Priority is not `inactive`
4. **Populate PreparedMessage** with discovered contacts
5. **Snapshot recipients** when message transitions to `ready` status

### Example

A maintenance event impacts two circuits:

- Circuit A belongs to Tenant X
- Circuit B belongs to Tenant Y

With `granularity=per_tenant` and `contact_roles=[NOC]`:

1. System creates two PreparedMessages (one per tenant)
2. For Tenant X's message, discovers contacts with NOC role assigned to Tenant X
3. For Tenant Y's message, discovers contacts with NOC role assigned to Tenant Y

### Standalone Messages

For templates with `event_type=none`:

- No automatic recipient discovery
- User manually selects contacts while in `draft` status
- Same approval and delivery flow applies

## Template Matching

When generating messages from an event, templates are matched and merged based on scopes.

### Matching Algorithm

1. **Filter by event type:**
   - Maintenance events match templates where `event_type` is `maintenance` or `both`
   - Outage events match templates where `event_type` is `outage` or `both`

2. **Score templates by scope matches:**
   ```
   score = template.weight
   for each scope in template.scopes:
       if scope matches context:
           score += scope.weight
   ```

3. **Select templates:**
   - Include templates with at least one matching scope
   - Include templates with no scopes (global defaults)

### Scope Matching

A scope matches when:

- Its `content_type` matches an object in the context (tenant, provider, etc.)
- Its `object_id` is null (matches all of that type) OR matches the specific object
- Its `event_type` is null OR matches the current event type
- Its `event_status` is null OR matches the current event status

### Field-Level Merging

When multiple templates match, fields are merged by weight (higher wins):

- `subject_template`
- `body_template`
- `headers_template`
- `css_template`
- `ical_template`

If a higher-weighted template's field is empty/null, the value is inherited from lower-weighted templates.

## iCal Generation

### When Generated

iCal attachments are generated when:

1. Template has `include_ical=True`
2. Message is linked to a Maintenance event (not Outage)
3. Template has a non-empty `ical_template`

### BCOP Standard

The iCal format follows the [BCOP (Best Current Operational Practice) standard](https://github.com/mjethanandani/circuit-maintenance) for circuit maintenance notifications.

### Required X-MAINTNOTE-* Properties

| Property | Description |
|----------|-------------|
| `X-MAINTNOTE-PROVIDER` | Service provider identifier (e.g., provider slug) |
| `X-MAINTNOTE-ACCOUNT` | Customer account identifier (e.g., tenant name) |
| `X-MAINTNOTE-MAINTENANCE-ID` | Unique maintenance identifier |
| `X-MAINTNOTE-OBJECT-ID` | Affected service/circuit ID(s) |
| `X-MAINTNOTE-IMPACT` | Impact level: NO-IMPACT, REDUCED-REDUNDANCY, DEGRADED, OUTAGE |
| `X-MAINTNOTE-STATUS` | Status: TENTATIVE, CONFIRMED, CANCELLED, IN-PROCESS, COMPLETED |

### Example BCOP Template

```ical
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//YourCompany//netbox-notices//EN
METHOD:REQUEST
BEGIN:VEVENT
DTSTAMP:{{ now|ical_datetime }}
DTSTART:{{ maintenance.start|ical_datetime }}
DTEND:{{ maintenance.end|ical_datetime }}
UID:{{ maintenance.pk }}-{{ tenant.pk }}@yourcompany.com
SUMMARY:{{ maintenance.name }} - {{ maintenance.provider.name }}
DESCRIPTION:{{ maintenance.summary | replace('\n', '\\n') }}
ORGANIZER;CN="{{ maintenance.provider.name }}":mailto:noc@yourcompany.com
SEQUENCE:{{ message_sequence|default(0) }}
X-MAINTNOTE-PROVIDER:{{ maintenance.provider.slug }}
X-MAINTNOTE-ACCOUNT:{{ tenant.name }}
X-MAINTNOTE-MAINTENANCE-ID;X-MAINTNOTE-PRECEDENCE=PRIMARY:{{ maintenance.name }}
{% for impact in tenant_impacts %}
X-MAINTNOTE-OBJECT-ID:{{ impact.target }}
{% endfor %}
X-MAINTNOTE-IMPACT:{{ highest_impact }}
X-MAINTNOTE-STATUS:{{ maintenance.status }}
END:VEVENT
END:VCALENDAR
```

## State Machine

PreparedMessage status transitions are enforced by a state machine with validation.

### Status Workflow

```
         ┌─────────────────────────────────┐
         │                                 │
         ▼                                 │
      [draft] ──────> [ready] ──────> [sent] ──────> [delivered]
         │               │                │
         │               │                │
         ▼               │                ▼
      (delete)           │            [failed]
                         │                │
                         │                │
                         └────────────────┘
                              (retry)
```

### Valid Transitions

| From | To | Trigger |
|------|----|---------|
| `draft` | `ready` | Approve message |
| `draft` | (delete) | Delete draft |
| `ready` | `sent` | External system picks up message |
| `sent` | `delivered` | Delivery confirmed |
| `sent` | `failed` | Delivery failed |
| `failed` | `ready` | Retry delivery |

### Validation Requirements

**draft -> ready (approval):**

- `recipients` must not be empty (computed from `contacts`)
- Sets `approved_by` to current user
- Sets `approved_at` to current timestamp
- Snapshots recipients JSON from contacts

**ready -> sent:**

- Sets `sent_at` to provided `timestamp` or current time

**sent -> delivered:**

- Sets `delivered_at` to provided `timestamp` or current time

### Optional Timestamp Parameter

External delivery systems may process messages in batches or have delayed polling. The `timestamp` parameter allows specifying when a transition actually occurred:

```http
PATCH /api/plugins/notices/prepared-messages/1/
{
    "status": "sent",
    "timestamp": "2026-01-27T10:00:00Z",
    "message": "Sent via batch processor"
}
```

**Timestamp validation:**

- Cannot be in the future
- Must respect chronological order:
  - `sent_at` >= `approved_at`
  - `delivered_at` >= `sent_at`

If `timestamp` is not provided, the current time is used.

## REST API

### Endpoints

```
GET    /api/plugins/notices/message-templates/
POST   /api/plugins/notices/message-templates/
GET    /api/plugins/notices/message-templates/{id}/
PUT    /api/plugins/notices/message-templates/{id}/
PATCH  /api/plugins/notices/message-templates/{id}/
DELETE /api/plugins/notices/message-templates/{id}/

GET    /api/plugins/notices/prepared-messages/
POST   /api/plugins/notices/prepared-messages/
GET    /api/plugins/notices/prepared-messages/{id}/
PATCH  /api/plugins/notices/prepared-messages/{id}/
DELETE /api/plugins/notices/prepared-messages/{id}/
```

### Filtering PreparedMessages

Query messages by status for delivery system integration:

```http
GET /api/plugins/notices/prepared-messages/?status=ready
```

### Creating a MessageTemplate

```http
POST /api/plugins/notices/message-templates/
Content-Type: application/json
Authorization: Token YOUR_API_TOKEN

{
    "name": "Maintenance Notification",
    "slug": "maintenance-notification",
    "event_type": "maintenance",
    "granularity": "per_tenant",
    "subject_template": "[{{ maintenance.status }}] {{ maintenance.provider.name }}: {{ maintenance.name }}",
    "body_template": "# Maintenance Notice\n\n{{ maintenance.summary }}",
    "body_format": "markdown",
    "include_ical": true,
    "ical_template": "BEGIN:VCALENDAR\n...\nEND:VCALENDAR",
    "contact_priorities": ["primary", "secondary"],
    "weight": 1000
}
```

**Response:**

```json
{
    "id": 1,
    "url": "/api/plugins/notices/message-templates/1/",
    "display": "Maintenance Notification",
    "name": "Maintenance Notification",
    "slug": "maintenance-notification",
    "event_type": "maintenance",
    "granularity": "per_tenant",
    ...
}
```

### Creating a PreparedMessage

```http
POST /api/plugins/notices/prepared-messages/
Content-Type: application/json
Authorization: Token YOUR_API_TOKEN

{
    "template_id": 1,
    "event_content_type": "maintenance",
    "event_id": 42,
    "subject": "Scheduled Maintenance: MAINT-001",
    "body_text": "This is a test notification...",
    "contact_ids": [1, 2, 3]
}
```

### Updating Message Status

External delivery systems update status after processing:

**Mark as sent:**

```http
PATCH /api/plugins/notices/prepared-messages/1/
Content-Type: application/json
Authorization: Token YOUR_API_TOKEN

{
    "status": "sent",
    "message": "Sent via SMTP relay"
}
```

**Mark as sent with custom timestamp (for batch processing):**

```http
PATCH /api/plugins/notices/prepared-messages/1/
Content-Type: application/json
Authorization: Token YOUR_API_TOKEN

{
    "status": "sent",
    "timestamp": "2026-01-22T10:30:00Z",
    "message": "Sent via batch processor"
}
```

**Mark as delivered:**

```http
PATCH /api/plugins/notices/prepared-messages/1/
Content-Type: application/json
Authorization: Token YOUR_API_TOKEN

{
    "status": "delivered",
    "timestamp": "2026-01-22T10:31:00Z",
    "message": "Delivered to 5 recipients"
}
```

**Mark as failed (for retry):**

```http
PATCH /api/plugins/notices/prepared-messages/1/
Content-Type: application/json
Authorization: Token YOUR_API_TOKEN

{
    "status": "failed",
    "message": "SMTP connection refused"
}
```

### Journal Entries

When a `message` field is included in status updates, a journal entry is automatically created:

| New Status | Journal Kind |
|------------|--------------|
| `ready` | info |
| `sent` | info |
| `delivered` | success |
| `failed` | warning |

## Integration

### Pull-Based API Model

The recommended integration pattern is pull-based:

1. External delivery system polls for ready messages:
   ```http
   GET /api/plugins/notices/prepared-messages/?status=ready
   ```

2. For each message, the delivery system:
   - Extracts recipient emails from `recipients` array
   - Sends the message via appropriate channel (email, Slack, etc.)
   - Updates status to `sent`
   - Updates status to `delivered` or `failed` based on result

### Webhook Integration

For push-based delivery, use NetBox's built-in Event Rules:

1. Go to **Operations > Event Rules**
2. Create a rule for `PreparedMessage` object type
3. Set condition: status = "ready"
4. Configure webhook URL for your delivery system

When a PreparedMessage transitions to `ready` status, NetBox will POST the message data to your webhook endpoint.

### Example Delivery Script

```python
#!/usr/bin/env python3
"""Example script to deliver prepared messages via SMTP."""

import requests
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage

NETBOX_URL = "https://netbox.example.com"
API_TOKEN = "your-api-token"
SMTP_HOST = "smtp.example.com"

headers = {"Authorization": f"Token {API_TOKEN}"}

# Fetch ready messages
response = requests.get(
    f"{NETBOX_URL}/api/plugins/notices/prepared-messages/",
    params={"status": "ready"},
    headers=headers,
)
messages = response.json()["results"]

for msg in messages:
    try:
        # Build email
        email = EmailMessage()
        email["Subject"] = msg["subject"]
        email["From"] = "noc@example.com"
        email["To"] = ", ".join(r["email"] for r in msg["recipients"])
        email.set_content(msg["body_text"])

        if msg["body_html"]:
            email.add_alternative(msg["body_html"], subtype="html")

        if msg["ical_content"]:
            email.add_attachment(
                msg["ical_content"].encode(),
                maintype="text",
                subtype="calendar",
                filename="maintenance.ics",
            )

        # Record send time before sending
        sent_at = datetime.now(timezone.utc).isoformat()

        # Send email
        with smtplib.SMTP(SMTP_HOST) as smtp:
            smtp.send_message(email)

        # Update status to sent with timestamp
        requests.patch(
            f"{NETBOX_URL}/api/plugins/notices/prepared-messages/{msg['id']}/",
            json={"status": "sent", "timestamp": sent_at, "message": "Sent via SMTP"},
            headers=headers,
        )

        # Update status to delivered
        delivered_at = datetime.now(timezone.utc).isoformat()
        requests.patch(
            f"{NETBOX_URL}/api/plugins/notices/prepared-messages/{msg['id']}/",
            json={
                "status": "delivered",
                "timestamp": delivered_at,
                "message": f"Delivered to {len(msg['recipients'])} recipients",
            },
            headers=headers,
        )

    except Exception as e:
        # Mark as failed
        requests.patch(
            f"{NETBOX_URL}/api/plugins/notices/prepared-messages/{msg['id']}/",
            json={"status": "failed", "message": str(e)},
            headers=headers,
        )
```

### Slack Integration Example

```python
"""Example: Post prepared messages to Slack."""

import requests

NETBOX_URL = "https://netbox.example.com"
API_TOKEN = "your-netbox-token"
SLACK_WEBHOOK = "https://hooks.slack.com/services/..."

headers = {"Authorization": f"Token {API_TOKEN}"}

response = requests.get(
    f"{NETBOX_URL}/api/plugins/notices/prepared-messages/",
    params={"status": "ready"},
    headers=headers,
)

for msg in response.json()["results"]:
    # Post to Slack
    slack_payload = {
        "text": msg["subject"],
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": msg["subject"]}},
            {"type": "section", "text": {"type": "mrkdwn", "text": msg["body_text"][:3000]}},
        ],
    }

    result = requests.post(SLACK_WEBHOOK, json=slack_payload)

    if result.ok:
        requests.patch(
            f"{NETBOX_URL}/api/plugins/notices/prepared-messages/{msg['id']}/",
            json={"status": "delivered", "message": "Posted to Slack"},
            headers=headers,
        )
```
