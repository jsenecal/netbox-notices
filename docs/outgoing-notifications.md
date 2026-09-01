# Outgoing Notifications

Event tracking is inbound: a provider tells you about a maintenance window. Outgoing notifications are the other direction, where you tell your own customers about it.

The plugin composes those notifications and tracks their lifecycle. It does not deliver them. Composition, recipient discovery and state tracking live here; SMTP, Slack, Teams and webhooks live in an external delivery system that talks to the REST API.

This page is the overview. The details are on their own pages:

- [Templates](messaging/templates.md) covers the `NotificationTemplate` model, the Jinja context, and how a template is matched and merged.
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
            | render subject, body, headers, CSS, iCal
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
