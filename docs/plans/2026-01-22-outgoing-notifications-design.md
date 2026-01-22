# Outgoing Notifications with Jinja Templates

**Date:** 2026-01-22
**Status:** Design Complete

## Overview

Add a message composition system to netbox-notices that prepares outgoing notifications using Jinja templates, discovers recipients from NetBox contacts, and exposes messages for external delivery systems.

### Architecture: Content/Delivery Separation

- **This plugin handles:** Templates, recipient discovery, message composition, message state
- **External system handles:** Actual delivery (SMTP, Slack, Teams, webhooks, etc.)
- **Communication:** REST API (pull model) + NetBox Event Rules (optional webhooks)

### Core Concepts

1. **MessageTemplate** - Jinja templates with Config Context-like scoping
2. **TemplateScope** - Links templates to NetBox objects, event types, and statuses with merge weights
3. **PreparedMessage** - Rendered message ready for delivery, with full lifecycle tracking

### Message Types

- **Event-linked** - Attached to Maintenance or Outage; gains access to event data, impacts, and (for Maintenance) iCal generation
- **Standalone** - General communications not tied to specific events (`event_type=none`)

---

## Data Models

### MessageTemplate

```python
class MessageTemplate(NetBoxModel):
    # Identity
    name = CharField(max_length=100)
    slug = SlugField(unique=True)
    description = TextField(blank=True)

    # Scope
    event_type = CharField(choices=[
        ('maintenance', 'Maintenance'),
        ('outage', 'Outage'),
        ('both', 'Both'),
        ('none', 'None (Standalone)'),
    ])

    # Generation behavior
    granularity = CharField(choices=[
        ('per_event', 'Per Event'),
        ('per_tenant', 'Per Tenant'),
        ('per_impact', 'Per Impact'),
    ])

    # Content templates
    subject_template = TextField()
    body_template = TextField()  # Supports Jinja {% block %} inheritance
    body_format = CharField(choices=[
        ('markdown', 'Markdown'),
        ('html', 'HTML'),
        ('text', 'Plain Text'),
    ])
    css_template = TextField(blank=True, null=True)
    headers_template = JSONField(default=dict)  # Accepts YAML input in UI/API

    # iCal (Maintenance only)
    include_ical = BooleanField(default=False)
    ical_template = TextField(blank=True, null=True)

    # Recipient discovery
    contact_roles = ManyToManyField('tenancy.ContactRole')
    contact_priorities = ArrayField(CharField())  # ['primary', 'secondary', 'tertiary']

    # Template inheritance
    is_base_template = BooleanField(default=False)
    extends = ForeignKey('self', null=True, blank=True, on_delete=SET_NULL)

    # Merge weight
    weight = IntegerField(default=1000)
```

### TemplateScope

Links templates to NetBox objects with Config Context-like matching:

```python
class TemplateScope(models.Model):
    template = ForeignKey(MessageTemplate, on_delete=CASCADE, related_name='scopes')

    # GenericFK to any NetBox object (Tenant, Provider, Site, etc.)
    content_type = ForeignKey(ContentType, on_delete=CASCADE)
    object_id = PositiveBigIntegerField(null=True, blank=True)  # null = all of this type

    # Event filtering
    event_type = CharField(null=True, blank=True, choices=[
        ('maintenance', 'Maintenance'),
        ('outage', 'Outage'),
        ('both', 'Both'),
        ('none', 'None'),
    ])
    event_status = CharField(null=True, blank=True)  # TENTATIVE, CONFIRMED, etc.

    # Merge priority
    weight = IntegerField(default=1000)

    class Meta:
        unique_together = ['template', 'content_type', 'object_id', 'event_type', 'event_status']
```

### PreparedMessage

```python
class PreparedMessage(NetBoxModel, JournalMixin):
    # Source
    template = ForeignKey(MessageTemplate, on_delete=PROTECT)

    # Linked event (optional)
    event_content_type = ForeignKey(ContentType, null=True, blank=True, on_delete=SET_NULL)
    event_id = PositiveBigIntegerField(null=True, blank=True)
    event = GenericForeignKey('event_content_type', 'event_id')

    # Status (state machine validated)
    status = CharField(choices=[
        ('draft', 'Draft'),
        ('ready', 'Ready'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
    ], default='draft')

    # Recipients
    contacts = ManyToManyField('tenancy.Contact')
    recipients = JSONField(default=list)  # Readonly snapshot: [{email, name, contact_id, role, priority}]

    # Rendered content (snapshot)
    subject = CharField(max_length=255)
    body_text = TextField()
    body_html = TextField(blank=True, null=True)
    headers = JSONField(default=dict)
    css = TextField(blank=True, null=True)
    ical_content = TextField(blank=True, null=True)

    # Approval tracking
    approved_by = ForeignKey(User, null=True, blank=True, on_delete=SET_NULL)
    approved_at = DateTimeField(null=True, blank=True)

    # Delivery tracking
    sent_at = DateTimeField(null=True, blank=True)
    delivered_at = DateTimeField(null=True, blank=True)
    viewed_at = DateTimeField(null=True, blank=True)
```

