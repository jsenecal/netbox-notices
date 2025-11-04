# Generic Object Impact Tracking Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform the vendor_notification plugin from circuit-specific to supporting maintenance/outage tracking for any configurable NetBox object type using Django's ContentTypes framework.

**Architecture:** Replace direct ForeignKey relationships with GenericForeignKey, add plugin configuration for allowed object types, rename all models to remove "Circuit" prefix, follow NetBox's Service/VLANGroup form patterns with HTMXSelect.

**Tech Stack:** Django 5.1+, NetBox 4.4+, Django ContentTypes framework, pytest, pytest-django

---

## Task 1: Create Constants and Utilities

**Files:**
- Create: `vendor_notification/constants.py`
- Create: `vendor_notification/utils.py`

**Step 1: Write test for get_allowed_content_types utility**

```python
# tests/test_configuration.py
from django.test import TestCase, override_settings
from vendor_notification.utils import get_allowed_content_types
from vendor_notification.constants import DEFAULT_ALLOWED_CONTENT_TYPES


class TestPluginConfiguration(TestCase):
    """Test plugin configuration and allowed content types"""

    def test_default_allowed_types(self):
        """Test default allowed_content_types from constants"""
        allowed = get_allowed_content_types()
        self.assertIn('circuits.Circuit', allowed)
        self.assertIn('dcim.PowerFeed', allowed)
        self.assertIn('dcim.Site', allowed)
        self.assertEqual(allowed, DEFAULT_ALLOWED_CONTENT_TYPES)

    @override_settings(
        PLUGINS_CONFIG={
            'vendor_notification': {
                'allowed_content_types': ['dcim.Device', 'virtualization.VirtualMachine']
            }
        }
    )
    def test_custom_allowed_types(self):
        """Test custom configuration overrides defaults"""
        allowed = get_allowed_content_types()
        self.assertEqual(len(allowed), 2)
        self.assertIn('dcim.Device', allowed)
        self.assertIn('virtualization.VirtualMachine', allowed)
        self.assertNotIn('circuits.Circuit', allowed)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_configuration.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'vendor_notification.utils'"

**Step 3: Create constants.py**

```python
# vendor_notification/constants.py
"""
Constants for vendor notification plugin configuration
"""

# Default allowed content types for impact linking
DEFAULT_ALLOWED_CONTENT_TYPES = [
    'circuits.Circuit',
    'dcim.PowerFeed',
    'dcim.Site',
]
```

**Step 4: Create utils.py**

```python
# vendor_notification/utils.py
"""
Utility functions for vendor notification plugin
"""
from django.conf import settings
from .constants import DEFAULT_ALLOWED_CONTENT_TYPES


def get_allowed_content_types():
    """
    Get list of allowed content types from plugin config.

    Returns list from PLUGINS_CONFIG['vendor_notification']['allowed_content_types']
    or DEFAULT_ALLOWED_CONTENT_TYPES if not configured.
    """
    return settings.PLUGINS_CONFIG.get('vendor_notification', {}).get(
        'allowed_content_types',
        DEFAULT_ALLOWED_CONTENT_TYPES
    )
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/test_configuration.py -v`
Expected: PASS (2 tests)

**Step 6: Commit**

```bash
git add vendor_notification/constants.py vendor_notification/utils.py tests/test_configuration.py
git commit -m "feat: add plugin configuration for allowed content types"
```

---

## Task 2: Update Plugin Config

**Files:**
- Modify: `vendor_notification/__init__.py:11-20`

**Step 1: Update __init__.py to include default_settings**

```python
# vendor_notification/__init__.py (modify lines 11-20)
from netbox.plugins import PluginConfig
from .constants import DEFAULT_ALLOWED_CONTENT_TYPES


class VendorNotificationConfig(PluginConfig):
    author = __author__
    author_email = __email__
    name = "vendor_notification"
    verbose_name = "NetBox Vendor Notification Plugin"
    description = "Track maintenance and outage events across various NetBox models"
    version = __version__
    min_version = "4.4.0"
    base_url = "vendor-notification"

    default_settings = {
        'allowed_content_types': DEFAULT_ALLOWED_CONTENT_TYPES
    }

    def ready(self):
        super().ready()
        from . import widgets


config = VendorNotificationConfig
```

**Step 2: Run configuration test to verify**

Run: `pytest tests/test_configuration.py -v`
Expected: PASS (2 tests)

**Step 3: Commit**

```bash
git add vendor_notification/__init__.py
git commit -m "feat: add default_settings to plugin config"
```

---

## Task 3: Rename Choice Classes

**Files:**
- Modify: `vendor_notification/models.py:159-205`

**Step 1: Rename choice classes (remove Circuit prefix)**

```python
# vendor_notification/models.py (lines 159-205)

class MaintenanceTypeChoices(ChoiceSet):
    """Valid maintenance status choices from BCOP standard"""

    key = "DocTypeChoices.Maintenance"

    CHOICES = [
        ("TENTATIVE", "Tentative", "yellow"),
        ("CONFIRMED", "Confirmed", "green"),
        ("CANCELLED", "Cancelled", "blue"),
        ("IN-PROCESS", "In-Progress", "orange"),
        ("COMPLETED", "Completed", "indigo"),
        ("RE-SCHEDULED", "Rescheduled", "green"),
        ("UNKNOWN", "Unknown", "blue"),
    ]


class ImpactTypeChoices(ChoiceSet):
    """Valid impact level choices from BCOP standard"""

    key = "DocTypeChoices.Impact"

    CHOICES = [
        ("NO-IMPACT", "No-Impact", "green"),
        ("REDUCED-REDUNDANCY", "Reduced Redundancy", "yellow"),
        ("DEGRADED", "Degraded", "orange"),
        ("OUTAGE", "Outage", "red"),
    ]


class OutageStatusChoices(ChoiceSet):
    """Status choices for unplanned outage events"""

    key = "Outage.Status"

    CHOICES = [
        ("REPORTED", "Reported", "red"),
        ("INVESTIGATING", "Investigating", "orange"),
        ("IDENTIFIED", "Identified", "yellow"),
        ("MONITORING", "Monitoring", "blue"),
        ("RESOLVED", "Resolved", "green"),
    ]
```

**Step 2: Commit**

```bash
git add vendor_notification/models.py
git commit -m "refactor: rename choice classes to remove Circuit prefix"
```

---

## Task 4: Rename BaseCircuitEvent to BaseEvent

**Files:**
- Modify: `vendor_notification/models.py:207-256`

**Step 1: Rename BaseCircuitEvent class**

```python
# vendor_notification/models.py (lines 207-256)

