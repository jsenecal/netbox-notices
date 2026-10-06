# Outgoing Notification Generation -- Design

Date: 2026-10-06
Status: approved (brainstorming session)
Branch: `feat/notification-generation`

## Problem

The outgoing notification subsystem has every building block -- template matching
(`TemplateMatchingService`, `merge_templates`), recipient discovery
(`RecipientDiscoveryService`), Jinja rendering (`TemplateRenderer`), iCal generation
(`ICalGenerationService`) and the `PreparedNotification` state machine -- but nothing
connects them. No view, API action, signal or command calls the services. Today a
`PreparedNotification` can only be created by hand (UI form, which does not render the
template and cannot link an event) or through the REST API with caller-rendered content.

## Goal

For any Maintenance or Outage, whether it came from an inbound provider notice or was
created by hand, an operator (or an external parser, or an opt-in automatic trigger) can
produce draft `PreparedNotification`s whose content is rendered by the plugin, review
them, edit or reset them, and approve them to `ready` -- without hand-writing content and
without using the API.

Out of scope: standalone (no-event) messages, a template preview page with sample data,
delivery (the plugin still never sends mail), tracking of recipient-only edits as
"modified".

## Decisions

| Topic | Decision |
|---|---|
| Trigger | On demand (UI button, REST action) plus opt-in automatic generation |
| Auto rules | Only on meaningful changes AND only while the event status is in a configured list |
| Regeneration | Untouched drafts re-rendered in place; modified drafts and anything past draft kept; a new draft is created alongside kept ones |
| Template model | Every non-base template is an independent "kind"; a matching child of a non-base template overrides its parent for that group; merging follows the `extends` chain only |
| Modified detection | Postgres generated column `content_hash` vs. snapshot `rendered_hash` |
| Reset | Per-draft "Reset to template" button and REST action |
| Timeline | Outgoing notifications appear on the event timeline as a new `outgoing` category |

## 1. Data model

### PreparedNotification (one migration)

- `tenant` -- FK `tenancy.Tenant`, null, `on_delete=SET_NULL`, `related_name="+"`.
- `impact` -- FK `notices.Impact`, null, `on_delete=SET_NULL`, `related_name="+"`.
  Together these identify the recipient group:

  | Granularity | tenant | impact |
  |---|---|---|
  | `per_event` | null | null |
  | `per_tenant` | set | null |
  | `per_impact` | impact's tenant (may be null) | set |

- `content_hash` -- `GeneratedField(db_persist=True)`, `CharField(max_length=32)`.
  Expression (Postgres, immutable):
  `md5(subject || E'\x1f' || body_text || E'\x1f' || body_html || E'\x1f' || headers::text || E'\x1f' || css || E'\x1f' || ical_content)`
  with each operand `COALESCE`d to `''`. `md5()` is used because Django's `SHA256()`
  compiles to pgcrypto `DIGEST()` and native `sha256()` needs a non-immutable
  text-to-bytea conversion; verified that the md5 expression is accepted as a stored
  generated column on PostgreSQL 17. This is change detection, not security.
  `headers::text` from jsonb is canonical, so key reordering is not a modification.
  Django 6.1 returns generated columns via `RETURNING` on insert and update.
- `rendered_hash` -- `CharField(max_length=32, blank=True, default="")`. Copied from
  `content_hash` inside Postgres after generation/reset with
  `PreparedNotification.objects.filter(pk=...).update(rendered_hash=F("content_hash"))`
  (bypasses `save()`: no extra changelog row). Blank for hand-created notifications.
- Queryset method `with_modified()` / filter: modified means
  `rendered_hash != '' AND rendered_hash != content_hash`. Exposed as a `modified`
  boolean on the filterset, table column, API (read-only), detail badge, event card.
- `to_objectchange(action)` -- call `super()`, set `related_object = self.event` (when
  set) so changes appear on the event timeline.

Known limitation: `contacts` (M2M) is not part of the hash; editing only recipients does
not mark a draft modified. Reset restores discovered contacts.

### NotificationTemplate.clean()

- Reject `extends` cycles (including self-reference).
- A template whose parent is a non-base template (an override) must have the same
  `granularity` as its parent.

## 2. Template selection and merging

Replaces the current "merge every matching template by score" behaviour.

- **Kind**: a template with `is_base_template=False` whose `event_type` fits the event
  (`maintenance`/`outage` or `both`).
- **Applies to a group**: the template has no scopes, or at least one scope matches the
  full context -- event type, event status, provider, and the group's tenant. A
  tenant-scoped scope with a specific `object_id` therefore only matches that tenant's
  group; `per_event` groups have no tenant.
- **Override**: if kind `C.extends == P`, `P` is a non-base kind, and both apply to a
  group, `C` replaces `P` for that group. If several children apply, the highest score
  (template weight + matching scope weights) wins. Overrides can be nested.
- **Base templates** (`is_base_template=True`) never generate on their own; children of
  base templates are ordinary kinds that borrow the layout.
- **Merge along the chain**: `merge_templates` takes the chain (most specific first) and
  each field falls back to the next template when empty (subject, body, body_format,
  css, ical, headers key-by-key, contact roles/priorities union, include_ical OR).
- **Grouping** is driven by the root kind's granularity (overrides share it, enforced by
  `clean()`).

## 3. Rendering (TemplateRenderer fixes)

- The `extends` chain bodies are registered in the `StringLoader` so `{% extends "base" %}`
  resolves (the parent body is registered as `base`; deeper chains register each
  ancestor under its slug and as `base` for the immediate child). Inheritance renders
  WITH the context (today `render_with_inheritance` drops it).
