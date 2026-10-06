# Outgoing Notifications

Event tracking is inbound: a provider tells you about a maintenance window. Outgoing notifications are the other direction, where you tell your own customers about it.

The plugin composes those notifications and tracks their lifecycle. It does not deliver them. Composition, recipient discovery and state tracking live here; SMTP, Slack, Teams and webhooks live in an external delivery system that talks to the REST API.

This page is the overview. The details are on their own pages:

- [Templates](messaging/templates.md) covers the `NotificationTemplate` model, the Jinja context, and how templates become notification kinds, override each other and merge.
- [Recipient Discovery](messaging/recipient-discovery.md) covers how contacts are found from impacted objects.
- [Approval Workflow](messaging/workflow.md) covers the state machine and the delivery loop.

## Flow

```
   Maintenance or Outage
            |
            v
   +--------------------+     scopes decide which template applies
   | NotificationTemplate | <-- TemplateScope (weighted, config-context style)
   +--------------------+
            |
            | NotificationGenerator: render subject, body, headers, CSS, iCal
            | discover recipients from impacts -> tenants -> contacts
            v
   +----------------------+
   | PreparedNotification |  status: draft
   +----------------------+
            |
            | PATCH status=ready  (snapshots recipients, stamps approval)
            v
        REST API  <----  external delivery system polls for status=ready
            |
            | PATCH status=sent, then delivered or failed
            v
   +----------------------+
   |  SentNotification    |  read-only proxy over sent and delivered
   +----------------------+
```

## Models

| Model | Purpose |
|---|---|
| `NotificationTemplate` | Jinja sources plus matching and recipient configuration |
| `TemplateScope` | Attaches a template to a NetBox object with a weight |
| `PreparedNotification` | A rendered notification with a status and a recipient snapshot |
| `SentNotification` | Proxy over `PreparedNotification`, filtered to `sent` and `delivered` |

Field-by-field reference is in [Templates](messaging/templates.md) and [Approval Workflow](messaging/workflow.md).

The rendered content is a snapshot. Editing a template afterwards does not change notifications already prepared from it, and editing a contact does not change the `recipients` list of a notification already approved. That is what makes the sent log an audit record rather than a live view.

## Generating notifications

`NotificationGenerator` turns a maintenance or outage into draft `PreparedNotification` records. It first builds a plan (what it would create, update, keep, delete or skip) and then applies it in one database transaction, so a failed run leaves nothing half written. The same plan drives the UI preview, the API dry run and automatic generation.

Every non-base template that matches the event type is a notification *kind*. For each kind the generator splits the event's impacts into recipient groups according to the kind's granularity, finds the contacts for each group, and renders one draft per group. Which template renders a group, and how overrides apply, is described in [Templates](messaging/templates.md).

### From the UI

Open a maintenance or outage and choose **Generate Notifications** in the Operations menu. The page previews the plan, one row per recipient group with its action, and lets you untick kinds you do not want to generate. Submitting applies the plan and returns to the event with a summary such as `2 created, 1 updated`. Previewing changes nothing.

Drafts then appear on the event's timeline and in the prepared notifications list, where they can be edited, reset to their template, and approved. See [Approval Workflow](messaging/workflow.md).

### From the API

```
POST /api/plugins/notices/maintenance/{id}/generate-notifications/
POST /api/plugins/notices/outage/{id}/generate-notifications/
```

The body is optional. `templates` is a list of notification kind IDs; an empty or absent list means every applicable kind. Duplicates are ignored, and an ID that is not a kind for this event is rejected with `400`. `dry_run` (default `false`) returns the plan without writing anything.

```bash
curl -X POST \
  -H "Authorization: Token $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true}' \
  https://netbox.example.com/api/plugins/notices/maintenance/42/generate-notifications/
```

```json
{
  "summary": "2 to create, 1 failing",
  "counts": {"create": 2, "error": 1},
  "items": [
    {
      "action": "create",
      "template": 3,
      "root_template": 3,
      "tenant": 7,
      "impact": null,
      "contacts": [12, 15],
      "subject": "[CONFIRMED] Acme Maintenance: MAINT-1001",
      "error": null,
      "notification": null
    }
  ]
}
```

A dry run words the summary as a plan ("2 to create"). An applied run uses the past tense ("2 created") and fills `notification` with the ID of the draft written. `template` is the template that actually rendered the group (an override, when one applies) and `root_template` is the kind it belongs to.

The caller needs add, change and delete on prepared notifications plus view on the event. Missing rights return `403`. See [Permissions](permissions.md).

### Automatic generation

Generation can also run by itself when an event changes. It is off by default; see `auto_generate_notifications` in [Configuration](configuration.md).

### Regeneration

Running generation again is safe. Each recipient group ends up with one of these actions:

| Action | Meaning |
|---|---|
| `create` | No draft exists for the group; a new one is written. |
| `update` | An untouched draft exists; it is re-rendered in place. |
| `keep` | A hand-edited draft exists; it is left alone. |
| `delete` | The group no longer exists or has no recipients; its untouched draft is removed. |
| `skip` | The group has no contacts to notify, so nothing is created. |
| `error` | A template failed to render; the group is reported and nothing is written for it. |

Rules that follow from this:

- A draft is *untouched* until its content diverges from what was rendered. Edited drafts (the `modified` flag) are kept, never overwritten or deleted.
- Anything past `draft` (`ready`, `sent`, `delivered`, `failed`) is never changed. The iCal `SEQUENCE` of a re-render counts those earlier notifications, so a calendar client sees an update.
- Notifications created by hand are never touched at all: not updated, kept, deleted, and they do not stop a generated draft being created for the same group.
- Generating with a subset of kinds only affects those kinds; drafts of unselected kinds are left alone.
- A template error, syntax or runtime, is reported as `error` on the affected kind only. Other kinds still generate.