class BaseEvent(NetBoxModel):
    """
    Abstract base class for maintenance and outage events.
    Provides common fields and relationships shared by both event types.
    """

    name = models.CharField(
        max_length=100,
        verbose_name="Event ID",
        help_text="Provider supplied event ID or ticket number",
    )

    summary = models.CharField(max_length=200, help_text="Brief summary of the event")

    provider = models.ForeignKey(
        to="circuits.provider",
        on_delete=models.CASCADE,
        related_name="%(class)s_events",  # Dynamic related name per subclass
    )

    start = models.DateTimeField(help_text="Start date and time of the event")

    original_timezone = models.CharField(
        max_length=63,
        blank=True,
        verbose_name="Original Timezone",
        help_text="Original timezone from provider notification",
    )

    internal_ticket = models.CharField(
        max_length=100,
        verbose_name="Internal Ticket #",
        help_text="Internal ticket or change reference",
        blank=True,
    )

    acknowledged = models.BooleanField(
        default=False,
        null=True,
        blank=True,
        verbose_name="Acknowledged?",
        help_text="Confirm if this event has been acknowledged",
    )

    comments = models.TextField(blank=True)

    class Meta:
        abstract = True
        ordering = ("-created",)
```

**Step 2: Commit**

```bash
git add vendor_notification/models.py
git commit -m "refactor: rename BaseCircuitEvent to BaseEvent"
```

---

## Task 5: Rename CircuitMaintenance to Maintenance

**Files:**
- Modify: `vendor_notification/models.py:258-323`

**Step 1: Write test for renamed Maintenance model**

```python
# tests/test_maintenance_model.py
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from circuits.models import Provider
from vendor_notification.models import Maintenance


class TestMaintenanceModel(TestCase):
    """Test Maintenance model basic functionality"""

    @classmethod
    def setUpTestData(cls):
        cls.provider = Provider.objects.create(
            name="Test Provider",
            slug="test-provider"
        )

    def test_create_maintenance(self):
        """Test creating a maintenance event"""
        maintenance = Maintenance.objects.create(
            name="MAINT-001",
            summary="Test maintenance",
            provider=self.provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=4),
            status="CONFIRMED"
        )

        self.assertEqual(maintenance.name, "MAINT-001")
        self.assertEqual(maintenance.status, "CONFIRMED")
        self.assertEqual(str(maintenance), "MAINT-001")

    def test_get_status_color(self):
        """Test status color helper"""
        maintenance = Maintenance.objects.create(
            name="MAINT-002",
            summary="Test",
            provider=self.provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=2),
            status="CONFIRMED"
        )

        self.assertEqual(maintenance.get_status_color(), "green")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_maintenance_model.py -v`
Expected: FAIL with "ImportError: cannot import name 'Maintenance'"

**Step 3: Rename CircuitMaintenance to Maintenance**

```python
# vendor_notification/models.py (lines 258-323)

class Maintenance(BaseEvent):
    """
    Planned maintenance events with scheduled end times.
    Inherits common fields from BaseEvent.
    """

    # Override provider to preserve backward compatibility with related_name
    provider = models.ForeignKey(
        to="circuits.provider",
        on_delete=models.CASCADE,
        related_name="maintenance",
        default=None,
    )

    end = models.DateTimeField(help_text="End date and time of the maintenance event")

    status = models.CharField(max_length=30, choices=MaintenanceTypeChoices)

    class Meta:
        ordering = ("-created",)
        verbose_name = "Maintenance"
        verbose_name_plural = "Maintenances"

    def __str__(self):
        return self.name

    def get_status_color(self):
        return MaintenanceTypeChoices.colors.get(self.status)

    def get_start_in_original_tz(self):
        """Get start time in original timezone if specified"""
        if self.original_timezone and self.start:
            try:
                tz = zoneinfo.ZoneInfo(self.original_timezone)
                return self.start.astimezone(tz)
            except (zoneinfo.ZoneInfoNotFoundError, ValueError):
                return self.start
        return self.start

    def get_end_in_original_tz(self):
        """Get end time in original timezone if specified"""
        if self.original_timezone and self.end:
            try:
                tz = zoneinfo.ZoneInfo(self.original_timezone)
                return self.end.astimezone(tz)
            except (zoneinfo.ZoneInfoNotFoundError, ValueError):
                return self.end
        return self.end

    def has_timezone_difference(self):
        """Check if original timezone differs from current timezone"""
        if not self.original_timezone:
            return False
        try:
            original_tz = zoneinfo.ZoneInfo(self.original_timezone)
            current_tz = timezone.get_current_timezone()
            return str(original_tz) != str(current_tz)
        except (zoneinfo.ZoneInfoNotFoundError, ValueError):
            return False

    def get_absolute_url(self):
        return reverse(
            "plugins:vendor_notification:maintenance", args=[self.pk]
        )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_maintenance_model.py -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add vendor_notification/models.py tests/test_maintenance_model.py
git commit -m "refactor: rename CircuitMaintenance to Maintenance"
```

---

## Task 6: Rename CircuitOutage to Outage

**Files:**
- Modify: `vendor_notification/models.py:325-369`

**Step 1: Write test for renamed Outage model**

```python
# tests/test_outage_model.py
from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError
from circuits.models import Provider
from vendor_notification.models import Outage


class TestOutageModel(TestCase):
    """Test Outage model basic functionality"""

    @classmethod
    def setUpTestData(cls):
        cls.provider = Provider.objects.create(
            name="Test Provider",
            slug="test-provider"
        )

    def test_create_outage(self):
        """Test creating an outage event"""
        outage = Outage.objects.create(
            name="OUT-001",
            summary="Test outage",
            provider=self.provider,
            start=timezone.now(),
            status="REPORTED"
        )

        self.assertEqual(outage.name, "OUT-001")
        self.assertEqual(outage.status, "REPORTED")
        self.assertIsNone(outage.end)

    def test_validation_resolved_requires_end_time(self):
        """Test that RESOLVED status requires end time"""
        outage = Outage(
            name="OUT-002",
            summary="Test",
            provider=self.provider,
            start=timezone.now(),
            status="RESOLVED"
            # Missing end time
        )

        with self.assertRaises(ValidationError) as cm:
            outage.full_clean()

        self.assertIn('end', cm.exception.message_dict)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_outage_model.py -v`
Expected: FAIL with "ImportError: cannot import name 'Outage'"

**Step 3: Rename CircuitOutage to Outage**

```python
# vendor_notification/models.py (lines 325-369)

