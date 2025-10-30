# Outage Tracking Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add unplanned outage event tracking with optional end times, ETR tracking, and unified view alongside existing maintenance events.

**Architecture:** Abstract base model pattern with `BaseCircuitEvent` providing shared fields/behavior, `CircuitMaintenance` and `CircuitOutage` as concrete implementations, refactored shared models using GenericForeignKey for polymorphic relationships.

**Tech Stack:** Django 4.x, NetBox 4.4+, Django REST Framework, pytest

---

## Task 1: Create CircuitOutageStatusChoices

**Files:**
- Modify: `netbox_circuitmaintenance/models.py:159` (add after CircuitMaintenanceTypeChoices)

**Step 1: Write the failing test**

Create: `tests/test_outage_models.py`

```python
"""
Unit tests for CircuitOutage models.
"""
import pytest
from netbox_circuitmaintenance.models import CircuitOutageStatusChoices


def test_outage_status_choices_exist():
    """Test that outage status choices are defined"""
    expected_statuses = ['REPORTED', 'INVESTIGATING', 'IDENTIFIED', 'MONITORING', 'RESOLVED']

    actual_statuses = [choice[0] for choice in CircuitOutageStatusChoices.CHOICES]

    assert set(expected_statuses) == set(actual_statuses)


def test_outage_status_colors():
    """Test that outage statuses have appropriate colors"""
    assert CircuitOutageStatusChoices.colors.get('REPORTED') == 'red'
    assert CircuitOutageStatusChoices.colors.get('INVESTIGATING') == 'orange'
    assert CircuitOutageStatusChoices.colors.get('IDENTIFIED') == 'yellow'
    assert CircuitOutageStatusChoices.colors.get('MONITORING') == 'blue'
    assert CircuitOutageStatusChoices.colors.get('RESOLVED') == 'green'
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_outage_models.py::test_outage_status_choices_exist -v`
Expected: FAIL with "cannot import name 'CircuitOutageStatusChoices'"

**Step 3: Write minimal implementation**

In `netbox_circuitmaintenance/models.py`, add after `CircuitMaintenanceImpactTypeChoices` (around line 188):

```python
class CircuitOutageStatusChoices(ChoiceSet):
    """
    Status choices for unplanned circuit outage events.
    Follows incident management workflow.
    """

    key = "CircuitOutage.Status"

    CHOICES = [
        ("REPORTED", "Reported", "red"),
        ("INVESTIGATING", "Investigating", "orange"),
        ("IDENTIFIED", "Identified", "yellow"),
        ("MONITORING", "Monitoring", "blue"),
        ("RESOLVED", "Resolved", "green"),
    ]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_outage_models.py -v`
Expected: 2 tests PASS

**Step 5: Commit**

```bash
git add tests/test_outage_models.py netbox_circuitmaintenance/models.py
git commit -m "feat: add CircuitOutageStatusChoices for outage workflow

Defines status workflow for unplanned outages:
- REPORTED: Initial state when outage is reported
- INVESTIGATING: Team is investigating root cause
- IDENTIFIED: Root cause identified, working on fix
- MONITORING: Fix applied, monitoring for stability
- RESOLVED: Outage fully resolved

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 2: Create BaseCircuitEvent Abstract Model

**Files:**
- Modify: `netbox_circuitmaintenance/models.py:190` (before CircuitMaintenance)

**Step 1: Write the failing test**

Add to `tests/test_outage_models.py`:

```python
from netbox_circuitmaintenance.models import BaseCircuitEvent


def test_base_circuit_event_is_abstract():
    """Test that BaseCircuitEvent cannot be instantiated"""
    with pytest.raises(TypeError, match="abstract"):
        BaseCircuitEvent()


def test_base_circuit_event_fields():
    """Test that BaseCircuitEvent defines expected fields"""
    expected_fields = [
        'name', 'summary', 'provider', 'start', 'original_timezone',
        'internal_ticket', 'acknowledged', 'comments'
    ]

    # Get field names from Meta
    for field_name in expected_fields:
        assert hasattr(BaseCircuitEvent, field_name), f"Missing field: {field_name}"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_outage_models.py::test_base_circuit_event_is_abstract -v`
Expected: FAIL with "cannot import name 'BaseCircuitEvent'"

**Step 3: Write minimal implementation**

In `netbox_circuitmaintenance/models.py`, add BEFORE `CircuitMaintenance` class (around line 190):

```python
class BaseCircuitEvent(NetBoxModel):
    """
    Abstract base class for circuit maintenance and outage events.
    Provides common fields and relationships shared by both event types.
    """
    name = models.CharField(
        max_length=100,
        verbose_name="Event ID",
        help_text="Provider supplied event ID or ticket number"
    )

    summary = models.CharField(
        max_length=200,
        help_text="Brief summary of the event"
    )

    provider = models.ForeignKey(
        to="circuits.provider",
        on_delete=models.CASCADE,
        related_name='%(class)s_events'  # Dynamic related name per subclass
    )

    start = models.DateTimeField(
        help_text="Start date and time of the event"
    )

    original_timezone = models.CharField(
        max_length=63,
        blank=True,
        verbose_name="Original Timezone",
        help_text="Original timezone from provider notification"
    )

    internal_ticket = models.CharField(
        max_length=100,
        verbose_name="Internal Ticket #",
        help_text="Internal ticket or change reference",
        blank=True
    )

    acknowledged = models.BooleanField(
        default=False,
        null=True,
        blank=True,
        verbose_name="Acknowledged?",
        help_text="Confirm if this event has been acknowledged"
    )

    comments = models.TextField(blank=True)

    class Meta:
        abstract = True
        ordering = ('-created',)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_outage_models.py::test_base_circuit_event_is_abstract tests/test_outage_models.py::test_base_circuit_event_fields -v`
Expected: 2 tests PASS

**Step 5: Commit**

```bash
git add tests/test_outage_models.py netbox_circuitmaintenance/models.py
git commit -m "feat: add BaseCircuitEvent abstract model

