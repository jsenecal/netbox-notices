# Approval Workflow

A `PreparedNotification` is a rendered notification with a status. The status moves through a state machine that validates every transition and applies side effects, so the record shows not just what was sent but when it was approved, by whom, and when it was accepted for delivery.

The implementation is `PreparedNotificationStateMachine` in `notices/validators.py`.

## States

| Status | Meaning |
|---|---|
| `draft` | Rendered but not approved. Content and recipients are still editable. |
| `ready` | Approved and queued. Recipients are frozen. |
| `sent` | Handed to the delivery system. |
| `delivered` | Confirmed as delivered. Terminal. |
| `failed` | Delivery failed. Can be retried. |

## Transitions

```
draft --> ready --> sent --> delivered
            ^         |
            |         v
            +------ failed
```

| From | Allowed targets |
|---|---|
| `draft` | `ready` |
| `ready` | `sent` |
| `sent` | `delivered`, `failed` |
| `delivered` | none |
| `failed` | `ready` |

Anything else is rejected with the current status and the valid targets named in the error.

Three properties of this graph matter in practice.

There is no route back from `ready` to `draft`. Approval is one-way. A notification approved by mistake cannot be edited back into a draft; it has to be left unsent or deleted.

`delivered` is terminal, and `failed` returns to `ready` rather than to `sent`. A retry goes through approval again, which re-snapshots recipients and re-stamps the approval fields, so a retry after a contact was corrected picks up the new address.

There is no `cancelled` state. A notification that should not go out is deleted, not withdrawn.

## Side effects

Each transition does more than write a status.

**To `ready`.** The recipient snapshot is recomputed from the `contacts` M2M, keeping only contacts with an email address. If the resulting snapshot is empty, the transition is refused:

```
Cannot approve notification with no recipients. Add contacts first.
```

Then `approved_by` is set to the requesting user and `approved_at` to the current time. Because this runs on every entry to `ready`, a retry from `failed` re-snapshots and re-stamps rather than preserving the original approval.

**To `sent`.** `sent_at` is set, but only if it is not already set. A second transition into `sent` cannot happen anyway, given the transition table.

**To `delivered`.** `delivered_at` is set on the same terms.

**To `failed`.** No side effects. Nothing records why it failed except the journal entry, if one is supplied.

The whole transition runs in a database transaction, so a refused approval leaves no partial snapshot behind.

## Timestamps

By default a transition stamps the current time. A delivery system that batches, or polls on a delay, can supply the real time instead:

```json
{"status": "sent", "timestamp": "2026-08-31T14:32:00Z"}
```

Two rules are enforced:

- A timestamp cannot be in the future.
- Ordering has to hold. `sent_at` cannot precede `approved_at`, and `delivered_at` cannot precede `sent_at`.

A violation is returned as a validation error against the `timestamp` field.

The ordering checks compare against the stored value, so they only apply when the earlier stamp exists. `approved_at` is always set by the transition into `ready`, so in normal use both checks are live.

One asymmetry is worth knowing: `approved_at` is always the real current time and ignores a supplied `timestamp`. Only `sent_at` and `delivered_at` honour it.

## Journal entries

Any transition can carry a `message`, which creates a NetBox journal entry against the notification recording the status change and the message text. The entry's kind is derived from the target status:

| Target status | Journal kind |
|---|---|
| `ready` | info |
| `sent` | info |
| `delivered` | success |
| `failed` | warning |

No message means no journal entry. Nothing else is written, so a `failed` transition with no message leaves no record of the reason. A delivery system should always send one on failure.

## Driving it over the API

Status is changed through the REST API only. The field is deliberately absent from the web UI, and the bulk edit view for prepared notifications is unmounted, because a direct write would bypass the recipient snapshot and the approval stamps described above. See [Permissions](../permissions.md).

### Create as draft

A create is always `draft`. Posting any other status is refused:

```
A notification is always created as 'draft'. Create it first, then PATCH it to 'ready'.
```

The reason is that a create has no prior state, so the state machine never runs. A notification stored straight into `ready` would carry no recipient snapshot and no approval stamps, and since `ready` has no route back to `draft`, nothing downstream could repair it. Before this was enforced, such a record would be retried by the outbound poller indefinitely.

```http
POST /api/plugins/notices/prepared-notifications/
```

```json
{
  "template_id": 3,
  "event_content_type": 91,
  "event_id": 42,
  "subject": "Scheduled maintenance on your circuit",
  "body_text": "...",
  "contact_ids": [12, 15]
}
```

### Approve

```http
PATCH /api/plugins/notices/prepared-notifications/57/
```

```json
{"status": "ready", "message": "Reviewed by NOC shift lead"}
```

### Mark sent and delivered

```json
{"status": "sent", "timestamp": "2026-08-31T14:32:00Z"}
```

```json
{"status": "delivered", "timestamp": "2026-08-31T14:32:07Z"}
```

### Record a failure

```json
{"status": "failed", "message": "SMTP 550: mailbox unavailable"}
```

## A delivery loop

The plugin is the queue; the delivery system is the worker. A polling loop looks like this:

1. `GET /api/plugins/notices/prepared-notifications/?status=ready` for work.
2. Send each notification using its `subject`, `body_text`, `body_html`, `headers`, `css` and `ical_content`, addressed to the entries in `recipients`.
3. `PATCH` each to `sent` with the send time.
4. `PATCH` to `delivered` on confirmation, or to `failed` with a message.

Read `recipients`, not `contacts`. The snapshot is the frozen list of addresses taken at approval; the M2M is the live set of contact records and may have moved since. See [Recipient Discovery](recipient-discovery.md).

Once a notification reaches `sent` or `delivered` it also appears in the read-only sent notifications list and its own API endpoint:

```http
GET /api/plugins/notices/sent-notifications/
```

That endpoint is a proxy over the same table, filtered to `sent` and `delivered` and restricted to `GET`, `HEAD` and `OPTIONS`.

## Fields the state machine does not set

`viewed_at` exists on the model and appears on the detail page, but no code path writes it. It is read-only in both serializers and has no transition attached, so it stays empty. Treat it as reserved.

## See also

- [Templates](templates.md)
- [Recipient Discovery](recipient-discovery.md)
- [REST API](../api/rest-api.md)
- [Permissions](../permissions.md)