class Outage(BaseEvent):
    """
    Unplanned outage events with optional end times and ETR tracking.
    Inherits common fields from BaseEvent.
    """

    end = models.DateTimeField(
        null=True,
        blank=True,
        help_text="End date and time of the outage (required when resolved)",
    )

    estimated_time_to_repair = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Estimated Time to Repair",
        help_text="Current estimate for when service will be restored",
    )

    status = models.CharField(max_length=30, choices=OutageStatusChoices)

    class Meta:
        verbose_name = "Outage"
        verbose_name_plural = "Outages"
        ordering = ("-created",)

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        # Validation: end time required when status = RESOLVED
        if self.status == "RESOLVED" and not self.end:
            raise ValidationError(
                {"end": "End time is required when marking outage as resolved"}
            )

    def get_status_color(self):
        return OutageStatusChoices.colors.get(self.status)

    def get_absolute_url(self):
        return reverse(
            "plugins:vendor_notification:outage", args=[self.pk]
        )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_outage_model.py -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add vendor_notification/models.py tests/test_outage_model.py
git commit -m "refactor: rename CircuitOutage to Outage"
```

---

## Task 7: Create New Impact Model with GenericForeignKey

**Files:**
- Modify: `vendor_notification/models.py:371-420` (replace CircuitMaintenanceImpact)

**Step 1: Write tests for Impact model with generic relationships**

```python
# tests/test_impact_model.py
from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.models import ContentType
from datetime import timedelta
from circuits.models import Provider, Circuit, CircuitType
from dcim.models import Site
from vendor_notification.models import Maintenance, Outage, Impact


class TestImpactModel(TestCase):
    """Test Impact model with generic foreign keys"""

    @classmethod
    def setUpTestData(cls):
        cls.provider = Provider.objects.create(
            name="Test Provider",
            slug="test-provider"
        )
        cls.circuit_type = CircuitType.objects.create(
            name="Test Circuit Type",
            slug="test-circuit-type"
        )
        cls.circuit = Circuit.objects.create(
            cid="TEST-001",
            provider=cls.provider,
            type=cls.circuit_type
        )
        cls.site = Site.objects.create(
            name="Test Site",
            slug="test-site"
        )
        cls.maintenance = Maintenance.objects.create(
            name="MAINT-001",
            summary="Test maintenance",
            provider=cls.provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=4),
            status="CONFIRMED"
        )

    def test_impact_with_circuit_target(self):
        """Test linking maintenance to circuit"""
        impact = Impact.objects.create(
            event=self.maintenance,
            target=self.circuit,
            impact="OUTAGE"
        )

        self.assertEqual(impact.target, self.circuit)
        self.assertEqual(impact.event, self.maintenance)
        self.assertEqual(impact.target_content_type.model, 'circuit')
        self.assertEqual(impact.event_content_type.model, 'maintenance')

    def test_impact_with_site_target(self):
        """Test linking maintenance to site"""
        impact = Impact.objects.create(
            event=self.maintenance,
            target=self.site,
            impact="DEGRADED"
        )

        self.assertEqual(impact.target, self.site)
        self.assertEqual(impact.target_content_type.model, 'site')

    def test_impact_with_outage_event(self):
        """Test linking outage event to circuit"""
        outage = Outage.objects.create(
            name="OUT-001",
            summary="Test outage",
            provider=self.provider,
            start=timezone.now(),
            status="REPORTED"
        )

        impact = Impact.objects.create(
            event=outage,
            target=self.circuit,
            impact="OUTAGE"
        )

        self.assertEqual(impact.event, outage)
        self.assertEqual(impact.event_content_type.model, 'outage')

    def test_validation_completed_event(self):
        """Test that impacts cannot be created for completed events"""
        completed_maintenance = Maintenance.objects.create(
            name="MAINT-DONE",
            summary="Completed",
            provider=self.provider,
            start=timezone.now() - timedelta(hours=4),
            end=timezone.now() - timedelta(hours=1),
            status="COMPLETED"
        )

        impact = Impact(
            event=completed_maintenance,
            target=self.circuit,
            impact="OUTAGE"
        )

        with self.assertRaises(ValidationError) as cm:
            impact.full_clean()

        self.assertIn("cannot alter an impact", str(cm.exception))

    def test_unique_constraint(self):
        """Test unique constraint on event+target combination"""
        Impact.objects.create(
            event=self.maintenance,
            target=self.circuit,
            impact="OUTAGE"
        )

        # Try to create duplicate
        with self.assertRaises(Exception):  # IntegrityError
            Impact.objects.create(
                event=self.maintenance,
                target=self.circuit,
                impact="DEGRADED"  # Different impact level, same event+target
            )
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_impact_model.py -v`
Expected: FAIL with "ImportError: cannot import name 'Impact'"

**Step 3: Replace CircuitMaintenanceImpact with new Impact model**

```python
# vendor_notification/models.py (replace lines 371-420)

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class Impact(NetBoxModel):
    """
    Links a maintenance or outage event to an affected NetBox object.
    Uses GenericForeignKey to support any configured object type.
    """

    # Link to event (Maintenance or Outage)
    event_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name='impacts_as_event',
        limit_choices_to=models.Q(
            app_label='vendor_notification',
            model__in=['maintenance', 'outage']
        )
    )
    event_object_id = models.PositiveIntegerField()
    event = GenericForeignKey('event_content_type', 'event_object_id')

    # Link to target NetBox object (Circuit, Device, Site, etc.)
    target_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name='impacts_as_target'
    )
    target_object_id = models.PositiveIntegerField()
    target = GenericForeignKey('target_content_type', 'target_object_id')

    # Impact level
    impact = models.CharField(
        max_length=30,
        choices=ImpactTypeChoices,
        null=True,
        blank=True,
    )

    class Meta:
        unique_together = [
            ('event_content_type', 'event_object_id',
             'target_content_type', 'target_object_id')
        ]
        ordering = ('impact',)
        verbose_name = "Impact"
        verbose_name_plural = "Impacts"

    def __str__(self):
        event_name = str(self.event) if self.event else "Unknown"
        target_name = str(self.target) if self.target else "Unknown"
        return f"{event_name} - {target_name}"

    def get_absolute_url(self):
        # Link to the event detail page
        if self.event and hasattr(self.event, 'get_absolute_url'):
            return self.event.get_absolute_url()
        return reverse('plugins:vendor_notification:impact', args=[self.pk])

    def get_impact_color(self):
        return ImpactTypeChoices.colors.get(self.impact)

    def clean(self):
        super().clean()
        from .utils import get_allowed_content_types

        allowed_types = get_allowed_content_types()

        # Validate target is an allowed type
        if self.target_content_type:
            app_label = self.target_content_type.app_label
            model = self.target_content_type.model
            type_string = f"{app_label}.{model}"

            # Case-insensitive comparison
            allowed_types_lower = [t.lower() for t in allowed_types]
            if type_string.lower() not in allowed_types_lower:
                raise ValidationError({
                    'target_content_type': f"Content type '{type_string}' is not allowed. "
                                          f"Allowed types: {', '.join(allowed_types)}"
                })

        # Validate event is Maintenance or Outage
        if self.event_content_type:
            if self.event_content_type.app_label != 'vendor_notification':
                raise ValidationError({
                    'event_content_type': 'Event must be a Maintenance or Outage'
                })
            if self.event_content_type.model not in ['maintenance', 'outage']:
                raise ValidationError({
                    'event_content_type': 'Event must be a Maintenance or Outage'
                })

        # Validate event status - cannot modify impacts on completed events
        if hasattr(self.event, 'status'):
            if self.event.status in ['COMPLETED', 'CANCELLED', 'RESOLVED']:
                raise ValidationError(
                    "You cannot alter an impact once the event has completed."
                )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_impact_model.py -v`
Expected: PASS (5 tests)

**Step 5: Commit**

```bash
git add vendor_notification/models.py tests/test_impact_model.py
git commit -m "feat: create Impact model with GenericForeignKey support"
```

---

## Task 8: Test Impact Validation with Disallowed Content Types

**Files:**
- Modify: `tests/test_impact_model.py` (add test)

**Step 1: Add test for disallowed content type validation**

```python
# tests/test_impact_model.py (add at end of TestImpactModel class)

    @override_settings(
        PLUGINS_CONFIG={
            'vendor_notification': {
                'allowed_content_types': ['circuits.Circuit']  # Only circuits allowed
            }
        }
    )
    def test_validation_disallowed_content_type(self):
        """Test that non-configured content types are rejected"""
        # Site is not in allowed list (only Circuit is)
        impact = Impact(
            event=self.maintenance,
            target=self.site,
            impact="OUTAGE"
        )

        with self.assertRaises(ValidationError) as cm:
            impact.full_clean()

        self.assertIn('target_content_type', cm.exception.message_dict)
        self.assertIn('not allowed', str(cm.exception))