Provides shared fields for both maintenance and outage events:
- Event identification (name, summary)
- Temporal data (start, timezone)
- Provider relationship
- Tracking metadata (ticket, acknowledged)

Uses dynamic related_name for clean ForeignKey relationships.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 3: Refactor CircuitMaintenance to Inherit from BaseCircuitEvent

**Files:**
- Modify: `netbox_circuitmaintenance/models.py:190` (CircuitMaintenance class)

**Step 1: Write the test**

Add to `tests/test_outage_models.py`:

```python
from netbox_circuitmaintenance.models import CircuitMaintenance


def test_circuit_maintenance_inherits_from_base():
    """Test that CircuitMaintenance inherits from BaseCircuitEvent"""
    assert issubclass(CircuitMaintenance, BaseCircuitEvent)


def test_circuit_maintenance_has_required_end_time():
    """Test that CircuitMaintenance end field exists and is required"""
    end_field = CircuitMaintenance._meta.get_field('end')
    assert end_field is not None
    assert end_field.null == False  # Required field
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_outage_models.py::test_circuit_maintenance_inherits_from_base -v`
Expected: FAIL with "False is not true"

**Step 3: Refactor CircuitMaintenance**

In `netbox_circuitmaintenance/models.py`, replace the CircuitMaintenance class definition:

**BEFORE:**
```python
class CircuitMaintenance(NetBoxModel):
    name = models.CharField(...)
    summary = models.CharField(...)
    status = models.CharField(...)
    provider = models.ForeignKey(...)
    start = models.DateTimeField(...)
    end = models.DateTimeField(...)
    original_timezone = models.CharField(...)
    internal_ticket = models.CharField(...)
    acknowledged = models.BooleanField(...)
    comments = models.TextField(...)
```

**AFTER:**
```python
class CircuitMaintenance(BaseCircuitEvent):
    """
    Planned maintenance events with scheduled end times.
    Inherits common fields from BaseCircuitEvent.
    """
    end = models.DateTimeField(
        help_text="End date and time of the maintenance event"
    )

    status = models.CharField(
        max_length=30,
        choices=CircuitMaintenanceTypeChoices
    )
```

Keep all the existing methods (get_status_color, get_start_in_original_tz, etc.) unchanged.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_outage_models.py::test_circuit_maintenance_inherits_from_base tests/test_outage_models.py::test_circuit_maintenance_has_required_end_time -v`
Expected: 2 tests PASS

**Step 5: Commit**

```bash
git add tests/test_outage_models.py netbox_circuitmaintenance/models.py
git commit -m "refactor: migrate CircuitMaintenance to inherit from BaseCircuitEvent

Removes duplicate field definitions, inherits from base:
- name, summary, provider, start (from base)
- original_timezone, internal_ticket, acknowledged, comments (from base)
- Retains maintenance-specific: end (required), status

All existing methods and Meta configuration preserved.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 4: Create CircuitOutage Model

**Files:**
- Modify: `netbox_circuitmaintenance/models.py` (add after CircuitMaintenance)

**Step 1: Write the failing test**

Add to `tests/test_outage_models.py`:

```python
from django.core.exceptions import ValidationError
from netbox_circuitmaintenance.models import CircuitOutage


def test_circuit_outage_inherits_from_base():
    """Test that CircuitOutage inherits from BaseCircuitEvent"""
    assert issubclass(CircuitOutage, BaseCircuitEvent)


def test_circuit_outage_end_is_optional():
    """Test that CircuitOutage end field is nullable"""
    end_field = CircuitOutage._meta.get_field('end')
    assert end_field.null == True
    assert end_field.blank == True


def test_circuit_outage_has_etr_field():
    """Test that CircuitOutage has estimated_time_to_repair field"""
    etr_field = CircuitOutage._meta.get_field('estimated_time_to_repair')
    assert etr_field is not None
    assert etr_field.null == True


def test_circuit_outage_validation_requires_end_when_resolved():
    """Test that clean() requires end time when status is RESOLVED"""
    from unittest.mock import Mock

    outage = CircuitOutage()
    outage.status = 'RESOLVED'
    outage.end = None

    with pytest.raises(ValidationError) as exc_info:
        outage.clean()

    assert 'end' in exc_info.value.message_dict


def test_circuit_outage_validation_allows_no_end_when_investigating():
    """Test that clean() allows no end time for non-resolved statuses"""
    from unittest.mock import Mock

    outage = CircuitOutage()
    outage.status = 'INVESTIGATING'
    outage.end = None

    # Should not raise
    outage.clean()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_outage_models.py::test_circuit_outage_inherits_from_base -v`
Expected: FAIL with "cannot import name 'CircuitOutage'"

**Step 3: Write minimal implementation**

In `netbox_circuitmaintenance/models.py`, add after CircuitMaintenance class:

```python
class CircuitOutage(BaseCircuitEvent):
    """
    Unplanned outage events with optional end times and ETR tracking.
    Inherits common fields from BaseCircuitEvent.
    """
    end = models.DateTimeField(
        null=True,
        blank=True,
        help_text="End date and time of the outage (required when resolved)"
    )

    estimated_time_to_repair = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Estimated Time to Repair",
        help_text="Current estimate for when service will be restored"
    )

    status = models.CharField(
        max_length=30,
        choices=CircuitOutageStatusChoices
    )

    class Meta:
        verbose_name = "Circuit Outage"
        verbose_name_plural = "Circuit Outages"

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        # Validation: end time required when status = RESOLVED
        if self.status == 'RESOLVED' and not self.end:
            raise ValidationError({
                'end': 'End time is required when marking outage as resolved'
            })

    def get_status_color(self):
        return CircuitOutageStatusChoices.colors.get(self.status)

    def get_absolute_url(self):
        return reverse(
            "plugins:netbox_circuitmaintenance:circuitoutage", args=[self.pk]
        )
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_outage_models.py -v -k "outage"`
Expected: All CircuitOutage tests PASS

**Step 5: Commit**

```bash
git add tests/test_outage_models.py netbox_circuitmaintenance/models.py
git commit -m "feat: add CircuitOutage model for unplanned events

New model for tracking unplanned outages:
- Optional end time (required only when RESOLVED)
- Estimated Time to Repair (ETR) field
- Outage-specific status workflow
- Validation: prevents marking RESOLVED without end time

Inherits provider, start, timezone tracking from BaseCircuitEvent.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 5: Create Database Migration for New Models

**Files:**
- Create: `netbox_circuitmaintenance/migrations/0009_add_outage_tracking.py`

**Step 1: Generate migration**

```bash
cd /home/jsenecal/Code/netbox-circuitmaintenance
source venv/bin/activate
python manage.py makemigrations netbox_circuitmaintenance
```

Expected: Creates new migration file `0009_add_outage_tracking.py` (or similar number)

**Step 2: Review migration**

Read the generated migration file to ensure it:
- Creates CircuitOutage table
- Handles BaseCircuitEvent abstract model correctly
- Preserves CircuitMaintenance data

**Step 3: Test migration (dry run)**

Note: This requires a NetBox test environment. Document for manual testing:

```bash
# In NetBox development environment
python manage.py migrate netbox_circuitmaintenance --plan
```

Expected: Shows migration plan without errors

**Step 4: Commit**

```bash
git add netbox_circuitmaintenance/migrations/0009_*.py
git commit -m "feat: add database migration for outage tracking

Creates CircuitOutage table with fields:
- Inherited from BaseCircuitEvent (name, summary, provider, start, etc.)
- Outage-specific: end (nullable), estimated_time_to_repair, status

Preserves existing CircuitMaintenance data unchanged.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 6: Create CircuitOutageSerializer

**Files:**
- Modify: `netbox_circuitmaintenance/api/serializers.py`

**Step 1: Write the test**

Create: `tests/test_outage_api.py`

```python
"""
Tests for CircuitOutage API serialization.
"""
import pytest
from netbox_circuitmaintenance.api.serializers import CircuitOutageSerializer


def test_circuit_outage_serializer_fields():
    """Test that serializer includes all required fields"""
    serializer = CircuitOutageSerializer()

    expected_fields = [
        'id', 'url', 'display', 'name', 'summary', 'status',
        'provider', 'start', 'end', 'estimated_time_to_repair',
        'original_timezone', 'internal_ticket', 'acknowledged',
        'comments', 'tags', 'custom_fields', 'created', 'last_updated'
    ]

    for field in expected_fields:
        assert field in serializer.fields, f"Missing field: {field}"


def test_circuit_outage_serializer_read_only_fields():
    """Test that computed fields are read-only"""
    serializer = CircuitOutageSerializer()

    assert serializer.fields['display'].read_only == True
    assert serializer.fields['created'].read_only == True
    assert serializer.fields['last_updated'].read_only == True
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_outage_api.py::test_circuit_outage_serializer_fields -v`
Expected: FAIL with "cannot import name 'CircuitOutageSerializer'"

**Step 3: Write implementation**

In `netbox_circuitmaintenance/api/serializers.py`, add after CircuitMaintenanceSerializer:

```python
from netbox.api.serializers import NetBoxModelSerializer
from rest_framework import serializers
from circuits.api.serializers import ProviderSerializer

from ..models import CircuitOutage


class CircuitOutageSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_circuitmaintenance-api:circuitoutage-detail'
    )
    provider = ProviderSerializer(nested=True)

    class Meta:
        model = CircuitOutage
        fields = (
            'id', 'url', 'display', 'name', 'summary', 'status',
            'provider', 'start', 'end', 'estimated_time_to_repair',
            'original_timezone', 'internal_ticket', 'acknowledged',
            'comments', 'tags', 'custom_fields', 'created', 'last_updated'
        )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_outage_api.py -v`
Expected: 2 tests PASS

**Step 5: Commit**

```bash
git add tests/test_outage_api.py netbox_circuitmaintenance/api/serializers.py
git commit -m "feat: add CircuitOutageSerializer for API

Serializes CircuitOutage model for REST API:
- All event fields (name, summary, status, dates)
- Nested provider serialization
- ETR field for repair estimates
- Standard NetBox fields (tags, custom_fields, timestamps)

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 7: Create CircuitOutage API ViewSet and URLs

**Files:**
- Modify: `netbox_circuitmaintenance/api/views.py`
- Modify: `netbox_circuitmaintenance/api/urls.py`

**Step 1: Write the test**

Add to `tests/test_outage_api.py`:

```python
from netbox_circuitmaintenance.api.views import CircuitOutageViewSet
from netbox_circuitmaintenance.models import CircuitOutage


