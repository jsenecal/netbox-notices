# EventNotificationForm Object Picker Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add dynamic HTMX-based object picker to EventNotificationForm, matching the UX pattern from ImpactForm, using a shared GenericForeignKeyFormMixin.

**Architecture:** Create reusable mixin for GenericForeignKey form handling with HTMX/DynamicModelChoiceField pattern. Refactor ImpactForm to use mixin, eliminating code duplication. Enhance EventNotificationForm with same pattern plus fieldsets for better UI organization.

**Tech Stack:** Django forms, NetBox utilities (HTMXSelect, DynamicModelChoiceField, get_field_value), GenericForeignKey, HTMX

---

## Task 1: Create GenericForeignKeyFormMixin

**Files:**
- Modify: `vendor_notification/forms.py:1-24` (add mixin after imports)

**Step 1: Add mixin class with init_generic_choice method**

Add after imports, before MaintenanceForm:

```python
class GenericForeignKeyFormMixin:
    """
    Mixin for forms with GenericForeignKey fields using HTMX pattern.

    Subclasses should declare:
        generic_fk_fields = [('field_prefix', 'content_type_field', 'object_id_field')]

    Example:
        generic_fk_fields = [('event', 'event_content_type', 'event_object_id')]

    This will:
    - Create 'event_choice' DynamicModelChoiceField when event_content_type is selected
    - Extract selected object from event_choice in clean()
    - Populate event_content_type and event_object_id for model save
    """

    # Override in subclasses with list of (prefix, content_type_field, object_id_field) tuples
    generic_fk_fields = []

    def init_generic_choice(self, field_prefix, content_type_id):
        """
        Initialize a choice field based on selected content type.
        Creates DynamicModelChoiceField for selecting actual objects.

        Args:
            field_prefix: Field name prefix (e.g., 'event', 'target')
            content_type_id: Primary key of selected ContentType (may be list from HTMX)
        """
        # Handle list values from duplicate GET parameters (HTMX includes all fields)
        if isinstance(content_type_id, list):
            content_type_id = content_type_id[0] if content_type_id else None

        if not content_type_id:
            return

        initial = None
        try:
            content_type = ContentType.objects.get(pk=content_type_id)
            model_class = content_type.model_class()

            # Get initial value if editing existing object
            object_id_field = f"{field_prefix}_object_id"
            object_id = get_field_value(self, object_id_field)

            # Handle list values from duplicate GET parameters
            if isinstance(object_id, list):
                object_id = object_id[0] if object_id else None

            if object_id:
                initial = model_class.objects.get(pk=object_id)

            # Create dynamic choice field with model-specific queryset
            choice_field_name = f"{field_prefix}_choice"
            self.fields[choice_field_name] = DynamicModelChoiceField(
                label=field_prefix.replace('_', ' ').title(),
                queryset=model_class.objects.all(),
                required=True,
                initial=initial,
            )
        except (ContentType.DoesNotExist, ObjectDoesNotExist):
            # Invalid content type or object - form validation will catch this
            pass

    def clean(self):
        """
        Extract ContentType and object ID from selected objects.
        Populates hidden GenericForeignKey fields for model persistence.
        """
        super().clean()

        # Process each registered GenericFK field
        for field_prefix, content_type_field, object_id_field in self.generic_fk_fields:
            choice_field_name = f"{field_prefix}_choice"
            choice_object = self.cleaned_data.get(choice_field_name)

            if choice_object:
                # Populate GenericForeignKey fields
                self.cleaned_data[content_type_field] = ContentType.objects.get_for_model(choice_object)
                self.cleaned_data[object_id_field] = choice_object.id

        return self.cleaned_data


```

**Step 2: Run linting**

```bash
/opt/netbox/venv/bin/ruff format vendor_notification/forms.py
/opt/netbox/venv/bin/ruff check vendor_notification/forms.py
```

Expected: No errors (or auto-fixable warnings)

**Step 3: Commit mixin**

```bash
git add vendor_notification/forms.py
git commit -m "feat: add GenericForeignKeyFormMixin for HTMX object pickers

Add reusable mixin for forms with GenericForeignKey fields using
HTMX pattern. Provides init_generic_choice() for dynamic field creation
and clean() for value extraction."
```

---

## Task 2: Refactor ImpactForm to Use Mixin