```

**Step 2: Add import at top of file**

```python
# tests/test_impact_model.py (add to imports)
from django.test import TestCase, override_settings
```

**Step 3: Run test to verify it passes**

Run: `pytest tests/test_impact_model.py::TestImpactModel::test_validation_disallowed_content_type -v`
Expected: PASS

**Step 4: Commit**

```bash
git add tests/test_impact_model.py
git commit -m "test: add validation test for disallowed content types"
```

---

## Task 9: Rename CircuitMaintenanceNotifications to EventNotification

**Files:**
- Modify: `vendor_notification/models.py:421-454`

**Step 1: Replace CircuitMaintenanceNotifications with EventNotification**

```python
# vendor_notification/models.py (replace lines 421-454)

class EventNotification(NetBoxModel):
    """
    Stores raw email notifications for maintenance or outage events.
    Uses GenericForeignKey to link to either event type.
    """

    # Link to event (Maintenance or Outage)
    event_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to=models.Q(
            app_label='vendor_notification',
            model__in=['maintenance', 'outage']
        )
    )
    event_object_id = models.PositiveIntegerField()
    event = GenericForeignKey('event_content_type', 'event_object_id')

    email = models.BinaryField()
    email_body = models.TextField(verbose_name="Email Body")
    subject = models.CharField(max_length=100)
    email_from = models.EmailField(verbose_name="Email From")
    email_received = models.DateTimeField(verbose_name="Email Received")  # Fixed typo

    class Meta:
        ordering = ("email_received",)
        verbose_name = "Event Notification"
        verbose_name_plural = "Event Notifications"

    def __str__(self):
        return self.subject

    def get_absolute_url(self):
        return reverse(
            "plugins:vendor_notification:eventnotification", args=[self.pk]
        )
```

**Step 2: Commit**

```bash
git add vendor_notification/models.py
git commit -m "refactor: rename CircuitMaintenanceNotifications to EventNotification with GenericForeignKey"
```

---

## Task 10: Delete Old Migrations and Create Fresh Migration

**Files:**
- Delete: All files in `vendor_notification/migrations/` except `__init__.py`
- Create: New migration via makemigrations

**Step 1: Delete old migration files**

```bash
cd vendor_notification/migrations/
ls -1 | grep -v __init__.py | xargs rm -f
cd ../..
```

**Step 2: Verify only __init__.py remains**

Run: `ls -la vendor_notification/migrations/`
Expected: Only `__init__.py` present

**Step 3: Create fresh initial migration**

Run: `python /opt/netbox/netbox/manage.py makemigrations vendor_notification`
Expected: "Migrations for 'vendor_notification': vendor_notification/migrations/0001_initial.py"

**Step 4: Review generated migration**

Run: `cat vendor_notification/migrations/0001_initial.py | head -50`
Expected: Should see Maintenance, Outage, Impact, EventNotification models

**Step 5: Commit**

```bash
git add vendor_notification/migrations/
git commit -m "feat: create fresh initial migration with generic models"
```

---

## Task 11: Update Forms - Create ImpactForm

**Files:**
- Modify: `vendor_notification/forms.py` (replace CircuitMaintenanceImpactForm)

**Step 1: Write test for ImpactForm**

```python
# tests/test_impact_forms.py
from django.test import TestCase
from django.contrib.contenttypes.models import ContentType
from circuits.models import Provider, Circuit, CircuitType
from vendor_notification.models import Maintenance
from vendor_notification.forms import ImpactForm
from django.utils import timezone
from datetime import timedelta


class TestImpactForm(TestCase):
    """Test ImpactForm with GenericForeignKey support"""

    @classmethod
    def setUpTestData(cls):
        cls.provider = Provider.objects.create(
            name="Test Provider",
            slug="test-provider"
        )
        cls.circuit_type = CircuitType.objects.create(
            name="Test Type",
            slug="test-type"
        )
        cls.circuit = Circuit.objects.create(
            cid="TEST-001",
            provider=cls.provider,
            type=cls.circuit_type
        )
        cls.maintenance = Maintenance.objects.create(
            name="MAINT-001",
            summary="Test",
            provider=cls.provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=4),
            status="CONFIRMED"
        )
        cls.maintenance_ct = ContentType.objects.get_for_model(Maintenance)
        cls.circuit_ct = ContentType.objects.get_for_model(Circuit)

    def test_form_has_required_fields(self):
        """Test form has all required fields"""
        form = ImpactForm()

        self.assertIn('event_content_type', form.fields)
        self.assertIn('event', form.fields)
        self.assertIn('target_content_type', form.fields)
        self.assertIn('target', form.fields)
        self.assertIn('impact', form.fields)

    def test_form_target_content_type_limited_to_allowed(self):
        """Test target_content_type choices limited by config"""
        form = ImpactForm()

        # Get queryset IDs
        allowed_ids = list(form.fields['target_content_type'].queryset.values_list('id', flat=True))

        # Circuit should be in allowed list (from DEFAULT_ALLOWED_CONTENT_TYPES)
        self.assertIn(self.circuit_ct.id, allowed_ids)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_impact_forms.py -v`
Expected: FAIL with "ImportError: cannot import name 'ImpactForm'"

**Step 3: Create ImpactForm following NetBox patterns**

```python
# vendor_notification/forms.py (replace CircuitMaintenanceImpactForm)