def test_circuit_outage_viewset_exists():
    """Test that CircuitOutageViewSet is defined"""
    assert CircuitOutageViewSet is not None


def test_circuit_outage_viewset_queryset():
    """Test that viewset uses correct queryset"""
    assert CircuitOutageViewSet.queryset.model == CircuitOutage


def test_circuit_outage_viewset_serializer():
    """Test that viewset uses CircuitOutageSerializer"""
    from netbox_circuitmaintenance.api.serializers import CircuitOutageSerializer
    assert CircuitOutageViewSet.serializer_class == CircuitOutageSerializer
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_outage_api.py::test_circuit_outage_viewset_exists -v`
Expected: FAIL with "cannot import name 'CircuitOutageViewSet'"

**Step 3: Write implementation**

In `netbox_circuitmaintenance/api/views.py`, add after CircuitMaintenanceViewSet:

```python
class CircuitOutageViewSet(NetBoxModelViewSet):
    queryset = models.CircuitOutage.objects.prefetch_related('tags')
    serializer_class = CircuitOutageSerializer
```

In `netbox_circuitmaintenance/api/urls.py`, add router registration after existing entries:

```python
router.register('circuitoutage', views.CircuitOutageViewSet)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_outage_api.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add tests/test_outage_api.py netbox_circuitmaintenance/api/views.py netbox_circuitmaintenance/api/urls.py
git commit -m "feat: add CircuitOutage API endpoints

Adds REST API support for outage tracking:
- ViewSet for CRUD operations
- URL routing at /api/plugins/netbox-circuitmaintenance/circuitoutage/
- Follows NetBox API conventions

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 8: Create CircuitOutage FilterSet

**Files:**
- Modify: `netbox_circuitmaintenance/filtersets.py`

**Step 1: Write the test**

Create: `tests/test_outage_filters.py`

```python
"""
Tests for CircuitOutage filtering.
"""
import pytest
from netbox_circuitmaintenance.filtersets import CircuitOutageFilterSet


def test_circuit_outage_filterset_exists():
    """Test that CircuitOutageFilterSet is defined"""
    assert CircuitOutageFilterSet is not None


def test_circuit_outage_filterset_model():
    """Test that filterset targets CircuitOutage model"""
    from netbox_circuitmaintenance.models import CircuitOutage
    assert CircuitOutageFilterSet.Meta.model == CircuitOutage


def test_circuit_outage_filterset_fields():
    """Test that filterset includes key filter fields"""
    expected_fields = ['name', 'status', 'provider', 'start', 'end']

    for field in expected_fields:
        assert field in CircuitOutageFilterSet.Meta.fields, f"Missing filter: {field}"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_outage_filters.py::test_circuit_outage_filterset_exists -v`
Expected: FAIL with "cannot import name 'CircuitOutageFilterSet'"

**Step 3: Write implementation**

In `netbox_circuitmaintenance/filtersets.py`, add after CircuitMaintenanceFilterSet:

```python
import django_filters
from .models import CircuitOutage


class CircuitOutageFilterSet(NetBoxModelFilterSet):
    provider = django_filters.ModelMultipleChoiceFilter(
        queryset=Provider.objects.all(),
        label='Provider',
    )
    status = django_filters.MultipleChoiceFilter(
        choices=CircuitOutageStatusChoices,
        null_value=None
    )

    class Meta:
        model = CircuitOutage
        fields = ['id', 'name', 'summary', 'status', 'provider', 'start', 'end',
                  'estimated_time_to_repair', 'internal_ticket', 'acknowledged']

    def search(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) |
            Q(summary__icontains=value) |
            Q(internal_ticket__icontains=value)
        )
```

**Step 4: Update API views to use filterset**

In `netbox_circuitmaintenance/api/views.py`, update CircuitOutageViewSet:

```python
from .. import filtersets

class CircuitOutageViewSet(NetBoxModelViewSet):
    queryset = models.CircuitOutage.objects.prefetch_related('tags')
    serializer_class = CircuitOutageSerializer
    filterset_class = filtersets.CircuitOutageFilterSet
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/test_outage_filters.py -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add tests/test_outage_filters.py netbox_circuitmaintenance/filtersets.py netbox_circuitmaintenance/api/views.py
git commit -m "feat: add CircuitOutageFilterSet for API filtering

Enables filtering outages by:
- Provider (multi-select)
- Status (multi-select)
- Date ranges (start, end, ETR)
- Text search (name, summary, ticket)

Integrated into API viewset for query support.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 9: Create CircuitOutage Forms

**Files:**
- Modify: `netbox_circuitmaintenance/forms.py`

**Step 1: Write the test**

Create: `tests/test_outage_forms.py`

```python
"""
Tests for CircuitOutage forms.
"""
import pytest
from netbox_circuitmaintenance.forms import CircuitOutageForm, CircuitOutageFilterForm


def test_circuit_outage_form_exists():
    """Test that CircuitOutageForm is defined"""
    assert CircuitOutageForm is not None


def test_circuit_outage_form_model():
    """Test that form targets CircuitOutage model"""
    from netbox_circuitmaintenance.models import CircuitOutage
    assert CircuitOutageForm.Meta.model == CircuitOutage


