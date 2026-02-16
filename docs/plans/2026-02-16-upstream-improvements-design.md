# Upstream v0.8.0 Improvements Design

**Date:** 2026-02-16
**Source:** [netbox-circuitmaintenance v0.8.0](https://github.com/jasonyates/netbox-circuitmaintenance/releases/tag/v)

Six improvements adapted from the upstream release, ordered by priority.

## 1. HTML Sanitization (Security Fix)

**Problem:** `eventnotification.html` uses `{{ object.email_body|safe }}` and `preparednotification.html` uses `{{ object.body_html|safe }}` — raw unsanitized HTML from email bodies and user-generated content, creating XSS risk.

**Solution:** Create a custom template filter `sanitize_html` that wraps NetBox's built-in `clean_html()` from `netbox.utilities.html` (uses nh3, already a NetBox dependency). Replace `|safe` with `|sanitize_html` in both templates.

**Files:**
- New: `notices/templatetags/notices_filters.py`
- Edit: `notices/templates/notices/eventnotification.html`
- Edit: `notices/templates/notices/preparednotification.html`

## 2. Database Indexes on status/start/end

**Problem:** Frequently queried fields (status, start, end) lack database indexes.

**Solution:** Add `db_index=True` to `status`, `start`, and `end` fields in BaseEvent. These are inherited by Maintenance and Outage. Generate a single migration covering all changes.

**Files:**
- Edit: `notices/models/events.py`
- New: migration file (auto-generated)

## 3. Date Range Validation (end >= start)

**Problem:** Events can be created with `end` before `start` — no model-level validation.

**Solution:** Add `clean()` method to BaseEvent that validates `self.end >= self.start` when both fields are set. Outage already overrides `clean()` — update it to call `super().clean()` first.

**Files:**
- Edit: `notices/models/events.py`

## 4. SearchIndex for Global Search

**Problem:** Plugin models don't appear in NetBox's global search.

**Solution:** Create `notices/search.py` with SearchIndex classes for: Maintenance, Outage, EventNotification, NotificationTemplate, PreparedNotification. Use `@register_search` decorator. Add `search_indexes` attribute to PluginConfig.

**Search field weights:**
- name/subject: 100 (primary)
- summary/description: 500 (secondary)
- comments: 5000 (tertiary)

**Files:**
- New: `notices/search.py`
- Edit: `notices/__init__.py`

## 5. Summary Dashboard

**Problem:** No overview page for quick situational awareness.

**Solution:** New `DashboardView` (permission-gated, read-only) as the first navigation item:
- **Stat cards:** In Progress, Confirmed This Week, Upcoming 7 days, Upcoming 30 days, Unacknowledged — each linking to filtered list views
- **14-day timeline:** Active/upcoming events with status badges, provider name, impact count
- **Upcoming by provider:** Grouped table of confirmed/tentative events

Covers both Maintenance and Outage models since our plugin supports both event types.

**Files:**
- New: `notices/templates/notices/dashboard.html`
- Edit: `notices/views.py`
- Edit: `notices/navigation.py`
- Edit: `notices/urls.py`

## 6. GraphQL API

**Problem:** No GraphQL support despite NetBox's native plugin GraphQL integration.

**Solution:** Create `notices/graphql/` package with Strawberry types, filters, and schema for all models: Maintenance, Outage, Impact, EventNotification, NotificationTemplate, PreparedNotification, SentNotification.

Models using GenericForeignKey (Impact, EventNotification, PreparedNotification) will exclude GFK fields and use custom resolvers to expose the related objects.

**Files:**
- New: `notices/graphql/__init__.py`
- New: `notices/graphql/types.py`
- New: `notices/graphql/filters.py`
- New: `notices/graphql/schema.py`
- Edit: `notices/__init__.py`

## Bonus: brief_fields on API Serializers

**Problem:** Serializers don't define `brief_fields`, which modern NetBox uses for compact nested representations.

**Solution:** Add `brief_fields` tuple to all serializer `Meta` classes. Typically: `('id', 'url', 'display', <key identifying fields>)`.

**Files:**
- Edit: `notices/api/serializers/events.py`
- Edit: `notices/api/serializers/messaging.py`