**Files:**
- Modify: `vendor_notification/forms.py:131-321` (ImpactForm class)

**Step 1: Update ImpactForm inheritance and add configuration**

Change line 131:

```python
class ImpactForm(GenericForeignKeyFormMixin, NetBoxModelForm):
    """
    Form for creating/editing Impact records with GenericForeignKey support.
    Handles both event (Maintenance/Outage) and target (Circuit/Device/etc.) relationships.
    Uses HTMX pattern from EventRuleForm for dynamic object selection.
    """

    # Register GenericFK fields with mixin
    generic_fk_fields = [
        ('event', 'event_content_type', 'event_object_id'),
        ('target', 'target_content_type', 'target_object_id'),
    ]
```

**Step 2: Remove init_event_choice and init_target_choice methods**

Delete lines 215-295 (both methods). These are now handled by mixin's `init_generic_choice()`.

**Step 3: Update __init__ to call mixin methods**

Replace calls to `self.init_event_choice(event_ct_id)` around line 208 with:

```python
        # Determine event content type from form state (instance, initial, or GET/POST)
        event_ct_id = get_field_value(self, "event_content_type")
        if event_ct_id:
            self.init_generic_choice('event', event_ct_id)

        # Determine target content type from form state
        target_ct_id = get_field_value(self, "target_content_type")
        if target_ct_id:
            self.init_generic_choice('target', target_ct_id)
```

**Step 4: Remove most of clean() method**

Replace clean() method (lines 297-320) with:

```python
    def clean(self):
        """
        Extract ContentType and object ID from selected objects.
        Mixin handles the GenericFK field population.
        """
        return super().clean()
```

**Step 5: Verify ImpactForm structure**

The refactored ImpactForm should be approximately 90 lines, down from 190.

Key sections remaining:
- Class declaration with mixin inheritance
- generic_fk_fields configuration
- fieldsets
- Meta class
- __init__ method (queryset filtering + mixin calls)
- Minimal clean() method

**Step 6: Run linting**

```bash
/opt/netbox/venv/bin/ruff format vendor_notification/forms.py
/opt/netbox/venv/bin/ruff check vendor_notification/forms.py
```

Expected: No errors

**Step 7: Test ImpactForm still works**

```bash
# Start NetBox dev server in background
cd /opt/netbox/netbox
python manage.py runserver 0.0.0.0:8008 &

# Wait a few seconds for server to start
sleep 5

# Check server is running
curl -s http://localhost:8008/maintenance/ | grep -q "Maintenance" && echo "Server running"
```

Expected: "Server running"

Manual test (open browser):
1. Navigate to http://localhost:8008/plugins/vendor-notification/impact/add/
2. Select "Maintenance" from Event Type dropdown
3. Verify Event dropdown appears with Maintenance objects
4. Select "Circuit" from Target Type dropdown
5. Verify Target dropdown appears with Circuit objects
6. Submit form - should create Impact successfully

**Step 8: Kill dev server**

```bash
pkill -f "manage.py runserver"
```

**Step 9: Commit refactored ImpactForm**

```bash
git add vendor_notification/forms.py
git commit -m "refactor: migrate ImpactForm to use GenericForeignKeyFormMixin

Replace custom init_event_choice/init_target_choice methods with
mixin pattern. Reduces code from 190 to ~90 lines while maintaining
identical functionality."
```

---

## Task 3: Update EventNotificationForm with Object Picker

**Files:**
- Modify: `vendor_notification/forms.py:323-354` (EventNotificationForm class)

**Step 1: Update EventNotificationForm inheritance and add configuration**

Replace EventNotificationForm class (lines 323-354) with:

```python
class EventNotificationForm(GenericForeignKeyFormMixin, NetBoxModelForm):
    """
    Form for creating/editing EventNotification records.
    Uses GenericForeignKeyFormMixin for HTMX-based event object picker.
    """

    # Register GenericFK field with mixin
    generic_fk_fields = [
        ('event', 'event_content_type', 'event_object_id'),
    ]

    fieldsets = (
        FieldSet('event_content_type', 'event_choice', name='Event'),
        FieldSet('subject', 'email_from', 'email_received', name='Email Details'),
        FieldSet('email_body', name='Message'),
    )

    class Meta:
        model = EventNotification
        fields = (
            "event_content_type",
            "event_object_id",
            "subject",
            "email_from",
            "email_body",
            "email_received",
        )
        widgets = {
            "event_content_type": HTMXSelect(),
            "event_object_id": forms.HiddenInput,
            "email_received": DateTimePicker(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Customize event_content_type field
        self.fields["event_content_type"].queryset = ContentType.objects.filter(
            app_label="vendor_notification", model__in=["maintenance", "outage"]
        )
        self.fields["event_content_type"].label = "Event Type"
        self.fields["event_content_type"].help_text = "Type of event (Maintenance or Outage)"

        # Make hidden object_id field not required
        self.fields["event_object_id"].required = False

        # Determine event content type from form state
        event_ct_id = get_field_value(self, "event_content_type")
        if event_ct_id:
            self.init_generic_choice('event', event_ct_id)
```

**Step 2: Run linting**

```bash
/opt/netbox/venv/bin/ruff format vendor_notification/forms.py
/opt/netbox/venv/bin/ruff check vendor_notification/forms.py
```

Expected: No errors

**Step 3: Test EventNotificationForm with object picker**

```bash
# Start NetBox dev server in background
cd /opt/netbox/netbox
python manage.py runserver 0.0.0.0:8008 &

# Wait for server to start
sleep 5

# Check server is running
curl -s http://localhost:8008/maintenance/ | grep -q "Maintenance" && echo "Server running"
```

Expected: "Server running"

Manual test (open browser):
1. Navigate to http://localhost:8008/plugins/vendor-notification/notification/add/
2. Select "Maintenance" from Event Type dropdown
3. Verify Event dropdown appears with Maintenance objects (NEW BEHAVIOR!)
4. Select a Maintenance event
5. Fill in email details (subject, from, body, received date)
6. Submit form - should create EventNotification successfully
7. Verify object picker shows correct Maintenance event when editing

Repeat test with "Outage" selection:
1. Create new EventNotification
2. Select "Outage" from Event Type
3. Verify Event dropdown shows Outage objects
4. Complete and submit

**Step 4: Kill dev server**

```bash
pkill -f "manage.py runserver"
```

**Step 5: Commit EventNotificationForm enhancement**

```bash
git add vendor_notification/forms.py
git commit -m "feat: add dynamic object picker to EventNotificationForm

Migrate EventNotificationForm to use GenericForeignKeyFormMixin pattern.
Adds HTMX-based event object picker (matching ImpactForm UX) and
fieldsets for better form organization."
```

---

## Task 4: Update conftest.py in Main Repo

**Files:**
- Modify: `/opt/netbox-vendor-notification/tests/conftest.py:1-46`

**Note:** This fix was discovered during worktree setup and should be applied to main repo.

**Step 1: Navigate to main repo**

```bash
cd /opt/netbox-vendor-notification
```

**Step 2: Update conftest.py with corrected Django setup**

Replace `/opt/netbox-vendor-notification/tests/conftest.py` with:

```python
"""
Pytest configuration for vendor_notification tests.
Sets up Django and NetBox environment for testing.
"""

import os
import sys

# Add NetBox to Python path BEFORE any imports
sys.path.insert(0, "/opt/netbox/netbox")

# Configure NetBox to use testing configuration
os.environ["NETBOX_CONFIGURATION"] = "netbox.configuration_testing"

# Set Django settings module to netbox.settings (NOT configuration_testing)
os.environ["DJANGO_SETTINGS_MODULE"] = "netbox.settings"

# Import and configure testing settings BEFORE pytest starts
from netbox import configuration_testing

# Configure database for testing
configuration_testing.DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Add vendor_notification to PLUGINS
if not hasattr(configuration_testing, "PLUGINS"):
    configuration_testing.PLUGINS = []
if "vendor_notification" not in configuration_testing.PLUGINS:
    configuration_testing.PLUGINS.append("vendor_notification")

# Set default PLUGINS_CONFIG if not present
if not hasattr(configuration_testing, "PLUGINS_CONFIG"):
    configuration_testing.PLUGINS_CONFIG = {}

if "vendor_notification" not in configuration_testing.PLUGINS_CONFIG:
    configuration_testing.PLUGINS_CONFIG["vendor_notification"] = {}

# Initialize Django BEFORE test collection
import django

django.setup()


def pytest_configure(config):
    """
    Hook called after command line options have been parsed.
    Django is already set up at module import time above.
    """
    pass
```