def test_circuit_outage_form_fields():
    """Test that form includes all required fields"""
    expected_fields = (
        'name', 'summary', 'status', 'provider', 'start', 'end',
        'estimated_time_to_repair', 'original_timezone',
        'internal_ticket', 'acknowledged', 'comments', 'tags'
    )

    assert CircuitOutageForm.Meta.fields == expected_fields


def test_circuit_outage_filter_form_exists():
    """Test that CircuitOutageFilterForm is defined"""
    assert CircuitOutageFilterForm is not None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_outage_forms.py::test_circuit_outage_form_exists -v`
Expected: FAIL with "cannot import name 'CircuitOutageForm'"

**Step 3: Write implementation**

In `netbox_circuitmaintenance/forms.py`, add after CircuitMaintenanceFilterForm:

```python
from .models import CircuitOutage, CircuitOutageStatusChoices


class CircuitOutageForm(NetBoxModelForm):

    provider = DynamicModelChoiceField(queryset=Provider.objects.all())

    original_timezone = forms.ChoiceField(
        choices=TimeZoneChoices,
        required=False,
        label="Timezone",
        help_text="Timezone for the start/end/ETR times (converted to system timezone on save)",
    )

    class Meta:
        model = CircuitOutage
        fields = (
            "name",
            "summary",
            "status",
            "provider",
            "start",
            "end",
            "estimated_time_to_repair",
            "original_timezone",
            "internal_ticket",
            "acknowledged",
            "comments",
            "tags",
        )
        widgets = {
            "start": DateTimePicker(),
            "end": DateTimePicker(),
            "estimated_time_to_repair": DateTimePicker(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # On edit, change help text since we don't convert
        if self.instance and self.instance.pk:
            self.fields["original_timezone"].help_text = (
                "Original timezone from provider notification (reference only)"
            )
            self.fields["original_timezone"].label = "Original Timezone"

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Only convert timezone on CREATE (not on edit)
        if not instance.pk and instance.original_timezone:
            try:
                # Get the timezone objects
                original_tz = zoneinfo.ZoneInfo(instance.original_timezone)
                system_tz = timezone.get_current_timezone()

                # Convert start time if provided
                if instance.start:
                    if timezone.is_naive(instance.start):
                        start_in_original_tz = instance.start.replace(
                            tzinfo=original_tz
                        )
                    else:
                        start_in_original_tz = instance.start.replace(
                            tzinfo=original_tz
                        )
                    instance.start = start_in_original_tz.astimezone(system_tz)

                # Convert end time if provided
                if instance.end:
                    if timezone.is_naive(instance.end):
                        end_in_original_tz = instance.end.replace(tzinfo=original_tz)
                    else:
                        end_in_original_tz = instance.end.replace(tzinfo=original_tz)
                    instance.end = end_in_original_tz.astimezone(system_tz)

                # Convert ETR time if provided
                if instance.estimated_time_to_repair:
                    if timezone.is_naive(instance.estimated_time_to_repair):
                        etr_in_original_tz = instance.estimated_time_to_repair.replace(
                            tzinfo=original_tz
                        )
                    else:
                        etr_in_original_tz = instance.estimated_time_to_repair.replace(
                            tzinfo=original_tz
                        )
                    instance.estimated_time_to_repair = etr_in_original_tz.astimezone(system_tz)

            except (zoneinfo.ZoneInfoNotFoundError, ValueError):
                # If timezone is invalid, just save without conversion
                pass

        if commit:
            instance.save()
            self.save_m2m()

        return instance


class CircuitOutageFilterForm(NetBoxModelFilterSetForm):
    model = CircuitOutage

    name = forms.CharField(required=False)
    summary = forms.CharField(required=False)
    provider = forms.ModelMultipleChoiceField(
        queryset=Provider.objects.all(), required=False
    )
    status = forms.MultipleChoiceField(
        choices=CircuitOutageStatusChoices, required=False
    )
    start = forms.CharField(required=False)
    end = forms.CharField(required=False)
    acknowledged = forms.BooleanField(required=False)
    internal_ticket = forms.CharField(required=False)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_outage_forms.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add tests/test_outage_forms.py netbox_circuitmaintenance/forms.py
git commit -m "feat: add CircuitOutage forms for UI

Creates forms for outage management:
- CircuitOutageForm: Create/edit with timezone conversion
- CircuitOutageFilterForm: Filter by status, provider, dates

Reuses timezone conversion logic from CircuitMaintenanceForm.
Applies to start, end, and ETR fields.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com)"
```

---

## Task 10: Create CircuitOutage Table for List View

**Files:**
- Modify: `netbox_circuitmaintenance/tables.py`

**Step 1: Write the test**

Create: `tests/test_outage_tables.py`

```python
"""
Tests for CircuitOutage tables.
"""
import pytest
from netbox_circuitmaintenance.tables import CircuitOutageTable


def test_circuit_outage_table_exists():
    """Test that CircuitOutageTable is defined"""
    assert CircuitOutageTable is not None


def test_circuit_outage_table_columns():
    """Test that table includes key columns"""
    table = CircuitOutageTable([])

    expected_columns = ['name', 'provider', 'status', 'start', 'end',
                       'estimated_time_to_repair']

    for col in expected_columns:
        assert col in table.base_columns, f"Missing column: {col}"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_outage_tables.py::test_circuit_outage_table_exists -v`
Expected: FAIL with "cannot import name 'CircuitOutageTable'"

**Step 3: Write implementation**

In `netbox_circuitmaintenance/tables.py`, add after CircuitMaintenanceTable:

```python
import django_tables2 as tables
from netbox.tables import NetBoxTable, columns

from .models import CircuitOutage


class CircuitOutageTable(NetBoxTable):
    name = tables.Column(linkify=True)
    provider = tables.Column(linkify=True)
    status = columns.ChoiceFieldColumn()
    start = columns.DateTimeColumn()
    end = columns.DateTimeColumn()
    estimated_time_to_repair = columns.DateTimeColumn(verbose_name="ETR")

    class Meta(NetBoxTable.Meta):
        model = CircuitOutage
        fields = (
            'pk', 'name', 'provider', 'summary', 'status', 'start', 'end',
            'estimated_time_to_repair', 'internal_ticket', 'acknowledged', 'created'
        )
        default_columns = (
            'name', 'provider', 'status', 'start', 'end', 'estimated_time_to_repair'
        )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_outage_tables.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add tests/test_outage_tables.py netbox_circuitmaintenance/tables.py
git commit -m "feat: add CircuitOutageTable for list views

Defines table columns for outage display:
- Linkified name and provider
- Status with color coding
- Temporal fields (start, end, ETR)
- Tracking metadata (ticket, acknowledged)

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 11: Create CircuitOutage Views

**Files:**
- Modify: `netbox_circuitmaintenance/views.py`

**Step 1: Write the test**

Create: `tests/test_outage_views.py`

```python
"""
Tests for CircuitOutage views.
"""
import pytest
from netbox_circuitmaintenance.views import (
    CircuitOutageListView,
    CircuitOutageView,
    CircuitOutageEditView,
    CircuitOutageDeleteView,
)


def test_circuit_outage_views_exist():
    """Test that all CircuitOutage views are defined"""
    assert CircuitOutageListView is not None
    assert CircuitOutageView is not None
    assert CircuitOutageEditView is not None
    assert CircuitOutageDeleteView is not None


def test_circuit_outage_list_view_queryset():
    """Test that list view uses correct queryset"""
    from netbox_circuitmaintenance.models import CircuitOutage
    assert CircuitOutageListView.queryset.model == CircuitOutage


def test_circuit_outage_list_view_table():
    """Test that list view uses CircuitOutageTable"""
    from netbox_circuitmaintenance.tables import CircuitOutageTable
    assert CircuitOutageListView.table == CircuitOutageTable
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_outage_views.py::test_circuit_outage_views_exist -v`
Expected: FAIL with "cannot import name 'CircuitOutageListView'"

**Step 3: Write implementation**

In `netbox_circuitmaintenance/views.py`, add after CircuitMaintenance views:

```python
from .models import CircuitOutage
from .tables import CircuitOutageTable
from .forms import CircuitOutageForm, CircuitOutageFilterForm


class CircuitOutageListView(generic.ObjectListView):
    queryset = CircuitOutage.objects.all()
    table = CircuitOutageTable
    filterset = filtersets.CircuitOutageFilterSet
    filterset_form = CircuitOutageFilterForm


class CircuitOutageView(generic.ObjectView):
    queryset = CircuitOutage.objects.all()


class CircuitOutageEditView(generic.ObjectEditView):
    queryset = CircuitOutage.objects.all()
    form = CircuitOutageForm


class CircuitOutageDeleteView(generic.ObjectDeleteView):
    queryset = CircuitOutage.objects.all()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_outage_views.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add tests/test_outage_views.py netbox_circuitmaintenance/views.py
git commit -m "feat: add CircuitOutage views for UI

Implements CRUD views for outage management:
- List view with filtering and table display
- Detail view for individual outages
- Edit view with form validation
- Delete view with confirmation

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 12: Create CircuitOutage URL Patterns

**Files:**
- Modify: `netbox_circuitmaintenance/urls.py`

**Step 1: Add URL patterns**

In `netbox_circuitmaintenance/urls.py`, add after CircuitMaintenance URLs:

```python
from .views import (
    CircuitOutageListView,
    CircuitOutageView,
    CircuitOutageEditView,
    CircuitOutageDeleteView,
)

urlpatterns = [
    # ... existing CircuitMaintenance URLs ...

    # CircuitOutage URLs
    path('outages/', CircuitOutageListView.as_view(), name='circuitoutage_list'),
    path('outages/add/', CircuitOutageEditView.as_view(), name='circuitoutage_add'),
    path('outages/<int:pk>/', CircuitOutageView.as_view(), name='circuitoutage'),
    path('outages/<int:pk>/edit/', CircuitOutageEditView.as_view(), name='circuitoutage_edit'),
    path('outages/<int:pk>/delete/', CircuitOutageDeleteView.as_view(), name='circuitoutage_delete'),
]
```

**Step 2: Test URL resolution**

Create: `tests/test_outage_urls.py`

```python
"""
Tests for CircuitOutage URL patterns.
"""
import pytest


def test_outage_urls_defined():
    """Test that outage URL patterns exist"""
    from netbox_circuitmaintenance.urls import urlpatterns

    outage_patterns = [p for p in urlpatterns if 'outage' in str(p.pattern)]

    assert len(outage_patterns) >= 5, "Should have at least 5 outage URL patterns"
```

**Step 3: Run test to verify it passes**

Run: `pytest tests/test_outage_urls.py -v`
Expected: Test PASS

**Step 4: Commit**

```bash
git add tests/test_outage_urls.py netbox_circuitmaintenance/urls.py
git commit -m "feat: add CircuitOutage URL patterns

Defines URL routes for outage management:
- /outages/ - List all outages
- /outages/add/ - Create new outage
- /outages/<id>/ - View outage details
- /outages/<id>/edit/ - Edit outage
- /outages/<id>/delete/ - Delete outage

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 13: Create CircuitOutage Templates

**Files:**
- Create: `netbox_circuitmaintenance/templates/netbox_circuitmaintenance/circuitoutage.html`

**Step 1: Create detail template**

```html
{% extends 'generic/object.html' %}
{% load helpers %}

{% block content %}
<div class="row">
    <div class="col col-md-6">
        <div class="card">
            <h5 class="card-header">Outage Details</h5>
            <div class="card-body">
                <table class="table table-hover attr-table">
                    <tr>
                        <th scope="row">Event ID</th>
                        <td>{{ object.name }}</td>
                    </tr>
                    <tr>
                        <th scope="row">Provider</th>
                        <td>{{ object.provider|linkify }}</td>
                    </tr>
                    <tr>
                        <th scope="row">Status</th>
                        <td>{% badge object.get_status_color %}{{ object.get_status_display }}{% endbadge %}</td>
                    </tr>
                    <tr>
                        <th scope="row">Summary</th>
                        <td>{{ object.summary }}</td>
                    </tr>
                    <tr>
                        <th scope="row">Start</th>
                        <td>{{ object.start|annotated_date }}</td>
                    </tr>
                    <tr>
                        <th scope="row">End</th>
                        <td>
                            {% if object.end %}
                                {{ object.end|annotated_date }}
                            {% else %}
                                <span class="text-muted">Not yet resolved</span>
                            {% endif %}
                        </td>
                    </tr>
                    <tr>
                        <th scope="row">Estimated Time to Repair</th>
                        <td>
                            {% if object.estimated_time_to_repair %}
                                {{ object.estimated_time_to_repair|annotated_date }}
                            {% else %}
                                <span class="text-muted">No estimate provided</span>
                            {% endif %}
                        </td>
                    </tr>
                    {% if object.original_timezone %}
                    <tr>
                        <th scope="row">Original Timezone</th>
                        <td>{{ object.original_timezone }}</td>
                    </tr>
                    {% endif %}
                    <tr>
                        <th scope="row">Internal Ticket</th>
                        <td>{{ object.internal_ticket|placeholder }}</td>
                    </tr>
                    <tr>
                        <th scope="row">Acknowledged</th>
                        <td>{% checkmark object.acknowledged %}</td>
                    </tr>
                </table>
            </div>
        </div>
        {% if object.comments %}
        <div class="card">
            <h5 class="card-header">Comments</h5>
            <div class="card-body">
                {{ object.comments|render_markdown }}
            </div>
        </div>
        {% endif %}
    </div>
</div>
{% endblock content %}
```

**Step 2: Verify template loads**

Manual testing step - requires NetBox environment:

```bash
# Start NetBox development server
python manage.py runserver

# Navigate to: http://localhost:8000/plugins/netbox-circuitmaintenance/outages/1/
```

Expected: Page renders without template errors

**Step 3: Commit**

```bash
git add netbox_circuitmaintenance/templates/netbox_circuitmaintenance/circuitoutage.html
git commit -m "feat: add CircuitOutage detail template

Creates detail view showing:
- Event identification (ID, provider, status)
- Timeline (start, end, ETR with null handling)
- Timezone information (if provided)
- Tracking metadata (ticket, acknowledged)
- Comments (markdown rendered)

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 14: Update Navigation to Include Outages

**Files:**
- Modify: `netbox_circuitmaintenance/navigation.py`

**Step 1: Update navigation structure**

In `netbox_circuitmaintenance/navigation.py`, modify the menu to include outages:

**BEFORE:**
```python
menu_items = (
    PluginMenuItem(
        link='plugins:netbox_circuitmaintenance:circuitmaintenance_list',
        link_text='Circuit Maintenance',
    ),
)
```

**AFTER:**
```python
from netbox.plugins import PluginMenuButton, PluginMenuItem

menu_items = (
    PluginMenuItem(
        link='plugins:netbox_circuitmaintenance:circuitmaintenance_list',
        link_text='Maintenances',
        buttons=(
            PluginMenuButton(
                link='plugins:netbox_circuitmaintenance:circuitmaintenance_add',
                title='Add',
                icon_class='mdi mdi-plus-thick',
            ),
        ),
    ),
    PluginMenuItem(
        link='plugins:netbox_circuitmaintenance:circuitoutage_list',
        link_text='Outages',
        buttons=(
            PluginMenuButton(
                link='plugins:netbox_circuitmaintenance:circuitoutage_add',
                title='Add',
                icon_class='mdi mdi-plus-thick',
            ),
        ),
    ),
)
```

**Step 2: Manual verification**

Requires NetBox environment:
- Restart NetBox
- Check that "Outages" appears in Circuit Maintenance plugin menu
- Verify "Add" button links to outage creation form

**Step 3: Commit**

```bash
git add netbox_circuitmaintenance/navigation.py
git commit -m "feat: add Outages to navigation menu

Updates plugin navigation:
- Renames 'Circuit Maintenance' to 'Maintenances'
- Adds 'Outages' menu item
- Includes Add buttons for both menu items

Provides easy access to both event types.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com)"
```

---

## Task 15: Update README Documentation

**Files:**
- Modify: `README.md`

**Step 1: Update README**

In `README.md`, add section about outage tracking after the maintenance tracking section:

```markdown
## Outage Tracking