## iCal attachments

A maintenance notification can carry an iCal attachment following the BCOP Maintnote standard, so a recipient's calendar client shows the window.

`ICalGenerationService` generates one only when all three of these hold:

1. The event is a `Maintenance`, not an `Outage`.
2. The template has `include_ical` set.
3. The template has a non-empty `ical_template`.

`generate_ical()` returns `None` rather than raising when the conditions are not met.

### BCOP properties

| Property | Source |
|---|---|
| `X-MAINTNOTE-PROVIDER` | Provider slug |
| `X-MAINTNOTE-ACCOUNT` | Tenant name |
| `X-MAINTNOTE-MAINTENANCE-ID` | Maintenance `name`, with `X-MAINTNOTE-PRECEDENCE=PRIMARY` |
| `X-MAINTNOTE-OBJECT-ID` | One line per impact, using the circuit ID where the target has one |
| `X-MAINTNOTE-IMPACT` | Worst impact level across the impacts in scope |
| `X-MAINTNOTE-STATUS` | Event status |

### Context

The iCal template sees the same variables as the body template, plus `message_sequence`, which maps to the iCal `SEQUENCE` property and lets a calendar client recognise an update to an event it already holds. `message_sequence` is passed by the caller and defaults to 1; it is not available in body templates.

`highest_impact` is guaranteed here, defaulting to `NO-IMPACT` when there are no impacts, whereas in a body template it is only present when impacts exist.

### Reference template

`notices.services.ical_generation.DEFAULT_BCOP_ICAL_TEMPLATE` holds a working template you can copy into a new one as a starting point:

```python
from notices.services.ical_generation import DEFAULT_BCOP_ICAL_TEMPLATE

print(DEFAULT_BCOP_ICAL_TEMPLATE)
```

## Integrating a delivery system

The plugin is the queue and the delivery system is the worker. Poll for approved notifications, send them, and report back:

1. `GET /api/plugins/notices/prepared-notifications/?status=ready`
2. Send each one, addressed to the entries in `recipients`.
3. `PATCH` it to `sent`, including a `timestamp` if you are reporting after the fact.
4. `PATCH` it to `delivered` on confirmation, or to `failed` with a `message`.

Two things are easy to get wrong.

Address from `recipients`, not `contacts`. The former is the frozen snapshot taken at approval; the latter is the live set of contact records.

Follow the transition graph. `ready` goes to `sent`, and only `sent` goes to `delivered`. Attempting to jump from `ready` straight to `delivered` is rejected. See [Approval Workflow](messaging/workflow.md).

### Minimal SMTP loop

```python
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage

import requests

NETBOX_URL = "https://netbox.example.com"
API_TOKEN = "your-api-token"
SMTP_HOST = "smtp.example.com"

headers = {"Authorization": f"Token {API_TOKEN}"}
endpoint = f"{NETBOX_URL}/api/plugins/notices/prepared-notifications/"

response = requests.get(endpoint, params={"status": "ready"}, headers=headers)

for notification in response.json()["results"]:
    try:
        email = EmailMessage()
        email["Subject"] = notification["subject"]
        email["From"] = "noc@example.com"
        email["To"] = ", ".join(r["email"] for r in notification["recipients"])
        email.set_content(notification["body_text"])

        if notification["body_html"]:
            email.add_alternative(notification["body_html"], subtype="html")

        if notification["ical_content"]:
            email.add_attachment(
                notification["ical_content"].encode(),
                maintype="text",
                subtype="calendar",
                filename="maintenance.ics",
            )

        sent_at = datetime.now(timezone.utc).isoformat()
        with smtplib.SMTP(SMTP_HOST) as smtp:
            smtp.send_message(email)

        requests.patch(
            f"{endpoint}{notification['id']}/",
            json={"status": "sent", "timestamp": sent_at, "message": "Sent via SMTP"},
            headers=headers,
        )
        requests.patch(
            f"{endpoint}{notification['id']}/",
            json={
                "status": "delivered",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": f"Delivered to {len(notification['recipients'])} recipients",
            },
            headers=headers,
        )
    except Exception as exc:
        requests.patch(
            f"{endpoint}{notification['id']}/",
            json={"status": "failed", "message": str(exc)},
            headers=headers,
        )
```

Marking `delivered` immediately after a successful SMTP handoff is a simplification. SMTP acceptance is not delivery; a real integration leaves the notification at `sent` and moves it to `delivered` when the transport reports back.

### Push instead of polling

For push-based delivery, use NetBox event rules under **Operations > Event Rules**. Create a rule on the `PreparedNotification` object type conditioned on `status = ready` and point it at your delivery system's webhook. The status updates still go back through the REST API.

### AWS SES

For a deployable integration with full delivery lifecycle tracking, including bounce and complaint handling and open and click events, see the [AWS SES Integration](integrations_aws_ses.md) guide. It covers scheduled polling, MIME construction with HTML and iCal parts, an SES configuration set with SNS event destinations, automatic status updates driven by SES events, and journal entries for informational events.

## See also

- [Templates](messaging/templates.md)
- [Recipient Discovery](messaging/recipient-discovery.md)
- [Approval Workflow](messaging/workflow.md)
- [REST API](api/rest-api.md)
- [Permissions](permissions.md)