---

## State Machine

PreparedMessage status transitions (enforced via serializer validation):

```
         ┌─────────────────────────────────┐
         │                                 │
         v                                 │
      [draft] ──────> [ready] ──────> [sent] ──────> [delivered]
         │               │                │
         │               │                │
         v               │                v
      (delete)           │            [failed]
                         │                │
                         │                │
                         └────────────────┘
                              (retry)
```

**Valid transitions:**
- `draft` → `ready` (approve) - Requires non-empty `recipients`
- `draft` → (delete)
- `ready` → `sent` (delivery pickup)
- `sent` → `delivered`
- `sent` → `failed`
- `failed` → `ready` (retry)

**On `draft` → `ready`:**
- Recompute `recipients` from `contacts`
- Validate `recipients` is not empty
- Set `approved_by` and `approved_at`
- Create journal entry

---

## Recipient Discovery

### Flow

1. **Collect target objects:**
   - Event-linked: Impact records → target objects
   - `per_event`: All impacts
   - `per_tenant`: Group impacts by tenant
   - `per_impact`: Single impact

2. **Resolve tenants:**
   - For each impacted object, get its tenant via `object.tenant`

3. **Find contacts:**
   - For each tenant, query ContactAssignments where:
     - `role` in template's `contact_roles`
     - `priority` in template's `contact_priorities`
     - `priority` != `inactive`

4. **Populate PreparedMessage:**
   - Add discovered contacts to `contacts` M2M
   - User can edit while in `draft` status

5. **Snapshot recipients:**
   - On create and on `contacts` change: compute `recipients` JSON
   - Frozen when status leaves `draft`

### Standalone Messages

- No event link, no automatic discovery
- User manually selects contacts
- Same `draft` → `ready` → delivery flow

---

## Template Matching & Merging

### Matching Logic

When generating messages from an event:

1. **Filter by event type:**
   - Maintenance: templates where `event_type` in (`maintenance`, `both`)
   - Outage: templates where `event_type` in (`outage`, `both`)
   - Standalone: templates where `event_type` = `none`

2. **Score templates:**
   ```python
   score = template.weight
   for scope in template.scopes:
       if scope_matches_context(scope, tenant, provider, event_status, ...):
           score += scope.weight
   ```

3. **Select matching templates:**
   - Must have at least one matching scope, OR no scopes (global default)

### Merging (Field-Level)

Higher-weighted template's field wins:

- `subject_template`
- `body_template`
- `headers_template`
- `css_template`
- `ical_template`

If higher template's field is empty/null, inherit from lower.

### Merging (Block-Level)

Within `body_template`, Jinja `{% block %}` inheritance applies:

```jinja
{# Base template #}
{% block header %}Default header{% endblock %}
{% block content %}{% endblock %}
{% block footer %}Default footer{% endblock %}

{# Child template (extends base) #}
{% extends "base" %}
{% block content %}Custom content for Tenant X{% endblock %}
```

---

## Template Context Variables

### All Templates

| Variable | Description |
|----------|-------------|
| `now` | Current datetime |
| `netbox_url` | NetBox base URL |
| `contacts` | List of recipient Contact objects |
| `tenant` | Target tenant (when scoped) |

### Maintenance Event-Linked

| Variable | Description |
|----------|-------------|
| `maintenance` | The Maintenance object |
| `maintenance.provider` | Provider object |
| `maintenance.status` | Current status |
| `maintenance.start` / `end` | Scheduled window |
| `impacts` | All Impact records for this message scope |
| `tenant_impacts` | Impacts for current tenant (per_tenant/per_impact) |
| `highest_impact` | Worst impact level |
| `message_sequence` | Notification count for this tenant+event |

### Outage Event-Linked

| Variable | Description |
|----------|-------------|
| `outage` | The Outage object |
| `outage.reported_at` | When reported |
| `outage.estimated_time_to_repair` | ETR if known |
| `outage.status` | Current status |
| `outage.end` | Resolution time (if resolved) |

### Per-Impact Granularity

| Variable | Description |
|----------|-------------|
| `impact` | The specific Impact record |
| `impact.target` | The impacted object |
| `object` | Alias for `impact.target` |

### Custom Jinja Filters

- `ical_datetime` - Format as iCal datetime (YYYYMMDDTHHMMSSZ)
- `markdown` - Render Markdown to HTML

---

## iCal Generation (BCOP Compliance)

### When Generated

- Template has `include_ical=True`
- Message is linked to Maintenance (not Outage)
- `ical_template` is populated

### BCOP-Compliant Example (Documentation)

Users copy and customize this template:

```ical
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//YourCompany//netbox-notices//
BEGIN:VEVENT
DTSTAMP:{{ now|ical_datetime }}
DTSTART:{{ maintenance.start|ical_datetime }}
DTEND:{{ maintenance.end|ical_datetime }}
UID:{{ maintenance.pk }}-{{ tenant.pk }}@yourcompany.com
SUMMARY:{{ maintenance.summary }}
ORGANIZER;CN="{{ maintenance.provider.name }}":mailto:noc@yourcompany.com
SEQUENCE:{{ message_sequence }}
X-MAINTNOTE-PROVIDER:{{ maintenance.provider.slug }}
X-MAINTNOTE-ACCOUNT:{{ tenant.name }}
X-MAINTNOTE-MAINTENANCE-ID;X-MAINTNOTE-PRECEDENCE=PRIMARY:{{ maintenance.name }}
{% for impact in tenant_impacts %}
X-MAINTNOTE-OBJECT-ID:{{ impact.target.cid|default:impact.target }}
{% endfor %}
X-MAINTNOTE-IMPACT:{{ highest_impact }}
X-MAINTNOTE-STATUS:{{ maintenance.status }}
END:VEVENT
END:VCALENDAR
```

### Required BCOP Fields

| Field | Description |
|-------|-------------|
| `X-MAINTNOTE-PROVIDER` | Service provider identifier |
| `X-MAINTNOTE-ACCOUNT` | Customer account identifier |
| `X-MAINTNOTE-MAINTENANCE-ID` | Unique maintenance ID |
| `X-MAINTNOTE-OBJECT-ID` | Affected service ID(s) |
| `X-MAINTNOTE-IMPACT` | NO-IMPACT, REDUCED-REDUNDANCY, DEGRADED, OUTAGE |
| `X-MAINTNOTE-STATUS` | TENTATIVE, CONFIRMED, CANCELLED, IN-PROCESS, COMPLETED |

---

## API Design

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

POST   /api/plugins/notices/prepared-messages/{id}/journal/
```

### Delivery System Integration (Pull Model)

**List ready messages:**
```http
GET /api/plugins/notices/prepared-messages/?status=ready
```

**Update status with optional journal entry:**
```http
PATCH /api/plugins/notices/prepared-messages/{id}/
Content-Type: application/json

{
    "status": "delivered",
    "delivered_at": "2026-01-22T10:31:00Z",
    "message": "Delivered via SMTP to 5 recipients"
}
```

If `message` is provided, a journal entry is created automatically with appropriate kind:
- `sent` → kind: `info`
- `delivered` → kind: `success`
- `failed` → kind: `warning`
- `ready` (retry) → kind: `info`

**Mark as viewed:**
```http
PATCH /api/plugins/notices/prepared-messages/{id}/
Content-Type: application/json

{"viewed_at": "2026-01-22T14:00:00Z"}
```

### Webhook Integration

Use NetBox's built-in Event Rules to fire webhooks when PreparedMessage transitions to `ready`. No custom webhook code in this plugin.

---

## UI Workflow

### Template Management

- Standard NetBox CRUD for MessageTemplates
- Scope assignment UI similar to Config Contexts
- Preview rendered template with sample data
- Jinja syntax validation on save
- YAML input for headers_template

### Message Generation (from Event)

1. From Maintenance/Outage detail page: **"Generate Notifications"** button
2. Select template (filtered by matching scopes + event type)
3. Preview shows:
   - Number of messages to be created (based on granularity)
   - Recipients per message
4. Confirm → Creates PreparedMessage(s) in `draft` status

### PreparedMessage Management

- List view with status filter tabs: Draft | Ready | Sent | Delivered | Failed
- Bulk actions: "Mark Ready", "Delete Drafts"
- Detail view shows:
  - Rendered content (subject, body preview, headers)
  - Recipients list
  - Linked event (if any)
  - Journal entries (delivery attempts, errors, notes)
  - Approval info (who/when)
- Edit contacts while in `draft`
- **"Approve"** button → transitions to `ready`, sets `approved_by`/`approved_at`

### Standalone Message Creation

1. "New Message" action (no event link)
2. Select template (filtered to `event_type=none`)
3. Manually select contacts
4. Same draft → ready → delivery flow

---

## Configuration

No new plugin settings required. All configuration is done through:

- MessageTemplate objects (user-managed)
- TemplateScope assignments
- NetBox's ContactRole and Contact objects
- NetBox's Event Rules (for optional webhook delivery triggers)

---

## Future Considerations

Not in scope for initial implementation, but possible enhancements:

- **Scheduled sending:** Add `scheduled_for` field, delivery system polls for ready + scheduled_for <= now
- **Recipient groups:** Predefined contact lists beyond tenant-based discovery
- **Template versioning:** Track template changes, link PreparedMessage to specific version
- **Delivery receipts per recipient:** Track delivery/view status per email address, not just per message
- **SMS/voice channels:** Additional contact fields and template types

---

## Summary

This design adds a flexible, backend-agnostic notification composition system to netbox-notices:

- **Templates** with Jinja, Markdown support, and Config Context-like scoping
- **Automatic recipient discovery** from NetBox contacts via tenant relationships
- **BCOP-compliant iCal** generation for maintenance events
- **Full message lifecycle** tracking with state machine validation
- **Audit trail** via approval tracking and journal entries
- **Pull-based API** for delivery system integration
- **NetBox Event Rules** for optional webhook triggers