**Step 3: Run tests to verify fix**

```bash
PYTHONPATH=/opt/netbox/netbox /opt/netbox/venv/bin/pytest tests/test_timezone_logic.py -v
```

Expected: 14 tests pass

**Step 4: Commit conftest.py fix to main repo**

```bash
git add tests/conftest.py
git commit -m "fix: correct Django settings initialization in conftest.py

Set DJANGO_SETTINGS_MODULE to 'netbox.settings' instead of
'netbox.configuration_testing'. NetBox's settings.py loads
configuration via NETBOX_CONFIGURATION env var.

This fixes 'ContentType not in INSTALLED_APPS' errors during
test collection by ensuring Django is properly configured before
test modules are imported."
```

**Step 5: Return to worktree**

```bash
cd /opt/netbox-vendor-notification/.worktrees/event-notification-form-picker
```

---

## Task 5: Final Verification and Documentation

**Files:**
- None (testing and verification only)

**Step 1: Run full test suite**

```bash
/opt/netbox/venv/bin/pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected:
- 180+ tests passing
- Same failure count as baseline (34 failures, 12 errors from pre-existing issues)
- No new failures introduced

**Step 2: Manual regression testing checklist**

Start dev server:
```bash
cd /opt/netbox/netbox
python manage.py runserver 0.0.0.0:8008 &
sleep 5
```

Test ImpactForm (regression):
- [ ] Create new Impact with Maintenance event → works
- [ ] Create new Impact with Outage event → works
- [ ] Create new Impact with Circuit target → works
- [ ] Create new Impact with Device target → works
- [ ] Edit existing Impact → fields pre-populate correctly
- [ ] HTMX dropdown behavior smooth (no JavaScript errors)

Test EventNotificationForm (new feature):
- [ ] Create new EventNotification with Maintenance → works
- [ ] Create new EventNotification with Outage → works
- [ ] Event object picker appears after selecting type → works
- [ ] Edit existing EventNotification → event pre-populates correctly
- [ ] Fieldsets display properly (Event, Email Details, Message) → works
- [ ] HTMX dropdown behavior smooth → works

Stop dev server:
```bash
pkill -f "manage.py runserver"
```

**Step 3: Review code quality**

Run final linting:
```bash
/opt/netbox/venv/bin/ruff format vendor_notification/forms.py
/opt/netbox/venv/bin/ruff check vendor_notification/forms.py
```

Expected: Clean (no errors or warnings)

**Step 4: Compare with design document**

Verify implementation matches design in `docs/plans/2025-11-05-event-notification-form-object-picker-design.md`:
- [ ] GenericForeignKeyFormMixin implemented per spec
- [ ] ImpactForm refactored to use mixin
- [ ] EventNotificationForm enhanced with object picker
- [ ] Fieldsets added to EventNotificationForm
- [ ] HTMXSelect widget configured
- [ ] No model changes (backward compatible)
- [ ] No migrations required

**Step 5: Final commit (if any remaining changes)**

```bash
git status
# If any unstaged changes:
git add -A
git commit -m "chore: final cleanup and documentation"
```

---

## Summary

**What was built:**
- GenericForeignKeyFormMixin: Reusable pattern for GenericFK forms with HTMX
- ImpactForm: Refactored to use mixin (190 → 90 lines, identical functionality)
- EventNotificationForm: Enhanced with dynamic object picker + fieldsets
- Test configuration: Fixed conftest.py for proper Django setup

**Code changes:**
- vendor_notification/forms.py: ~80 lines added (mixin), ~100 lines removed (refactor), ~35 lines changed (EventNotificationForm)
- tests/conftest.py: Corrected Django settings initialization

**Testing:**
- Manual testing required for HTMX behavior (no automated tests for form rendering)
- All existing tests continue to pass (180+ passing)
- Regression tested ImpactForm (existing feature)
- Verified EventNotificationForm new behavior

**Deployment:**
- No migrations required
- No model changes
- Backward compatible
- Single file change (forms.py) + test fix

**Next steps:**
- Merge worktree branch to main
- Deploy to production
- Monitor for any HTMX/JavaScript issues in production
- Consider extracting mixin to NetBox core if pattern proves broadly useful