- `body_format`:
  - `markdown`: rendered source -> `body_text`; `markdown` filter output -> `body_html`.
  - `html`: rendered output -> `body_html`; tag-stripped copy -> `body_text`.
  - `text`: rendered output -> `body_text`; `body_html` empty.
- Subject, each header value, and CSS are rendered as Jinja with the same context.
- iCal through `ICalGenerationService` with `message_sequence = 1 + count of earlier
  non-draft notifications for the same event, root kind and group`.

## 4. NotificationGenerator service

`notices/services/notification_generation.py`, `NotificationGenerator(event, templates=None)`.

- `plan()` -- side-effect free. Returns a list of `PlannedNotification` (dataclass):
  `root_template`, `template` (winning override or root), `tenant`, `impact`,
  `contacts`, rendered fields, `action`, `existing` (PreparedNotification or None),
  `error` (str or None).
  1. Kinds: all applicable non-base kinds, or the explicit `templates` selection.
  2. For each kind, groups from `RecipientDiscoveryService` with the kind's granularity.
  3. Per group: pick the override, render, compare against existing notifications for
     (event, root kind family, tenant, impact).
  4. Action:
     - `create` -- no existing untouched draft for the group.
     - `update` -- existing draft, not modified: re-render in place.
     - `keep` -- existing draft that is modified, or existing notifications past draft
       (a new draft is still created alongside a past-draft one; a modified draft
       suppresses creation).
     - `delete` -- existing untouched draft whose group no longer exists.
     - `skip` -- group has no contacts.
     - errored items carry `error` and are not applied.
- `apply(plan)` -- one transaction; performs create/update/delete; leaves keep/skip/error;
  sets `rendered_hash` via the queryset update; returns saved notifications and a
  summary dict of counts per action.
- `render_one(notification)` -- re-render a single draft from its own template, event and
  group (current state, not the original output); used by Reset.

A render failure (syntax error, undefined variable) only marks its own items as errored.

## 5. Entry points

### UI

- Maintenance and Outage detail pages: "Generate Notifications" in the actions
  dropdown -> `/maintenance/<pk>/generate-notifications/` (and outage):
  - GET: checkboxes for applicable kinds (all checked), Preview button re-renders the
    page with the selection, preview table (template/override, group, recipients,
    action, subject, error).
  - POST: applies, redirects to the event with a count summary message.
  - Requires add, change and delete on `notices.preparednotification`.
- Event detail "Outgoing Notifications" card: subject, group, status badge, modified
  marker, link to the filtered list.
- PreparedNotification detail: Event link, group, Modified badge, **Approve** (draft ->
  ready via the state machine with `request.user`; dedicated POST view, status stays out
  of the form) and **Reset to template** (draft + linked event + modified).
- Filterset additions: `event_content_type`, `event_id`, `tenant_id`, `modified`.
  Table columns: event, tenant, modified.

### REST API

- `POST /api/plugins/notices/maintenance/{id}/generate-notifications/` and the same
  under `outage/`. Body `{"templates": [ids], "dry_run": bool}`. Dry run returns the
  plan only; otherwise applies and returns plan + saved ids.
- `POST /api/plugins/notices/prepared-notifications/{id}/reset/`.
- Serializer: `tenant`, `impact`, read-only `modified`; hashes not exposed.

### Auto mode

- Setting `auto_generate_notifications = {"maintenance": [], "outage": []}` (statuses;
  empty = off).
- `post_save`/`post_delete` on Maintenance, Outage, Impact. Meaningful = event created,
  or status/start/end/estimated_time_to_repair changed vs. `_prechange_snapshot`, or an
  impact created/changed/deleted.
- Runs only if meaningful AND current status is in the list. Queued with
  `transaction.on_commit`, de-duplicated per event per transaction. All kinds.
- Failures are logged and journaled on the event (kind warning); never break the save.
- Outside a request (scripts), NetBox records no ObjectChange, so those runs do not
  appear on the timeline.

## 6. Timeline

- `categorize_change`: `preparednotification` -> `outgoing` (icon `email-arrow-right`,
  colour `purple`); existing `eventnotification` stays `notification`.
- Titles: create "Notification drafted: <subject> (<tenant or all>)"; status change
  "Notification approved|sent|delivered|failed: <subject>"; other update "Notification
  edited: <subject>"; delete "Notification discarded: <subject>".

## 7. Docs

README, CHANGELOG `[Unreleased]` (Added; Changed -- template merge now follows
`extends`), `docs/outgoing-notifications.md`, `docs/messaging/templates.md`,
`docs/messaging/workflow.md`, `docs/configuration.md`, `docs/api/rest-api.md`.

## 8. Testing

Plugin-owned logic only, TDD per unit. Matching (kind/override/base, tenant scope,
winning override, chain merge; rewrite or delete merge-everything tests), `clean()`,
renderer (inheritance with context, body formats), generator actions incl. errors and
iCal sequence, apply/render_one hashes, the modified predicate on real Postgres, auto
mode rules and de-duplication, timeline category/titles, view/API logic (permission
gate, dry run writes nothing, Approve through state machine). Diff coverage at or above
the project average.

Tests run in the worktree with `flock /tmp/netbox-plugins-testdb.lock
/opt/netbox/venv/bin/python -m pytest ...` -- `python -m` is required so the worktree's
`notices` package is imported instead of the editable install of the main checkout.