from django import forms
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from netbox.forms import NetBoxModelForm
from utilities.forms.fields import DynamicModelChoiceField, ContentTypeChoiceField
from utilities.forms.widgets import HTMXSelect
from utilities.forms.utils import get_field_value
from .models import Maintenance, Outage, Impact
from .utils import get_allowed_content_types


class ImpactForm(NetBoxModelForm):
    """
    Form for creating/editing Impact records.
    Uses HTMXSelect to dynamically update field choices based on ContentType selection.
    """

    # Event selection (Maintenance or Outage)
    event_content_type = ContentTypeChoiceField(
        queryset=ContentType.objects.filter(
            app_label='vendor_notification',
            model__in=['maintenance', 'outage']
        ),
        widget=HTMXSelect(),
        required=True,
        label='Event Type'
    )
    event = DynamicModelChoiceField(
        label='Event',
        queryset=Maintenance.objects.none(),
        required=True,
        disabled=True,
        selector=True
    )

    # Target object selection (Circuit, Device, Site, etc.)
    target_content_type = ContentTypeChoiceField(
        label='Target Object Type',
        widget=HTMXSelect(),
        required=True
    )
    target = DynamicModelChoiceField(
        label='Target Object',
        queryset=None,
        required=True,
        disabled=True,
        selector=True
    )

    class Meta:
        model = Impact
        fields = ['event_content_type', 'target_content_type', 'impact', 'tags']

    def __init__(self, *args, **kwargs):
        initial = kwargs.get('initial', {}).copy()

        # Populate from instance when editing
        if (instance := kwargs.get('instance')) and instance.pk:
            if instance.event:
                initial['event'] = instance.event
            if instance.target:
                initial['target'] = instance.target

        kwargs['initial'] = initial
        super().__init__(*args, **kwargs)

        # Limit target_content_type to allowed types from config
        allowed_types = get_allowed_content_types()
        allowed_ct_ids = []
        for type_string in allowed_types:
            try:
                app_label, model = type_string.lower().split('.')
                ct = ContentType.objects.get(app_label=app_label, model=model)
                allowed_ct_ids.append(ct.id)
            except (ValueError, ContentType.DoesNotExist):
                pass

        self.fields['target_content_type'].queryset = ContentType.objects.filter(
            id__in=allowed_ct_ids
        )

        # Update event field based on selected event_content_type
        if event_ct_id := get_field_value(self, 'event_content_type'):
            try:
                event_ct = ContentType.objects.get(pk=event_ct_id)
                model = event_ct.model_class()
                self.fields['event'].queryset = model.objects.all()
                self.fields['event'].widget.attrs['selector'] = model._meta.label_lower
                self.fields['event'].disabled = False
                self.fields['event'].label = model._meta.verbose_name.title()
            except ObjectDoesNotExist:
                pass

        # Update target field based on selected target_content_type
        if target_ct_id := get_field_value(self, 'target_content_type'):
            try:
                target_ct = ContentType.objects.get(pk=target_ct_id)
                model = target_ct.model_class()
                self.fields['target'].queryset = model.objects.all()
                self.fields['target'].widget.attrs['selector'] = model._meta.label_lower
                self.fields['target'].disabled = False
                self.fields['target'].label = model._meta.verbose_name.title()
            except ObjectDoesNotExist:
                pass

    def clean(self):
        super().clean()
        # Assign generic relationships
        self.instance.event = self.cleaned_data.get('event')
        self.instance.target = self.cleaned_data.get('target')
        return self.cleaned_data
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_impact_forms.py -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add vendor_notification/forms.py tests/test_impact_forms.py
git commit -m "feat: create ImpactForm with HTMXSelect support"
```

---

## Task 12: Update Remaining Forms for Renamed Models

**Files:**
- Modify: `vendor_notification/forms.py` (update all form class names)

**Step 1: Update MaintenanceForm (was CircuitMaintenanceForm)**

Find and replace class names in forms.py:
- `CircuitMaintenanceForm` → `MaintenanceForm` (update Meta.model too)
- `CircuitMaintenanceFilterForm` → `MaintenanceFilterForm`
- `CircuitMaintenanceBulkEditForm` → `MaintenanceBulkEditForm`
- `CircuitOutageForm` → `OutageForm`
- `CircuitOutageFilterForm` → `OutageFilterForm`
- `CircuitOutageBulkEditForm` → `OutageBulkEditForm`
- `CircuitMaintenanceNotificationsForm` → `EventNotificationForm`

Also update model imports at top of file.

**Step 2: Commit**

```bash
git add vendor_notification/forms.py
git commit -m "refactor: update form classes for renamed models"
```

---

## Task 13: Update API Serializers

**Files:**
- Modify: `vendor_notification/api/serializers.py`

**Step 1: Write test for ImpactSerializer**

```python
# tests/test_impact_api.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from django.utils import timezone
from datetime import timedelta
from circuits.models import Provider, Circuit, CircuitType
from vendor_notification.models import Maintenance, Impact


User = get_user_model()


