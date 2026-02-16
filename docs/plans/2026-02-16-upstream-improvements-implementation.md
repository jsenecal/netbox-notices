# Upstream v0.8.0 Improvements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement six improvements adapted from the upstream netbox-circuitmaintenance v0.8.0 release: HTML sanitization, database indexes, date validation, global search, summary dashboard, and GraphQL API; plus brief_fields on serializers.

**Architecture:** Each improvement is an independent task that can be implemented and committed separately. Tasks are ordered by priority (security first, then performance, data integrity, features). All changes follow existing NetBox plugin patterns and conventions.

**Tech Stack:** Django 4.x, NetBox 4.4+, Strawberry GraphQL, nh3 (via NetBox's `clean_html()`), pytest

---

### Task 1: HTML Sanitization — Templatetag

**Files:**
- Create: `notices/templatetags/__init__.py`
- Create: `notices/templatetags/notices_filters.py`
- Test: `tests/test_sanitize_filter.py`

**Step 1: Write the failing test**

Create `tests/test_sanitize_filter.py`:

```python
"""Tests for the sanitize_html template filter."""

import pytest
from django.template import Context, Template


@pytest.mark.django_db
class TestSanitizeHtmlFilter:
    def test_strips_script_tags(self):
        t = Template('{% load notices_filters %}{{ html|sanitize_html }}')
        result = t.render(Context({"html": '<p>Hello</p><script>alert("xss")</script>'}))
        assert "<script>" not in result
        assert "<p>Hello</p>" in result

    def test_allows_safe_tags(self):
        t = Template('{% load notices_filters %}{{ html|sanitize_html }}')
        html = "<p>Text with <strong>bold</strong> and <a href='https://example.com'>link</a></p>"
        result = t.render(Context({"html": html}))
        assert "<strong>bold</strong>" in result
        assert "<a " in result

    def test_strips_event_handlers(self):
        t = Template('{% load notices_filters %}{{ html|sanitize_html }}')
        result = t.render(Context({"html": '<img src="x" onerror="alert(1)">'}))
        assert "onerror" not in result

    def test_empty_string(self):
        t = Template('{% load notices_filters %}{{ html|sanitize_html }}')
        result = t.render(Context({"html": ""}))
        assert result.strip() == ""

    def test_none_value(self):
        t = Template('{% load notices_filters %}{{ html|sanitize_html }}')
        result = t.render(Context({"html": None}))
        assert result.strip() == "None"

    def test_plain_text_passes_through(self):
        t = Template('{% load notices_filters %}{{ html|sanitize_html }}')
        result = t.render(Context({"html": "Just plain text"}))
        assert "Just plain text" in result
```

**Step 2: Run test to verify it fails**

Run: `/opt/netbox/venv/bin/pytest tests/test_sanitize_filter.py -v`
Expected: FAIL — `TemplateSyntaxError: 'notices_filters' is not a registered tag library`

**Step 3: Write minimal implementation**

Create `notices/templatetags/__init__.py` (empty file).

Create `notices/templatetags/notices_filters.py`:

```python
from django import template
from django.utils.safestring import mark_safe
from netbox.utilities.html import clean_html

register = template.Library()


@register.filter(name="sanitize_html")
def sanitize_html(value):
    """Sanitize HTML using NetBox's nh3-based clean_html utility."""
    if not value:
        return value
    return mark_safe(clean_html(str(value)))
```

**Step 4: Run test to verify it passes**

Run: `/opt/netbox/venv/bin/pytest tests/test_sanitize_filter.py -v`
Expected: PASS

**Step 5: Update templates to use sanitize_html**

Edit `notices/templates/notices/eventnotification.html` (line 1):
- Replace: `{{object.email_body|safe}}`
- With: `{% load notices_filters %}{{ object.email_body|sanitize_html }}`

Edit `notices/templates/notices/preparednotification.html`:
- Add `{% load notices_filters %}` after `{% load helpers %}` on line 2
- Replace line 139 `{{ object.body_html|safe }}` with `{{ object.body_html|sanitize_html }}`

**Step 6: Run full tests**

Run: `/opt/netbox/venv/bin/pytest tests/ -v`
Expected: PASS

**Step 7: Lint and commit**

```bash
/opt/netbox/venv/bin/ruff check --fix notices/templatetags/ tests/test_sanitize_filter.py
/opt/netbox/venv/bin/ruff format notices/templatetags/ tests/test_sanitize_filter.py
git add notices/templatetags/ tests/test_sanitize_filter.py notices/templates/notices/eventnotification.html notices/templates/notices/preparednotification.html
git commit -m "fix(security): sanitize HTML in email and notification templates

Replace |safe with |sanitize_html filter using NetBox's nh3-based
clean_html utility to prevent XSS from email bodies and rendered
notification HTML."
```

---

### Task 2: Database Indexes on status/start/end

**Files:**
- Modify: `notices/models/events.py:42,101,103,178,186,199`
- New migration (auto-generated)

**Step 1: Add db_index to fields**

Edit `notices/models/events.py`:

In `BaseEvent` class, change line 42:
- From: `start = models.DateTimeField(help_text="Start date and time of the event")`
- To: `start = models.DateTimeField(db_index=True, help_text="Start date and time of the event")`

In `Maintenance` class, change line 101:
- From: `end = models.DateTimeField(help_text="End date and time of the maintenance event")`
- To: `end = models.DateTimeField(db_index=True, help_text="End date and time of the maintenance event")`

In `Maintenance` class, change line 103:
- From: `status = models.CharField(max_length=30, choices=MaintenanceTypeChoices)`
- To: `status = models.CharField(max_length=30, choices=MaintenanceTypeChoices, db_index=True)`

In `Outage` class, change line 178:
- From: `start = models.DateTimeField(default=timezone.now, help_text="Start date and time of the outage")`
- To: `start = models.DateTimeField(default=timezone.now, db_index=True, help_text="Start date and time of the outage")`

In `Outage` class, change line 186:
- From: `end = models.DateTimeField(null=True, blank=True, help_text=...)`
- To: `end = models.DateTimeField(null=True, blank=True, db_index=True, help_text=...)`

In `Outage` class, change line 199:
- From: `status = models.CharField(max_length=30, choices=OutageStatusChoices)`
- To: `status = models.CharField(max_length=30, choices=OutageStatusChoices, db_index=True)`

**Step 2: Generate migration**

Run: `make makemigrations`

**Step 3: Run migration**

Run: `make migrate`

**Step 4: Run tests**

Run: `/opt/netbox/venv/bin/pytest tests/ -v`
Expected: PASS

**Step 5: Lint and commit**

```bash
/opt/netbox/venv/bin/ruff check --fix notices/models/events.py
/opt/netbox/venv/bin/ruff format notices/models/events.py
git add notices/models/events.py notices/migrations/
git commit -m "perf: add database indexes to status, start, and end fields

Add db_index=True to frequently queried fields on Maintenance and
Outage models to improve query performance for list views, filtering,
and calendar rendering."
```

---

### Task 3: Date Range Validation (end >= start)

**Files:**
- Modify: `notices/models/events.py:22-84` (BaseEvent class)
- Modify: `notices/models/events.py:217-221` (Outage.clean)
- Test: `tests/test_date_validation.py`

**Step 1: Write the failing test**

Create `tests/test_date_validation.py`:

```python
"""Tests for date range validation on event models."""

from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone


@pytest.mark.django_db
class TestMaintenanceDateValidation:
    def test_end_before_start_raises_error(self, provider):
        from notices.models import Maintenance

        now = timezone.now()
        m = Maintenance(
            name="MAINT-001",
            summary="Test",
            provider=provider,
            status="CONFIRMED",
            start=now,
            end=now - timedelta(hours=1),
        )
        with pytest.raises(ValidationError, match="end.*must be after"):
            m.full_clean()

    def test_end_equal_to_start_is_valid(self, provider):
        from notices.models import Maintenance

        now = timezone.now()
        m = Maintenance(
            name="MAINT-002",
            summary="Test",
            provider=provider,
            status="CONFIRMED",
            start=now,
            end=now,
        )
        m.full_clean()  # Should not raise

    def test_end_after_start_is_valid(self, provider):
        from notices.models import Maintenance

        now = timezone.now()
        m = Maintenance(
            name="MAINT-003",
            summary="Test",
            provider=provider,
            status="CONFIRMED",
            start=now,
            end=now + timedelta(hours=4),
        )
        m.full_clean()  # Should not raise


@pytest.mark.django_db
class TestOutageDateValidation:
    def test_end_before_start_raises_error(self, provider):
        from notices.models import Outage

        now = timezone.now()
        o = Outage(
            name="OUT-001",
            summary="Test",
            provider=provider,
            status="RESOLVED",
            start=now,
            end=now - timedelta(hours=1),
        )
        with pytest.raises(ValidationError, match="end.*must be after"):
            o.full_clean()

    def test_resolved_without_end_raises_error(self, provider):
        """Existing validation still works."""
        from notices.models import Outage

        now = timezone.now()
        o = Outage(
            name="OUT-002",
            summary="Test",
            provider=provider,
            status="RESOLVED",
            start=now,
            end=None,
        )
        with pytest.raises(ValidationError, match="End time is required"):
            o.full_clean()

    def test_no_end_on_active_outage_is_valid(self, provider):
        """Outages without end are valid when not resolved."""
        from notices.models import Outage

        now = timezone.now()
        o = Outage(
            name="OUT-003",
            summary="Test",
            provider=provider,
            status="INVESTIGATING",
            start=now,
        )
        o.full_clean()  # Should not raise
```

**Step 2: Run test to verify it fails**

Run: `/opt/netbox/venv/bin/pytest tests/test_date_validation.py -v`
Expected: FAIL — `test_end_before_start_raises_error` does NOT raise ValidationError

**Step 3: Implement validation in BaseEvent**

Edit `notices/models/events.py`, add `clean()` method to `BaseEvent` (after `class Meta` block, before `Maintenance` class):

```python
    def clean(self):
        super().clean()
        # Validate end >= start when both are set
        end = getattr(self, "end", None)
        if self.start and end and end < self.start:
            raise ValidationError({"end": "The end time must be after the start time."})
```

The `Outage.clean()` already calls `super().clean()` on line 218, so it inherits this validation automatically.

**Step 4: Run test to verify it passes**

Run: `/opt/netbox/venv/bin/pytest tests/test_date_validation.py -v`
Expected: PASS

**Step 5: Run full tests**

Run: `/opt/netbox/venv/bin/pytest tests/ -v`
Expected: PASS

**Step 6: Lint and commit**

```bash
/opt/netbox/venv/bin/ruff check --fix notices/models/events.py tests/test_date_validation.py
/opt/netbox/venv/bin/ruff format notices/models/events.py tests/test_date_validation.py
git add notices/models/events.py tests/test_date_validation.py
git commit -m "fix: add date range validation ensuring end >= start

Add clean() to BaseEvent that validates end time is not before start
time. Outage inherits this via super().clean() alongside its existing
resolved-requires-end validation."
```

---

### Task 4: SearchIndex for Global Search

**Files:**
- Create: `notices/search.py`
- Modify: `notices/__init__.py:13-29`
- Test: `tests/test_search_index.py`

**Step 1: Write the failing test**

Create `tests/test_search_index.py`:

```python
"""Tests for SearchIndex registration."""

import pytest


@pytest.mark.django_db
class TestSearchIndexes:
    def test_maintenance_index_registered(self):
        from netbox.registry import registry

        search_classes = {idx.__name__ for idx in registry["search"].get("notices", [])}
        assert "MaintenanceIndex" in search_classes

    def test_outage_index_registered(self):
        from netbox.registry import registry

        search_classes = {idx.__name__ for idx in registry["search"].get("notices", [])}
        assert "OutageIndex" in search_classes

    def test_notification_template_index_registered(self):
        from netbox.registry import registry

        search_classes = {idx.__name__ for idx in registry["search"].get("notices", [])}
        assert "NotificationTemplateIndex" in search_classes

    def test_maintenance_index_fields(self):
        from notices.search import MaintenanceIndex

        field_names = [f[0] for f in MaintenanceIndex.fields]
        assert "name" in field_names
        assert "summary" in field_names
        assert "comments" in field_names

    def test_maintenance_index_model(self):
        from notices.models import Maintenance
        from notices.search import MaintenanceIndex

        assert MaintenanceIndex.model is Maintenance
```

**Step 2: Run test to verify it fails**

Run: `/opt/netbox/venv/bin/pytest tests/test_search_index.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'notices.search'`

**Step 3: Create search.py**

Create `notices/search.py`:

```python
from netbox.search import SearchIndex, register_search

from . import models


@register_search
class MaintenanceIndex(SearchIndex):
    model = models.Maintenance
    fields = (
        ("name", 100),
        ("summary", 500),
        ("internal_ticket", 300),
        ("comments", 5000),
    )
    display_attrs = ("provider", "status", "summary")


@register_search
class OutageIndex(SearchIndex):
    model = models.Outage
    fields = (
        ("name", 100),
        ("summary", 500),
        ("internal_ticket", 300),
        ("comments", 5000),
    )
    display_attrs = ("provider", "status", "summary")


@register_search
class EventNotificationIndex(SearchIndex):
    model = models.EventNotification
    fields = (
        ("subject", 100),
        ("email_from", 300),
    )
    display_attrs = ("subject", "email_from", "email_received")


@register_search
class NotificationTemplateIndex(SearchIndex):
    model = models.NotificationTemplate
    fields = (
        ("name", 100),
        ("slug", 110),
        ("description", 500),
    )
    display_attrs = ("description", "event_type", "granularity")


@register_search
class PreparedNotificationIndex(SearchIndex):
    model = models.PreparedNotification
    fields = (
        ("subject", 100),
        ("body_text", 5000),
    )
    display_attrs = ("subject", "status", "template")
```

**Step 4: Update PluginConfig**

Edit `notices/__init__.py`, add `search_indexes` attribute to the `NoticesConfig` class (after `base_url`):

```python
    search_indexes = "search.indexes"
```

Wait — NetBox uses `@register_search` decorator so the indexes auto-register when the module is imported. The `search_indexes` attribute on PluginConfig points to a module attribute that lists the indexes. Looking at the dummy plugin pattern, the attribute should point to the module path and attribute name.

Actually, checking again: the `@register_search` decorator handles all registration. We just need the module to be imported. NetBox's plugin loader automatically imports `search.py` from plugins. No `search_indexes` attribute is needed on PluginConfig — NetBox 4.4+ auto-discovers `search.py` in plugin packages.

**Step 5: Run test to verify it passes**

Run: `/opt/netbox/venv/bin/pytest tests/test_search_index.py -v`
Expected: PASS

**Step 6: Run full tests**

Run: `/opt/netbox/venv/bin/pytest tests/ -v`
Expected: PASS

**Step 7: Lint and commit**

```bash
/opt/netbox/venv/bin/ruff check --fix notices/search.py tests/test_search_index.py
/opt/netbox/venv/bin/ruff format notices/search.py tests/test_search_index.py
git add notices/search.py tests/test_search_index.py
git commit -m "feat: add SearchIndex for global NetBox search

Register Maintenance, Outage, EventNotification, NotificationTemplate,
and PreparedNotification in NetBox's global search. Enables finding
plugin objects from the main search bar."
```

---

### Task 5: Summary Dashboard

**Files:**
- Modify: `notices/views.py:1-26`
- Create: `notices/templates/notices/dashboard.html`
- Modify: `notices/navigation.py:90-98`
- Modify: `notices/urls.py:6-12`
- Test: `tests/test_dashboard.py`

**Step 1: Write the failing test**

Create `tests/test_dashboard.py`:

```python
"""Tests for the Summary Dashboard view."""

from datetime import timedelta

import pytest
from django.test import RequestFactory
from django.utils import timezone

from notices.models import Maintenance, Outage


@pytest.mark.django_db
class TestDashboardView:
    def test_dashboard_url_resolves(self):
        from django.urls import reverse

        url = reverse("plugins:notices:dashboard")
        assert url == "/plugins/notices/"

    def test_dashboard_context_has_stats(self, provider):
        from django.contrib.auth import get_user_model
        from django.test import Client

        User = get_user_model()
        user = User.objects.create_superuser("admin_dash", "admin@test.com", "admin")
        client = Client()
        client.force_login(user)
        response = client.get("/plugins/notices/")
        assert response.status_code == 200
        assert "maintenance_in_progress" in response.context
        assert "outage_active" in response.context
        assert "upcoming_7" in response.context
        assert "upcoming_30" in response.context
        assert "unacknowledged" in response.context

    def test_dashboard_counts_in_progress_maintenance(self, provider):
        from django.contrib.auth import get_user_model
        from django.test import Client

        now = timezone.now()
        Maintenance.objects.create(
            name="M1", summary="Test", provider=provider,
            status="IN-PROCESS", start=now - timedelta(hours=1), end=now + timedelta(hours=1),
        )
        User = get_user_model()
        user = User.objects.create_superuser("admin_dash2", "admin2@test.com", "admin")
        client = Client()
        client.force_login(user)
        response = client.get("/plugins/notices/")
        assert response.context["maintenance_in_progress"] == 1

    def test_dashboard_counts_active_outages(self, provider):
        from django.contrib.auth import get_user_model
        from django.test import Client

        now = timezone.now()
        Outage.objects.create(
            name="O1", summary="Test", provider=provider,
            status="INVESTIGATING", start=now,
        )
        User = get_user_model()
        user = User.objects.create_superuser("admin_dash3", "admin3@test.com", "admin")
        client = Client()
        client.force_login(user)
        response = client.get("/plugins/notices/")
        assert response.context["outage_active"] == 1
```

**Step 2: Run test to verify it fails**

Run: `/opt/netbox/venv/bin/pytest tests/test_dashboard.py -v`
Expected: FAIL — `NoReverseMatch: 'dashboard' is not a valid view function or pattern name`

**Step 3: Implement DashboardView**

Add to `notices/views.py` (after imports, before MaintenanceView class):

```python
class DashboardView(PermissionRequiredMixin, View):
    """Summary dashboard showing event statistics and upcoming timeline."""

    permission_required = "notices.view_maintenance"
    template_name = "notices/dashboard.html"

    def get(self, request):
        now = timezone.now()
        week_end = now + timedelta(days=7)
        month_end = now + timedelta(days=30)

        # Active statuses
        maintenance_active = ["TENTATIVE", "CONFIRMED", "IN-PROCESS", "RE-SCHEDULED"]
        outage_active = ["REPORTED", "INVESTIGATING", "IDENTIFIED", "MONITORING"]

        # Stats
        maintenance_in_progress = models.Maintenance.objects.filter(status="IN-PROCESS").count()
        outage_active_count = models.Outage.objects.filter(status__in=outage_active).count()

        confirmed_this_week = models.Maintenance.objects.filter(
            status="CONFIRMED", start__gte=now, start__lte=week_end
        ).count()

        upcoming_7 = (
            models.Maintenance.objects.filter(
                status__in=maintenance_active, start__gte=now, start__lte=week_end
            ).count()
            + models.Outage.objects.filter(
                status__in=outage_active, start__gte=now - timedelta(days=7)
            ).count()
        )

        upcoming_30 = (
            models.Maintenance.objects.filter(
                status__in=maintenance_active, start__gte=now, start__lte=month_end
            ).count()
            + models.Outage.objects.filter(
                status__in=outage_active
            ).count()
        )

        unacknowledged = (
            models.Maintenance.objects.filter(
                status__in=maintenance_active, acknowledged=False
            ).count()
            + models.Outage.objects.filter(
                status__in=outage_active, acknowledged=False
            ).count()
        )

        # Timeline: next 14 days of events
        timeline_end = now + timedelta(days=14)
        timeline_maintenance = (
            models.Maintenance.objects.filter(
                status__in=maintenance_active,
                start__lte=timeline_end,
                end__gte=now,
            )
            .select_related("provider")
            .annotate(impact_count=Count("impacts"))
            .order_by("start")[:20]
        )
        timeline_outages = (
            models.Outage.objects.filter(status__in=outage_active)
            .select_related("provider")
            .annotate(impact_count=Count("impacts"))
            .order_by("start")[:20]
        )

        # Upcoming by provider
        upcoming_by_provider = (
            models.Maintenance.objects.filter(
                status__in=["TENTATIVE", "CONFIRMED"],
                start__gte=now,
            )
            .select_related("provider")
            .order_by("provider__name", "start")[:50]
        )

        return render(request, self.template_name, {
            "maintenance_in_progress": maintenance_in_progress,
            "outage_active": outage_active_count,
            "confirmed_this_week": confirmed_this_week,
            "upcoming_7": upcoming_7,
            "upcoming_30": upcoming_30,
            "unacknowledged": unacknowledged,
            "timeline_maintenance": timeline_maintenance,
            "timeline_outages": timeline_outages,
            "upcoming_by_provider": upcoming_by_provider,
        })
```

**Step 4: Create dashboard template**

Create `notices/templates/notices/dashboard.html`:

```html
{% extends 'generic/base.html' %}
{% load helpers %}

{% block title %}Notices Dashboard{% endblock %}

{% block tabs %}{% endblock %}

{% block content %}
<div class="row mb-3">
    <div class="col-12">
        <h2 class="mb-3">Notices Dashboard</h2>
    </div>
</div>

{# Stat Cards #}
<div class="row mb-3">
    <div class="col">
        <a href="{% url 'plugins:notices:maintenance_list' %}?status=IN-PROCESS" class="text-decoration-none">
            <div class="card">
                <div class="card-body text-center">
                    <h1 class="display-4 {% if maintenance_in_progress %}text-warning{% else %}text-muted{% endif %}">{{ maintenance_in_progress }}</h1>
                    <div class="text-secondary">In Progress</div>
                </div>
            </div>
        </a>
    </div>
    <div class="col">
        <a href="{% url 'plugins:notices:outage_list' %}?status=REPORTED&status=INVESTIGATING&status=IDENTIFIED&status=MONITORING" class="text-decoration-none">
            <div class="card">
                <div class="card-body text-center">
                    <h1 class="display-4 {% if outage_active %}text-danger{% else %}text-muted{% endif %}">{{ outage_active }}</h1>
                    <div class="text-secondary">Active Outages</div>
                </div>
            </div>
        </a>
    </div>
    <div class="col">
        <a href="{% url 'plugins:notices:maintenance_list' %}?status=CONFIRMED&start__gte=today&start__lte=next_week" class="text-decoration-none">
            <div class="card">
                <div class="card-body text-center">
                    <h1 class="display-4 {% if confirmed_this_week %}text-success{% else %}text-muted{% endif %}">{{ confirmed_this_week }}</h1>
                    <div class="text-secondary">Confirmed This Week</div>
                </div>
            </div>
        </a>
    </div>
    <div class="col">
        <div class="card">
            <div class="card-body text-center">
                <h1 class="display-4 {% if upcoming_7 %}text-info{% else %}text-muted{% endif %}">{{ upcoming_7 }}</h1>
                <div class="text-secondary">Upcoming (7 days)</div>
            </div>
        </div>
    </div>
    <div class="col">
        <div class="card">
            <div class="card-body text-center">
                <h1 class="display-4 {% if upcoming_30 %}text-primary{% else %}text-muted{% endif %}">{{ upcoming_30 }}</h1>
                <div class="text-secondary">Upcoming (30 days)</div>
            </div>
        </div>
    </div>
    <div class="col">
        <a href="{% url 'plugins:notices:maintenance_list' %}?acknowledged=false" class="text-decoration-none">
            <div class="card">
                <div class="card-body text-center">
                    <h1 class="display-4 {% if unacknowledged %}text-danger{% else %}text-muted{% endif %}">{{ unacknowledged }}</h1>
                    <div class="text-secondary">Unacknowledged</div>
                </div>
            </div>
        </a>
    </div>
</div>

{# Timeline: next 14 days #}
<div class="row mb-3">
    <div class="col-12">
        <div class="card">
            <h5 class="card-header">14-Day Timeline</h5>
            {% if timeline_maintenance or timeline_outages %}
            <table class="table table-hover">
                <thead>
                    <tr>
                        <th>Type</th>
                        <th>Name</th>
                        <th>Provider</th>
                        <th>Status</th>
                        <th>Start</th>
                        <th>End</th>
                        <th>Impacts</th>
                    </tr>
                </thead>
                <tbody>
                    {% for m in timeline_maintenance %}
                    <tr>
                        <td><span class="badge bg-blue">Maintenance</span></td>
                        <td><a href="{{ m.get_absolute_url }}">{{ m.name }}</a></td>
                        <td>{{ m.provider }}</td>
                        <td>{% badge m.get_status_display bg_color=m.get_status_color %}</td>
                        <td>{{ m.start }}</td>
                        <td>{{ m.end }}</td>
                        <td>{{ m.impact_count }}</td>
                    </tr>
                    {% endfor %}
                    {% for o in timeline_outages %}
                    <tr>
                        <td><span class="badge bg-red">Outage</span></td>
                        <td><a href="{{ o.get_absolute_url }}">{{ o.name }}</a></td>
                        <td>{{ o.provider }}</td>
                        <td>{% badge o.get_status_display bg_color=o.get_status_color %}</td>
                        <td>{{ o.start }}</td>
                        <td>{{ o.end|placeholder }}</td>
                        <td>{{ o.impact_count }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
            <div class="card-body text-muted">No active or upcoming events in the next 14 days.</div>
            {% endif %}
        </div>
    </div>
</div>

{# Upcoming by Provider #}
{% if upcoming_by_provider %}
<div class="row mb-3">
    <div class="col-12">
        <div class="card">
            <h5 class="card-header">Upcoming Maintenance by Provider</h5>
            <table class="table table-hover">
                <thead>
                    <tr>
                        <th>Provider</th>
                        <th>Name</th>
                        <th>Status</th>
                        <th>Start</th>
                        <th>End</th>
                    </tr>
                </thead>
                <tbody>
                    {% for m in upcoming_by_provider %}
                    <tr>
                        <td>{{ m.provider }}</td>
                        <td><a href="{{ m.get_absolute_url }}">{{ m.name }}</a></td>
                        <td>{% badge m.get_status_display bg_color=m.get_status_color %}</td>
                        <td>{{ m.start }}</td>
                        <td>{{ m.end }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</div>
{% endif %}

{% endblock content %}
```

**Step 5: Add URL route**

Edit `notices/urls.py`, add as first URL pattern (before maintenance URLs):

```python
    # Dashboard
    path("", views.DashboardView.as_view(), name="dashboard"),
```

**Step 6: Update navigation**

Edit `notices/navigation.py`, add Dashboard as first group in the menu (before Notifications group). Add this item:

```python
# Dashboard
dashboard_items = [
    PluginMenuItem(
        link="plugins:notices:dashboard",
        link_text="Summary",
        permissions=["notices.view_maintenance"],
    ),
]
```

Then update the `menu` definition to include it as the first group:

```python
menu = PluginMenu(
    label="Notices",
    groups=(
        ("Dashboard", dashboard_items),
        ("Notifications", notifications_items),
        ("Events", events_items),
        ("Messaging", messaging_items),
    ),
    icon_class="mdi mdi-wrench",
)
```

**Step 7: Run tests**

Run: `/opt/netbox/venv/bin/pytest tests/test_dashboard.py -v`
Expected: PASS

Run: `/opt/netbox/venv/bin/pytest tests/ -v`
Expected: PASS

**Step 8: Lint and commit**

```bash
/opt/netbox/venv/bin/ruff check --fix notices/views.py notices/urls.py notices/navigation.py tests/test_dashboard.py
/opt/netbox/venv/bin/ruff format notices/views.py notices/urls.py notices/navigation.py tests/test_dashboard.py
git add notices/views.py notices/urls.py notices/navigation.py notices/templates/notices/dashboard.html tests/test_dashboard.py
git commit -m "feat: add summary dashboard with stat cards and timeline

Add Dashboard view as first navigation item showing: in-progress count,
active outages, confirmed this week, upcoming 7/30 days, unacknowledged,
14-day timeline, and upcoming-by-provider table."
```

---

### Task 6: GraphQL API

**Files:**
- Create: `notices/graphql/__init__.py`
- Create: `notices/graphql/types.py`
- Create: `notices/graphql/filters.py`
- Create: `notices/graphql/schema.py`
- Test: `tests/test_graphql.py`

**Step 1: Write the failing test**

Create `tests/test_graphql.py`:

```python
"""Tests for GraphQL API types."""

import pytest


@pytest.mark.django_db
class TestGraphQLTypes:
    def test_maintenance_type_exists(self):
        from notices.graphql.types import MaintenanceType

        assert MaintenanceType is not None

    def test_outage_type_exists(self):
        from notices.graphql.types import OutageType

        assert OutageType is not None

    def test_impact_type_exists(self):
        from notices.graphql.types import ImpactType

        assert ImpactType is not None

    def test_notification_template_type_exists(self):
        from notices.graphql.types import NotificationTemplateType

        assert NotificationTemplateType is not None

    def test_schema_exports_list(self):
        from notices.graphql.schema import schema

        assert isinstance(schema, list)
        assert len(schema) == 1  # Single Query class
```

**Step 2: Run test to verify it fails**

Run: `/opt/netbox/venv/bin/pytest tests/test_graphql.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'notices.graphql'`

**Step 3: Create graphql package**

Create `notices/graphql/__init__.py` (empty file).

Create `notices/graphql/filters.py`:

```python
import strawberry
import strawberry_django
from strawberry.scalars import ID
from strawberry_django import FilterLookup

from notices import models
from netbox.graphql.filter_mixins import PrimaryModelFilterMixin

__all__ = (
    "MaintenanceFilter",
    "OutageFilter",
    "ImpactFilter",
    "EventNotificationFilter",
    "NotificationTemplateFilter",
    "PreparedNotificationFilter",
)


@strawberry_django.filter_type(models.Maintenance, lookups=True)
class MaintenanceFilter(PrimaryModelFilterMixin):
    name: FilterLookup[str] | None = strawberry_django.filter_field()
    summary: FilterLookup[str] | None = strawberry_django.filter_field()
    status: FilterLookup[str] | None = strawberry_django.filter_field()
    provider_id: ID | None = strawberry_django.filter_field()
    acknowledged: bool | None = strawberry_django.filter_field()


@strawberry_django.filter_type(models.Outage, lookups=True)
class OutageFilter(PrimaryModelFilterMixin):
    name: FilterLookup[str] | None = strawberry_django.filter_field()
    summary: FilterLookup[str] | None = strawberry_django.filter_field()
    status: FilterLookup[str] | None = strawberry_django.filter_field()
    provider_id: ID | None = strawberry_django.filter_field()
    acknowledged: bool | None = strawberry_django.filter_field()


@strawberry_django.filter_type(models.Impact, lookups=True)
class ImpactFilter(PrimaryModelFilterMixin):
    impact: FilterLookup[str] | None = strawberry_django.filter_field()
    event_object_id: ID | None = strawberry_django.filter_field()
    target_object_id: ID | None = strawberry_django.filter_field()


@strawberry_django.filter_type(models.EventNotification, lookups=True)
class EventNotificationFilter(PrimaryModelFilterMixin):
    subject: FilterLookup[str] | None = strawberry_django.filter_field()
    email_from: FilterLookup[str] | None = strawberry_django.filter_field()


@strawberry_django.filter_type(models.NotificationTemplate, lookups=True)
class NotificationTemplateFilter(PrimaryModelFilterMixin):
    name: FilterLookup[str] | None = strawberry_django.filter_field()
    slug: FilterLookup[str] | None = strawberry_django.filter_field()
    event_type: FilterLookup[str] | None = strawberry_django.filter_field()


@strawberry_django.filter_type(models.PreparedNotification, lookups=True)
class PreparedNotificationFilter(PrimaryModelFilterMixin):
    status: FilterLookup[str] | None = strawberry_django.filter_field()
    subject: FilterLookup[str] | None = strawberry_django.filter_field()
```

Create `notices/graphql/types.py`:

```python
from typing import Annotated, List

import strawberry
import strawberry_django

from notices import models
from netbox.graphql.types import NetBoxObjectType
from .filters import *

__all__ = (
    "MaintenanceType",
    "OutageType",
    "ImpactType",
    "EventNotificationType",
    "NotificationTemplateType",
    "PreparedNotificationType",
)


@strawberry_django.type(
    models.Maintenance,
    fields="__all__",
    filters=MaintenanceFilter,
    pagination=True,
    exclude=("impacts",),
)
class MaintenanceType(NetBoxObjectType):
    provider: Annotated["ProviderType", strawberry.lazy("circuits.graphql.types")]


@strawberry_django.type(
    models.Outage,
    fields="__all__",
    filters=OutageFilter,
    pagination=True,
    exclude=("impacts",),
)
class OutageType(NetBoxObjectType):
    provider: Annotated["ProviderType", strawberry.lazy("circuits.graphql.types")]


@strawberry_django.type(
    models.Impact,
    fields="__all__",
    filters=ImpactFilter,
    pagination=True,
    exclude=("event", "target"),
)
class ImpactType(NetBoxObjectType):
    pass


@strawberry_django.type(
    models.EventNotification,
    fields="__all__",
    filters=EventNotificationFilter,
    pagination=True,
    exclude=("event",),
)
class EventNotificationType(NetBoxObjectType):
    pass


@strawberry_django.type(
    models.NotificationTemplate,
    fields="__all__",
    filters=NotificationTemplateFilter,
    pagination=True,
)
class NotificationTemplateType(NetBoxObjectType):
    pass


@strawberry_django.type(
    models.PreparedNotification,
    fields="__all__",
    filters=PreparedNotificationFilter,
    pagination=True,
    exclude=("event",),
)
class PreparedNotificationType(NetBoxObjectType):
    pass
```

Create `notices/graphql/schema.py`:

```python
from typing import List

import strawberry
import strawberry_django

from .types import *


@strawberry.type(name="Query")
class NoticesQuery:
    maintenance: MaintenanceType = strawberry_django.field()
    maintenance_list: List[MaintenanceType] = strawberry_django.field()

    outage: OutageType = strawberry_django.field()
    outage_list: List[OutageType] = strawberry_django.field()

    impact: ImpactType = strawberry_django.field()
    impact_list: List[ImpactType] = strawberry_django.field()

    event_notification: EventNotificationType = strawberry_django.field()
    event_notification_list: List[EventNotificationType] = strawberry_django.field()

    notification_template: NotificationTemplateType = strawberry_django.field()
    notification_template_list: List[NotificationTemplateType] = strawberry_django.field()

    prepared_notification: PreparedNotificationType = strawberry_django.field()
    prepared_notification_list: List[PreparedNotificationType] = strawberry_django.field()


schema = [NoticesQuery]
```

**Step 4: Update PluginConfig**

Edit `notices/__init__.py`, add `graphql_schema` attribute to `NoticesConfig` (after `base_url`):

```python
    graphql_schema = "graphql.schema.schema"
```

**Step 5: Run tests**

Run: `/opt/netbox/venv/bin/pytest tests/test_graphql.py -v`
Expected: PASS

Run: `/opt/netbox/venv/bin/pytest tests/ -v`
Expected: PASS

**Step 6: Lint and commit**

```bash
/opt/netbox/venv/bin/ruff check --fix notices/graphql/ tests/test_graphql.py
/opt/netbox/venv/bin/ruff format notices/graphql/ tests/test_graphql.py
git add notices/graphql/ tests/test_graphql.py notices/__init__.py
git commit -m "feat: add GraphQL API for all plugin models

Add Strawberry GraphQL types, filters, and schema for Maintenance,
Outage, Impact, EventNotification, NotificationTemplate, and
PreparedNotification. Register via PluginConfig.graphql_schema."
```

---

### Task 7: brief_fields on API Serializers

**Files:**
- Modify: `notices/api/serializers/events.py`
- Modify: `notices/api/serializers/messaging.py`
- Test: `tests/test_brief_fields.py`

**Step 1: Write the failing test**

Create `tests/test_brief_fields.py`:

```python
"""Tests for brief_fields on API serializers."""

import pytest


class TestBriefFields:
    def test_maintenance_serializer_has_brief_fields(self):
        from notices.api.serializers.events import MaintenanceSerializer

        assert hasattr(MaintenanceSerializer.Meta, "brief_fields")
        assert "id" in MaintenanceSerializer.Meta.brief_fields
        assert "url" in MaintenanceSerializer.Meta.brief_fields
        assert "display" in MaintenanceSerializer.Meta.brief_fields
        assert "name" in MaintenanceSerializer.Meta.brief_fields

    def test_outage_serializer_has_brief_fields(self):
        from notices.api.serializers.events import OutageSerializer

        assert hasattr(OutageSerializer.Meta, "brief_fields")
        assert "id" in OutageSerializer.Meta.brief_fields

    def test_impact_serializer_has_brief_fields(self):
        from notices.api.serializers.events import ImpactSerializer

        assert hasattr(ImpactSerializer.Meta, "brief_fields")

    def test_notification_template_serializer_has_brief_fields(self):
        from notices.api.serializers.messaging import NotificationTemplateSerializer

        assert hasattr(NotificationTemplateSerializer.Meta, "brief_fields")
        assert "name" in NotificationTemplateSerializer.Meta.brief_fields
        assert "slug" in NotificationTemplateSerializer.Meta.brief_fields

    def test_prepared_notification_serializer_has_brief_fields(self):
        from notices.api.serializers.messaging import PreparedNotificationSerializer

        assert hasattr(PreparedNotificationSerializer.Meta, "brief_fields")
```

**Step 2: Run test to verify it fails**

Run: `/opt/netbox/venv/bin/pytest tests/test_brief_fields.py -v`
Expected: FAIL — `AttributeError: type object 'Meta' has no attribute 'brief_fields'`

**Step 3: Add brief_fields**

Edit `notices/api/serializers/events.py`:

In `MaintenanceSerializer.Meta` (after `fields` tuple, around line 206):
```python
        brief_fields = ("id", "url", "display", "name", "status", "provider", "start", "end")
```

In `OutageSerializer.Meta` (after `fields` tuple, around line 245):
```python
        brief_fields = ("id", "url", "display", "name", "status", "provider", "start", "end")
```

In `ImpactSerializer.Meta` (after `fields` tuple, around line 291):
```python
        brief_fields = ("id", "url", "display", "impact")
```

In `EventNotificationSerializer.Meta` (after `fields` tuple, around line 371):
```python
        brief_fields = ("id", "url", "display", "subject", "email_from", "email_received")
```

Edit `notices/api/serializers/messaging.py`:

In `NotificationTemplateSerializer.Meta` (after `fields` list, around line 91):
```python
        brief_fields = ("id", "url", "display", "name", "slug", "description")
```

In `PreparedNotificationSerializer.Meta` (after `read_only_fields`, around line 218):
```python
        brief_fields = ("id", "url", "display", "subject", "status")
```

In `SentNotificationSerializer.Meta` (after `read_only_fields`, around line 298):
```python
        brief_fields = ("id", "url", "display", "subject", "status", "sent_at")
```

**Step 4: Run tests**

Run: `/opt/netbox/venv/bin/pytest tests/test_brief_fields.py -v`
Expected: PASS

Run: `/opt/netbox/venv/bin/pytest tests/ -v`
Expected: PASS

**Step 5: Lint and commit**

```bash
/opt/netbox/venv/bin/ruff check --fix notices/api/serializers/ tests/test_brief_fields.py
/opt/netbox/venv/bin/ruff format notices/api/serializers/ tests/test_brief_fields.py
git add notices/api/serializers/ tests/test_brief_fields.py
git commit -m "feat: add brief_fields to all API serializers

Add brief_fields tuples to serializer Meta classes for compact nested
representations, following the modern NetBox serializer pattern."
```