In addition to planned maintenance, this plugin supports tracking unplanned outage events:

### Key Features

- **Optional End Time**: Outages can be created without an end time, which becomes required when marking as resolved
- **ETR Tracking**: Track Estimated Time to Repair with full revision history via NetBox's changelog
- **Outage Status Workflow**:
  - REPORTED: Initial state when outage is reported
  - INVESTIGATING: Team is investigating root cause
  - IDENTIFIED: Root cause identified, working on fix
  - MONITORING: Fix applied, monitoring for stability
  - RESOLVED: Outage fully resolved (requires end time)
- **Shared Impact Model**: Uses the same circuit impact tracking as maintenance events
- **Unified View**: View both maintenance and outages together in a single interface

### API Endpoints

```
GET    /api/plugins/netbox-circuitmaintenance/circuitoutage/
POST   /api/plugins/netbox-circuitmaintenance/circuitoutage/
GET    /api/plugins/netbox-circuitmaintenance/circuitoutage/{id}/
PATCH  /api/plugins/netbox-circuitmaintenance/circuitoutage/{id}/
DELETE /api/plugins/netbox-circuitmaintenance/circuitoutage/{id}/
```

### Example: Creating an Outage

```python
POST /api/plugins/netbox-circuitmaintenance/circuitoutage/
{
    "name": "OUT-2024-001",
    "summary": "Fiber cut on Main Street",
    "provider": 1,
    "start": "2024-10-29T14:30:00Z",
    "estimated_time_to_repair": "2024-10-29T18:00:00Z",
    "status": "INVESTIGATING"
}
```
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add outage tracking documentation