class TestImpactAPI(TestCase):
    """Test Impact API with generic foreign keys"""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='testuser',
            password='testpass'
        )
        cls.user.is_superuser = True
        cls.user.save()

        cls.provider = Provider.objects.create(
            name="API Provider",
            slug="api-provider"
        )
        cls.circuit_type = CircuitType.objects.create(
            name="API Type",
            slug="api-type"
        )
        cls.circuit = Circuit.objects.create(
            cid="API-001",
            provider=cls.provider,
            type=cls.circuit_type
        )
        cls.maintenance = Maintenance.objects.create(
            name="API-MAINT-001",
            summary="API Test",
            provider=cls.provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=3),
            status="CONFIRMED"
        )
        cls.impact = Impact.objects.create(
            event=cls.maintenance,
            target=cls.circuit,
            impact='OUTAGE'
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_list_impacts(self):
        """Test listing impacts includes nested objects"""
        response = self.client.get('/api/plugins/vendor-notification/impacts/')

        self.assertEqual(response.status_code, 200)
        self.assertGreater(response.data['count'], 0)

        # Check first result has nested objects
        result = response.data['results'][0]
        self.assertIn('event_object', result)
        self.assertIn('target_object', result)
        self.assertIn('event_content_type', result)
        self.assertIn('target_content_type', result)

    def test_retrieve_impact(self):
        """Test retrieving single impact"""
        response = self.client.get(f'/api/plugins/vendor-notification/impacts/{self.impact.id}/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['impact'], 'OUTAGE')
        self.assertIsNotNone(response.data['event_object'])
        self.assertIsNotNone(response.data['target_object'])
```

**Step 2: Run test to verify current state**

Run: `pytest tests/test_impact_api.py -v`
Expected: FAIL (API endpoints don't exist yet or serializer broken)

**Step 3: Create ImpactSerializer**

```python
# vendor_notification/api/serializers.py (add ImpactSerializer)

from rest_framework import serializers
from netbox.api.serializers import NetBoxModelSerializer
from ..models import Maintenance, Outage, Impact, EventNotification


class ImpactSerializer(NetBoxModelSerializer):
    """
    Serializer for Impact model with generic foreign key support.
    Includes nested object representations for easier API consumption.
    """

    event_content_type = serializers.CharField()
    event_object_id = serializers.IntegerField()
    target_content_type = serializers.CharField()
    target_object_id = serializers.IntegerField()

    # Include object representations
    event_object = serializers.SerializerMethodField(read_only=True)
    target_object = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Impact
        fields = [
            'id', 'url', 'display',
            'event_content_type', 'event_object_id', 'event_object',
            'target_content_type', 'target_object_id', 'target_object',
            'impact', 'created', 'last_updated', 'tags'
        ]

    def get_event_object(self, obj):
        """Return nested representation of the event"""
        if obj.event:
            return {
                'id': obj.event.id,
                'name': str(obj.event),
                'url': obj.event.get_absolute_url() if hasattr(obj.event, 'get_absolute_url') else None
            }
        return None

    def get_target_object(self, obj):
        """Return nested representation of the target"""
        if obj.target:
            return {
                'id': obj.target.id,
                'name': str(obj.target),
                'url': obj.target.get_absolute_url() if hasattr(obj.target, 'get_absolute_url') else None
            }
        return None


class MaintenanceSerializer(NetBoxModelSerializer):
    """Serializer for Maintenance with nested impacts"""
    impacts = ImpactSerializer(many=True, read_only=True, source='impacts_as_event')

    class Meta:
        model = Maintenance
        fields = [
            'id', 'url', 'display', 'name', 'summary', 'provider', 'start', 'end',
            'original_timezone', 'status', 'internal_ticket', 'acknowledged',
            'comments', 'impacts', 'created', 'last_updated', 'tags'
        ]


class OutageSerializer(NetBoxModelSerializer):
    """Serializer for Outage with nested impacts"""
    impacts = ImpactSerializer(many=True, read_only=True, source='impacts_as_event')

    class Meta:
        model = Outage
        fields = [
            'id', 'url', 'display', 'name', 'summary', 'provider', 'start', 'end',
            'estimated_time_to_repair', 'original_timezone', 'status',
            'internal_ticket', 'acknowledged', 'comments', 'impacts',
            'created', 'last_updated', 'tags'
        ]


class EventNotificationSerializer(NetBoxModelSerializer):
    """Serializer for EventNotification"""
    event_content_type = serializers.CharField()
    event_object_id = serializers.IntegerField()

    class Meta:
        model = EventNotification
        fields = [
            'id', 'url', 'display', 'event_content_type', 'event_object_id',
            'subject', 'email_from', 'email_received', 'email_body',
            'created', 'last_updated'
        ]
```

**Step 4: Update other serializer class names**

Replace in serializers.py:
- `CircuitMaintenanceSerializer` → `MaintenanceSerializer`
- `CircuitOutageSerializer` → `OutageSerializer`
- `CircuitMaintenanceNotificationsSerializer` → `EventNotificationSerializer`

**Step 5: Commit**

```bash
git add vendor_notification/api/serializers.py tests/test_impact_api.py
git commit -m "feat: create API serializers for generic models"
```

---

## Task 14: Update API Views and URLs

**Files:**
- Modify: `vendor_notification/api/views.py`
- Modify: `vendor_notification/api/urls.py`

**Step 1: Update view classes in api/views.py**

Replace viewset names:
- `CircuitMaintenanceViewSet` → `MaintenanceViewSet`
- `CircuitOutageViewSet` → `OutageViewSet`
- `CircuitMaintenanceImpactViewSet` → `ImpactViewSet`
- `CircuitMaintenanceNotificationsViewSet` → `EventNotificationViewSet`

Update queryset and serializer_class for each.

**Step 2: Update URL patterns in api/urls.py**

```python
# vendor_notification/api/urls.py

from netbox.api.routers import NetBoxRouter
from . import views

router = NetBoxRouter()
router.register('maintenances', views.MaintenanceViewSet)
router.register('outages', views.OutageViewSet)
router.register('impacts', views.ImpactViewSet)
router.register('event-notifications', views.EventNotificationViewSet)

urlpatterns = router.urls
```

**Step 3: Run API test**

Run: `pytest tests/test_impact_api.py -v`
Expected: PASS (2 tests)

**Step 4: Commit**

```bash
git add vendor_notification/api/views.py vendor_notification/api/urls.py
git commit -m "refactor: update API views and URLs for renamed models"
```

---

## Task 15: Update Tables

**Files:**
- Modify: `vendor_notification/tables.py`

**Step 1: Create ImpactTable**

```python
# vendor_notification/tables.py (replace CircuitMaintenanceImpactTable)

import django_tables2 as tables
from netbox.tables import NetBoxTable, columns
from .models import Maintenance, Outage, Impact, EventNotification


class ImpactTable(NetBoxTable):
    """Table for displaying Impact records"""

    event = tables.Column(
        accessor='event',
        linkify=True,
        verbose_name='Event'
    )
    event_type = columns.ContentTypeColumn(
        accessor='event_content_type',
        verbose_name='Event Type'
    )
    target = tables.Column(
        accessor='target',
        linkify=True,
        verbose_name='Target Object'
    )
    target_type = columns.ContentTypeColumn(
        accessor='target_content_type',
        verbose_name='Target Type'
    )
    impact = columns.ChoiceFieldColumn()

    class Meta(NetBoxTable.Meta):
        model = Impact
        fields = ('pk', 'event_type', 'event', 'target_type', 'target', 'impact', 'created', 'last_updated')
        default_columns = ('event', 'target_type', 'target', 'impact')


class MaintenanceTable(NetBoxTable):
    """Table for Maintenance events"""
    name = tables.Column(linkify=True)
    provider = tables.Column(linkify=True)
    status = columns.ChoiceFieldColumn()
    start = columns.DateTimeColumn()
    end = columns.DateTimeColumn()

    class Meta(NetBoxTable.Meta):
        model = Maintenance
        fields = ('pk', 'name', 'provider', 'summary', 'status', 'start', 'end',
                  'internal_ticket', 'acknowledged', 'created', 'last_updated')
        default_columns = ('name', 'provider', 'status', 'start', 'end')


class OutageTable(NetBoxTable):
    """Table for Outage events"""
    name = tables.Column(linkify=True)
    provider = tables.Column(linkify=True)
    status = columns.ChoiceFieldColumn()
    start = columns.DateTimeColumn()

    class Meta(NetBoxTable.Meta):
        model = Outage
        fields = ('pk', 'name', 'provider', 'summary', 'status', 'start', 'end',
                  'estimated_time_to_repair', 'internal_ticket', 'acknowledged')
        default_columns = ('name', 'provider', 'status', 'start')


class EventNotificationTable(NetBoxTable):
    """Table for Event Notifications"""
    subject = tables.Column(linkify=True)

    class Meta(NetBoxTable.Meta):
        model = EventNotification
        fields = ('pk', 'subject', 'email_from', 'email_received', 'created')
        default_columns = ('subject', 'email_from', 'email_received')
```

**Step 2: Commit**

```bash
git add vendor_notification/tables.py
git commit -m "refactor: update tables for generic models"
```

---

## Task 16: Update Filtersets

**Files:**
- Modify: `vendor_notification/filtersets.py`

**Step 1: Create ImpactFilterSet**

```python
# vendor_notification/filtersets.py (replace CircuitMaintenanceImpactFilterSet)

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
import django_filters
from netbox.filtersets import NetBoxModelFilterSet
from .models import Maintenance, Outage, Impact, EventNotification


class ImpactFilterSet(NetBoxModelFilterSet):
    """FilterSet for Impact model with ContentType filtering"""

    target_content_type = django_filters.ModelMultipleChoiceFilter(
        queryset=ContentType.objects.all(),
        label='Target Object Type',
    )
    event_content_type = django_filters.ModelMultipleChoiceFilter(
        queryset=ContentType.objects.filter(
            app_label='vendor_notification',
            model__in=['maintenance', 'outage']
        ),
        label='Event Type',
    )

    class Meta:
        model = Impact
        fields = ['id', 'impact', 'event_content_type', 'target_content_type']

    def search(self, queryset, name, value):
        """Enable search across related object names"""
        return queryset.filter(
            Q(impact__icontains=value)
        )


class MaintenanceFilterSet(NetBoxModelFilterSet):
    """FilterSet for Maintenance model"""

    class Meta:
        model = Maintenance
        fields = ['id', 'name', 'provider', 'status', 'acknowledged']

    def search(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) |
            Q(summary__icontains=value)
        )


class OutageFilterSet(NetBoxModelFilterSet):
    """FilterSet for Outage model"""

    class Meta:
        model = Outage
        fields = ['id', 'name', 'provider', 'status', 'acknowledged']

    def search(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) |
            Q(summary__icontains=value)
        )


class EventNotificationFilterSet(NetBoxModelFilterSet):
    """FilterSet for EventNotification model"""

    class Meta:
        model = EventNotification
        fields = ['id', 'subject', 'email_from']

    def search(self, queryset, name, value):
        return queryset.filter(
            Q(subject__icontains=value) |
            Q(email_body__icontains=value)
        )
```

**Step 2: Commit**

```bash
git add vendor_notification/filtersets.py
git commit -m "refactor: update filtersets for generic models"
```

---

## Task 17: Update URLs

**Files:**
- Modify: `vendor_notification/urls.py`

**Step 1: Update URL patterns**

```python
# vendor_notification/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # Maintenance URLs
    path('maintenances/', views.MaintenanceListView.as_view(), name='maintenance_list'),
    path('maintenances/add/', views.MaintenanceEditView.as_view(), name='maintenance_add'),
    path('maintenances/<int:pk>/', views.MaintenanceView.as_view(), name='maintenance'),
    path('maintenances/<int:pk>/edit/', views.MaintenanceEditView.as_view(), name='maintenance_edit'),
    path('maintenances/<int:pk>/delete/', views.MaintenanceDeleteView.as_view(), name='maintenance_delete'),

    # Outage URLs
    path('outages/', views.OutageListView.as_view(), name='outage_list'),
    path('outages/add/', views.OutageEditView.as_view(), name='outage_add'),
    path('outages/<int:pk>/', views.OutageView.as_view(), name='outage'),
    path('outages/<int:pk>/edit/', views.OutageEditView.as_view(), name='outage_edit'),
    path('outages/<int:pk>/delete/', views.OutageDeleteView.as_view(), name='outage_delete'),

    # Impact URLs
    path('impacts/', views.ImpactListView.as_view(), name='impact_list'),
    path('impacts/add/', views.ImpactEditView.as_view(), name='impact_add'),
    path('impacts/<int:pk>/', views.ImpactView.as_view(), name='impact'),
    path('impacts/<int:pk>/edit/', views.ImpactEditView.as_view(), name='impact_edit'),
    path('impacts/<int:pk>/delete/', views.ImpactDeleteView.as_view(), name='impact_delete'),

    # Notification URLs
    path('notifications/', views.EventNotificationListView.as_view(), name='eventnotification_list'),
    path('notifications/<int:pk>/', views.EventNotificationView.as_view(), name='eventnotification'),
]
```

**Step 2: Commit**

```bash
git add vendor_notification/urls.py
git commit -m "refactor: update URL patterns for renamed models"
```

---

## Task 18: Update Views

**Files:**
- Modify: `vendor_notification/views.py`

**Step 1: Update view classes and add Impact views**

Replace all view class names:
- `CircuitMaintenanceListView` → `MaintenanceListView`
- `CircuitMaintenanceView` → `MaintenanceView`
- `CircuitMaintenanceEditView` → `MaintenanceEditView`
- `CircuitMaintenanceDeleteView` → `MaintenanceDeleteView`
- `CircuitOutageListView` → `OutageListView`
- etc.

Add ImpactEditView with alter_object:

```python
# vendor_notification/views.py (add ImpactEditView)

from django.contrib.contenttypes.models import ContentType
from netbox.views import generic
from .models import Maintenance, Outage, Impact, EventNotification
from .forms import MaintenanceForm, OutageForm, ImpactForm, EventNotificationForm
from .filtersets import MaintenanceFilterSet, OutageFilterSet, ImpactFilterSet, EventNotificationFilterSet
from .tables import MaintenanceTable, OutageTable, ImpactTable, EventNotificationTable


class ImpactEditView(generic.ObjectEditView):
    queryset = Impact.objects.all()
    form = ImpactForm

    def alter_object(self, obj, request, args, kwargs):
        """
        Set event from query parameters when adding impact from event detail page.
        Example: /impacts/add/?event_type=maintenance&event_id=123
        """
        if not obj.pk:
            # Check for event parameters in query string
            event_type = request.GET.get('event_type')  # 'maintenance' or 'outage'
            event_id = request.GET.get('event_id')

            if event_type and event_id:
                try:
                    ct = ContentType.objects.get(
                        app_label='vendor_notification',
                        model=event_type
                    )
                    obj.event_content_type = ct
                    obj.event_object_id = event_id
                except ContentType.DoesNotExist:
                    pass

        return obj