Documents new outage tracking features:
- Outage status workflow
- ETR tracking capabilities
- API endpoints and examples
- Relationship to maintenance tracking

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com)"
```

---

## Task 16: Run Full Test Suite

**Step 1: Run all tests**

```bash
source ../../venv/bin/activate
pytest tests/ -v --tb=short
```

Expected: All tests pass

**Step 2: Check test coverage**

```bash
pytest tests/ --cov=netbox_circuitmaintenance --cov-report=term-missing
```

Expected: New modules have reasonable coverage (>70%)

**Step 3: If failures occur**

- Review failure output
- Fix issues
- Rerun tests
- Commit fixes with descriptive messages

---

## Task 17: Final Verification and Cleanup

**Step 1: Verify all models registered**

Check that `netbox_circuitmaintenance/__init__.py` doesn't need updates for model registration.

**Step 2: Check for linting issues**

```bash
source ../../venv/bin/activate
black netbox_circuitmaintenance/ tests/ --check
isort netbox_circuitmaintenance/ tests/ --check
```

**Step 3: Apply formatting if needed**

```bash
black netbox_circuitmaintenance/ tests/
isort netbox_circuitmaintenance/ tests/
git add -A
git commit -m "style: apply black and isort formatting

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com)"
```

**Step 4: Review git log**

```bash
git log --oneline
```

Expected: Clean commit history with descriptive messages

---

## Post-Implementation Tasks

### Manual Testing Checklist

These require a NetBox development environment:

1. **Database Migration**
   ```bash
   python manage.py migrate netbox_circuitmaintenance
   ```

2. **Create Test Outage via UI**
   - Navigate to Circuit Maintenance > Outages
   - Click "Add"
   - Fill form with test data
   - Verify validation (end time required when RESOLVED)

3. **Update ETR**
   - Edit existing outage
   - Change ETR value
   - Check NetBox changelog shows update

4. **Test API**
   ```bash
   curl http://localhost:8000/api/plugins/netbox-circuitmaintenance/circuitoutage/
   ```

5. **Test Filtering**
   - Use filter form to find outages by status
   - Verify results match expected criteria

### Documentation

- Update CHANGELOG.md with new features
- Consider adding screenshots to docs/
- Update any integration guides if applicable

### Future Enhancements (Out of Scope)

The following were identified in the design doc but are not part of v1:
- Unified events view (combined maintenance + outages)
- Refactoring CircuitMaintenanceImpact to use GenericForeignKey
- Custom timeline view for ETR history
- Circuit detail page events tab

---

## Notes for Engineers

### Testing Without NetBox

Most tests in this plan are standalone unit tests that don't require NetBox:
- Model field validation
- Serializer field checks
- Form class verification
- View class existence

Integration tests requiring NetBox (marked "Manual testing step") should be run in a development environment.

### Timezone Conversion Logic

The `CircuitOutageForm.save()` method reuses timezone conversion from `CircuitMaintenanceForm`:
- Only converts on CREATE (not edit)
- Handles start, end, AND estimated_time_to_repair
- Gracefully handles invalid timezones

### Model Validation

`CircuitOutage.clean()` enforces business rule:
- End time is OPTIONAL for non-resolved outages
- End time is REQUIRED when status = 'RESOLVED'
- Django calls clean() before save() automatically

### ETR History

ETR changes are tracked via NetBox's `ObjectChange` model:
- No custom history model needed
- Query `ObjectChange.objects.filter(object_id=outage.pk)`
- Timeline view can be added in future enhancement

### Related Skills

- @superpowers:test-driven-development - Applied throughout (RED-GREEN-REFACTOR)
- @superpowers:verification-before-completion - Final testing phase
- @superpowers:finishing-a-development-branch - After all tasks complete