```

**Step 2: Commit**

```bash
git add vendor_notification/views.py
git commit -m "refactor: update view classes for renamed models"
```

---

## Task 19: Update Navigation

**Files:**
- Modify: `vendor_notification/navigation.py`

**Step 1: Update navigation menu**

```python
# vendor_notification/navigation.py

from netbox.plugins import PluginMenuButton, PluginMenuItem, PluginMenu

menu = PluginMenu(
    label="Vendor Notifications",
    groups=(
        ("Events", (
            PluginMenuItem(
                link="plugins:vendor_notification:maintenance_list",
                link_text="Maintenances",
                buttons=(
                    PluginMenuButton(
                        link="plugins:vendor_notification:maintenance_add",
                        title="Add",
                        icon_class="mdi mdi-plus-thick",
                    ),
                ),
            ),
            PluginMenuItem(
                link="plugins:vendor_notification:outage_list",
                link_text="Outages",
                buttons=(
                    PluginMenuButton(
                        link="plugins:vendor_notification:outage_add",
                        title="Add",
                        icon_class="mdi mdi-plus-thick",
                    ),
                ),
            ),
        )),
        ("Related", (
            PluginMenuItem(
                link="plugins:vendor_notification:impact_list",
                link_text="Impacts",
            ),
            PluginMenuItem(
                link="plugins:vendor_notification:eventnotification_list",
                link_text="Notifications",
            ),
        )),
    ),
)
```

**Step 2: Commit**

```bash
git add vendor_notification/navigation.py
git commit -m "refactor: update navigation for renamed models"
```

---

## Task 20: Update Templates

**Files:**
- Rename: All template files to match new model names
- Modify: Template content to use new model names

**Step 1: Rename template files**

```bash
cd vendor_notification/templates/vendor_notification/
mv circuitmaintenance.html maintenance.html
mv circuitoutage.html outage.html
mv circuitmaintenancenotifications.html eventnotification.html
# Keep other templates, update references inside
cd ../../..
```

**Step 2: Update template variable references**

In each template file, replace:
- `circuitmaintenance` → `maintenance`
- `circuitoutage` → `outage`
- `circuitmaintenance_impact` → `impact`

**Step 3: Commit**

```bash
git add vendor_notification/templates/
git commit -m "refactor: rename and update templates for new models"
```

---

## Task 21: Update All Test Files

**Files:**
- Modify: All test files in `tests/` to use new model names

**Step 1: Update test imports and model references**

In each test file, replace:
- `from netbox_circuitmaintenance.models import CircuitMaintenance` → `from vendor_notification.models import Maintenance`
- `CircuitMaintenance` → `Maintenance`
- `CircuitOutage` → `Outage`
- etc.

**Step 2: Run all tests**

Run: `pytest tests/ -v`
Expected: All tests pass

**Step 3: Commit**

```bash
git add tests/
git commit -m "test: update all tests for renamed models"
```

---

## Task 22: Update README with Configuration Examples

**Files:**
- Modify: `README.md`

**Step 1: Add configuration section to README**

Add after installation instructions:

```markdown
## Configuration

### Allowed Content Types

By default, the plugin supports linking maintenance and outage events to:
- Circuits (`circuits.Circuit`)
- Power Feeds (`dcim.PowerFeed`)
- Sites (`dcim.Site`)

You can customize which NetBox object types are allowed in your `configuration.py`:

```python
PLUGINS_CONFIG = {
    'vendor_notification': {
        'allowed_content_types': [
            'circuits.Circuit',
            'dcim.Device',
            'dcim.PowerFeed',
            'dcim.Site',
            'virtualization.VirtualMachine',
        ]
    }
}
```

### Migration from netbox-circuitmaintenance

**There is no upgrade path from the original netbox-circuitmaintenance plugin.**

This is a complete rewrite with breaking changes. If you're migrating:
1. Backup your data
2. Uninstall the old plugin
3. Install this plugin
4. Run migrations
5. Manually re-import critical data if needed

```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add configuration examples and migration notes"
```

---

## Task 23: Run Full Test Suite

**Files:**
- N/A

**Step 1: Run all tests**

Run: `pytest tests/ -v --tb=short`
Expected: All tests pass

**Step 2: Check coverage**

Run: `pytest tests/ --cov=vendor_notification --cov-report=term-missing`
Expected: Reasonable coverage (>70%)

**Step 3: If any failures, fix and commit**

```bash
# Fix issues
git add <fixed-files>
git commit -m "fix: resolve test failures"
```

---

## Task 24: Run Code Quality Checks

**Files:**
- N/A

**Step 1: Run ruff format**

Run: `ruff format vendor_notification/ tests/`
Expected: Code formatted

**Step 2: Run ruff lint**

Run: `ruff check --fix vendor_notification/ tests/`
Expected: No lint errors

**Step 3: Commit formatting changes**

```bash
git add vendor_notification/ tests/
git commit -m "style: apply ruff formatting and linting"
```

---

## Task 25: Final Integration Test

**Files:**
- N/A

**Step 1: Run migrations in test environment**

Run: `python /opt/netbox/netbox/manage.py migrate vendor_notification`
Expected: Migration applies cleanly

**Step 2: Test in NetBox UI (manual)**

1. Start NetBox: `make runserver` (in devcontainer)
2. Navigate to Vendor Notifications menu
3. Create a Maintenance event
4. Create an Impact linking it to a Circuit
5. Verify everything displays correctly

**Step 3: Document any issues found**

If issues found, create new tasks to fix them.

---

## Verification Checklist

After completing all tasks:

- [ ] All model classes renamed (no "Circuit" prefix)
- [ ] Impact model uses GenericForeignKey for both event and target
- [ ] EventNotification uses GenericForeignKey for event
- [ ] Plugin configuration includes default_settings
- [ ] Forms use HTMXSelect for ContentType fields
- [ ] API serializers include nested object representations
- [ ] All tests pass
- [ ] Ruff formatting applied
- [ ] Fresh migration created
- [ ] README updated with configuration examples
- [ ] Navigation menu updated
- [ ] All URL patterns updated

---

## Notes

- **Testing Environment:** Tests require full NetBox environment. Use devcontainer or set DJANGO_SETTINGS_MODULE appropriately.
- **Python Path:** Use `/opt/netbox/venv/bin/python` for all Python commands.
- **Database:** Migrations should be run against test database or devcontainer.
- **Breaking Changes:** This is a complete rewrite - no backward compatibility with old plugin.
