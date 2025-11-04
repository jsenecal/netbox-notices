# Impact Form Object Picker Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace manual PK entry in Impact form with dynamic object pickers using NetBox's EventRuleForm HTMX pattern.

**Architecture:** Use HTMXSelect widgets for content type dropdowns that trigger form reload. Dynamically inject DynamicModelChoiceField based on selected content type. Hide raw object_id fields. Extract ContentType and ID in clean() method. Support both standalone and embedded (from Event page) contexts.

**Tech Stack:** Django forms, NetBox utilities (HTMXSelect, DynamicModelChoiceField, get_field_value), HTMX for dynamic reloading

---

## Task 1: Update ImpactForm imports and Meta class

**Files:**
- Modify: `vendor_notification/forms.py:1-20` (imports section)
- Modify: `vendor_notification/forms.py:118-146` (ImpactForm class)

**Step 1: Add required imports**

Add these imports to the top of `vendor_notification/forms.py` after existing imports:

```python
from django.core.exceptions import ObjectDoesNotExist
from utilities.forms import get_field_value
from utilities.forms.widgets import HTMXSelect
```

**Step 2: Update ImpactForm Meta class widgets**

Replace the entire `ImpactForm` class (currently lines 118-174) with this updated version:

```python
class ImpactForm(NetBoxModelForm):
    """
    Form for creating/editing Impact records with GenericForeignKey support.
    Handles both event (Maintenance/Outage) and target (Circuit/Device/etc.) relationships.
    Uses HTMX pattern from EventRuleForm for dynamic object selection.
    """

    event_content_type = ContentTypeChoiceField(
        label="Event Type",
        queryset=ContentType.objects.filter(app_label="vendor_notification", model__in=["maintenance", "outage"]),
        help_text="Type of event (Maintenance or Outage)",
    )

    target_content_type = ContentTypeChoiceField(
        label="Target Type",
        queryset=ContentType.objects.none(),  # Will be set in __init__
        help_text="Type of affected object",
    )

    # Dynamic choice fields - created in __init__ based on content type selection
    event_choice = None
    target_choice = None

    fieldsets = (
        ('Event', ('event_content_type', 'event_choice')),
        ('Target', ('target_content_type', 'target_choice')),
        ('Impact Details', ('impact', 'tags')),
    )

    class Meta:
        model = Impact
        fields = (
            'event_content_type',
            'event_object_id',
            'target_content_type',
            'target_object_id',
            'impact',
            'tags',
        )
        widgets = {
            'event_content_type': HTMXSelect(),
            'target_content_type': HTMXSelect(),
            'event_object_id': forms.HiddenInput,
            'target_object_id': forms.HiddenInput,
        }
```

**Step 3: Verify syntax**

Run Python syntax check:

```bash
/opt/netbox/venv/bin/python -m py_compile vendor_notification/forms.py
```

Expected: No output (syntax valid)

**Step 4: Commit**

```bash
git add vendor_notification/forms.py
git commit -m "refactor: add HTMX widgets and imports to ImpactForm

Add HTMXSelect widgets for content type fields and hidden inputs for
object_id fields. Add imports for get_field_value and HTMXSelect.
Prepare form structure for dynamic object picker implementation.

Refs: docs/plans/2025-11-04-impact-form-object-picker-design.md"
```

---

## Task 2: Implement ImpactForm __init__ method

**Files:**
- Modify: `vendor_notification/forms.py:118-146` (add __init__ method after fieldsets)

**Step 1: Add __init__ method**

Add this method immediately after the `Meta` class in `ImpactForm`:

```python
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Make hidden object_id fields not required
        self.fields['event_object_id'].required = False
        self.fields['target_object_id'].required = False

        # Get allowed content types for targets from plugin configuration
        allowed_types = get_allowed_content_types()
        target_content_types = []
        for type_string in allowed_types:
            try:
                app_label, model = type_string.lower().split(".")
                ct = ContentType.objects.filter(app_label=app_label, model=model).first()
                if ct:
                    target_content_types.append(ct.pk)
            except (ValueError, AttributeError):
                # Skip invalid format
                continue

        # Update target_content_type queryset based on allowed types
        self.fields["target_content_type"].queryset = ContentType.objects.filter(
            pk__in=target_content_types
        )

        # Determine event content type from form state (instance, initial, or GET/POST)
        event_ct_id = get_field_value(self, 'event_content_type')
        if event_ct_id:
            self.init_event_choice(event_ct_id)

        # Determine target content type from form state
        target_ct_id = get_field_value(self, 'target_content_type')
        if target_ct_id:
            self.init_target_choice(target_ct_id)

        # Handle embedded context (pre-filled from Event detail page)
        if not self.instance.pk:  # Only on create
            event_obj_id = get_field_value(self, 'event_object_id')
            if event_ct_id and event_obj_id:
                # Make event fields read-only in embedded context
                self.fields['event_content_type'].disabled = True
                if 'event_choice' in self.fields:
                    self.fields['event_choice'].disabled = True
```

**Step 2: Verify syntax**

```bash
/opt/netbox/venv/bin/python -m py_compile vendor_notification/forms.py
```

Expected: No output (syntax valid)

**Step 3: Commit**

```bash
git add vendor_notification/forms.py
git commit -m "feat: add ImpactForm __init__ with dynamic field setup

Implement form initialization that:
- Makes hidden object_id fields non-required
- Filters target content types based on plugin config
- Detects selected content types via get_field_value
- Calls helper methods to inject dynamic choice fields
- Handles embedded context by disabling event fields

Refs: docs/plans/2025-11-04-impact-form-object-picker-design.md"
```

---

## Task 3: Implement init_event_choice helper method

**Files:**
- Modify: `vendor_notification/forms.py` (add method after __init__)

**Step 1: Add init_event_choice method**

Add this method after the `__init__` method in `ImpactForm`:

```python
    def init_event_choice(self, content_type_id):
        """
        Initialize event choice field based on selected content type.
        Creates DynamicModelChoiceField with appropriate queryset.

        Args:
            content_type_id: Primary key of selected ContentType
        """
        initial = None
        try:
            content_type = ContentType.objects.get(pk=content_type_id)
            model_class = content_type.model_class()

            # Get initial value if editing existing Impact
            event_id = get_field_value(self, 'event_object_id')
            if event_id:
                initial = model_class.objects.get(pk=event_id)

            # Create dynamic choice field with model-specific queryset
            self.fields['event_choice'] = DynamicModelChoiceField(
                label='Event',
                queryset=model_class.objects.all(),
                required=True,
                initial=initial
            )
        except (ContentType.DoesNotExist, ObjectDoesNotExist):
            # Invalid content type or object - form validation will catch this
            pass
```

**Step 2: Verify syntax**

```bash
/opt/netbox/venv/bin/python -m py_compile vendor_notification/forms.py
```

Expected: No output (syntax valid)

**Step 3: Commit**

```bash
git add vendor_notification/forms.py
git commit -m "feat: add init_event_choice helper to ImpactForm

Add helper method that dynamically creates DynamicModelChoiceField
for event selection based on selected ContentType. Handles both
create and edit modes by detecting initial values.

Refs: docs/plans/2025-11-04-impact-form-object-picker-design.md"
```

---

## Task 4: Implement init_target_choice helper method

**Files:**
- Modify: `vendor_notification/forms.py` (add method after init_event_choice)

**Step 1: Add init_target_choice method**

Add this method after the `init_event_choice` method in `ImpactForm`:

```python
    def init_target_choice(self, content_type_id):
        """
        Initialize target choice field based on selected content type.
        Creates DynamicModelChoiceField with appropriate queryset.

        Args:
            content_type_id: Primary key of selected ContentType
        """
        initial = None
        try:
            content_type = ContentType.objects.get(pk=content_type_id)
            model_class = content_type.model_class()

            # Get initial value if editing existing Impact
            target_id = get_field_value(self, 'target_object_id')
            if target_id:
                initial = model_class.objects.get(pk=target_id)

            # Create dynamic choice field with model-specific queryset
            self.fields['target_choice'] = DynamicModelChoiceField(
                label='Target Object',
                queryset=model_class.objects.all(),
                required=True,
                initial=initial
            )
        except (ContentType.DoesNotExist, ObjectDoesNotExist):
            # Invalid content type or object - form validation will catch this
            pass
```

**Step 2: Verify syntax**

```bash
/opt/netbox/venv/bin/python -m py_compile vendor_notification/forms.py
```

Expected: No output (syntax valid)

**Step 3: Commit**

```bash
git add vendor_notification/forms.py
git commit -m "feat: add init_target_choice helper to ImpactForm

Add helper method that dynamically creates DynamicModelChoiceField
for target object selection based on selected ContentType. Mirrors
init_event_choice pattern for consistency.

Refs: docs/plans/2025-11-04-impact-form-object-picker-design.md"
```

---

## Task 5: Implement ImpactForm clean method

**Files:**
- Modify: `vendor_notification/forms.py` (add method after init_target_choice)

**Step 1: Add clean method**

Add this method after the `init_target_choice` method in `ImpactForm`:

```python
    def clean(self):
        """
        Extract ContentType and object ID from selected objects.
        Populates hidden GenericForeignKey fields for model persistence.
        """
        super().clean()

        # Extract event object and populate GenericForeignKey fields
        event_choice = self.cleaned_data.get('event_choice')
        if event_choice:
            self.cleaned_data['event_content_type'] = ContentType.objects.get_for_model(event_choice)
            self.cleaned_data['event_object_id'] = event_choice.id

        # Extract target object and populate GenericForeignKey fields
        target_choice = self.cleaned_data.get('target_choice')
        if target_choice:
            self.cleaned_data['target_content_type'] = ContentType.objects.get_for_model(target_choice)
            self.cleaned_data['target_object_id'] = target_choice.id

        return self.cleaned_data
```

**Step 2: Verify syntax**

```bash
/opt/netbox/venv/bin/python -m py_compile vendor_notification/forms.py
```

Expected: No output (syntax valid)

**Step 3: Run linting**

```bash
/opt/netbox/venv/bin/ruff check vendor_notification/forms.py
```

Expected: No errors (or auto-fixable warnings)

**Step 4: Format code**

```bash
/opt/netbox/venv/bin/ruff format vendor_notification/forms.py
```

Expected: File formatted successfully

**Step 5: Commit**

```bash
git add vendor_notification/forms.py
git commit -m "feat: add clean method to extract objects from choices

Implement form validation that extracts ContentType and object IDs
from DynamicModelChoiceField selections. Uses get_for_model to
automatically determine correct ContentType for selected objects.

Completes ImpactForm HTMX pattern implementation.

Refs: docs/plans/2025-11-04-impact-form-object-picker-design.md"
```

---

## Task 6: Update template_content.py for embedded context

**Files:**
- Modify: `vendor_notification/template_content.py`

**Step 1: Review current template_content.py**

Read the file to understand current structure:

```bash
cat vendor_notification/template_content.py
```

**Step 2: Add Impact button template content**

If the file exists and has content, add this at the end. If it's empty or doesn't exist, create it with this content:

```python
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse


def add_impact_button(instance):
    """
    Add 'Add Impact' button to Maintenance and Outage detail pages.
    Pre-fills event content type and object ID via URL parameters.

    Args:
        instance: Maintenance or Outage instance

    Returns:
        HTML string with button linking to Impact creation form
    """
    ct = ContentType.objects.get_for_model(instance)
    url = f"{reverse('plugins:vendor_notification:impact_add')}?event_content_type={ct.pk}&event_object_id={instance.pk}"
    return f'''
    <div class="card">
        <div class="card-body">
            <h5 class="card-title">Impacts</h5>
            <p class="card-text">Add affected objects for this event.</p>
            <a href="{url}" class="btn btn-sm btn-primary">
                <i class="mdi mdi-plus-thick"></i> Add Impact
            </a>
        </div>
    </div>
    '''


# Register template content for Maintenance model
template_extensions = {
    'circuits.provider': {
        'right_page': [],
    },
    'vendor_notification.maintenance': {
        'right_page': [add_impact_button],
    },
    'vendor_notification.outage': {
        'right_page': [add_impact_button],
    },
}
```

**Step 3: Verify syntax**

```bash
/opt/netbox/venv/bin/python -m py_compile vendor_notification/template_content.py
```

Expected: No output (syntax valid)

**Step 4: Commit**

```bash
git add vendor_notification/template_content.py
git commit -m "feat: add Impact button to event detail pages

Add template content injection that displays 'Add Impact' button on
Maintenance and Outage detail pages. Button pre-fills event context
via URL parameters for streamlined impact creation workflow.

Refs: docs/plans/2025-11-04-impact-form-object-picker-design.md"
```

---

## Task 7: Manual testing - Standalone Impact creation

**Goal:** Verify form works correctly in standalone mode (from Impact list page)

**Step 1: Start NetBox development server**

```bash
make runserver
```

Expected: Server starts on http://localhost:8008

**Step 2: Navigate to Impact add form**

1. Open browser to http://localhost:8008
2. Login (admin/admin)
3. Navigate to: Plugins → Vendor Notification → Impacts
4. Click "Add" button

**Step 3: Test event selection**

1. Select "Event Type" → "Maintenance"
2. Verify HTMX reloads form
3. Verify "Event" dropdown appears with APISelect widget
4. Type to search for maintenance events
5. Select a maintenance event

Expected: Form reloads after content type selection, dropdown shows searchable maintenance events

**Step 4: Test target selection**

1. Select "Target Type" → "Circuit" (or another allowed type)
2. Verify HTMX reloads form
3. Verify "Target Object" dropdown appears with APISelect widget
4. Type to search for circuits
5. Select a circuit

Expected: Form reloads after content type selection, dropdown shows searchable circuits

**Step 5: Complete form submission**

1. Select "Impact" level (e.g., "Outage")
2. Click "Create"

Expected: Impact created successfully, redirects to Impact detail page

**Step 6: Document results**

If any issues found, document them. Otherwise, proceed to commit:

```bash
git commit --allow-empty -m "test: verify standalone Impact creation works

Manual testing confirms:
- Event content type selection triggers HTMX reload
- Event object picker appears with correct queryset
- Target content type selection triggers HTMX reload
- Target object picker appears with correct queryset
- Form submission creates Impact successfully

Refs: docs/plans/2025-11-04-impact-form-object-picker-design.md"
```

---

## Task 8: Manual testing - Embedded Impact creation

**Goal:** Verify form works correctly in embedded mode (from Event detail page)

**Step 1: Navigate to Maintenance detail page**

1. Navigate to: Plugins → Vendor Notification → Maintenances
2. Click on any maintenance event

**Step 2: Verify Impact button appears**

1. Look for "Add Impact" button in right sidebar

Expected: Button appears with link to Impact add form

**Step 3: Click Add Impact button**

1. Click "Add Impact" button
2. Verify redirects to Impact add form
3. Verify URL contains: `?event_content_type=X&event_object_id=Y`

Expected: Form loads with pre-filled event fields

**Step 4: Verify event fields are disabled**

1. Verify "Event Type" dropdown is disabled/readonly
2. Verify "Event" field shows selected maintenance (if visible)
3. Verify cannot change event selection

Expected: Event fields are pre-filled and locked

**Step 5: Complete target selection**

1. Select "Target Type" → "Circuit"
2. Select target circuit from dropdown
3. Select "Impact" level
4. Click "Create"

Expected: Impact created successfully with correct event linkage

**Step 6: Repeat for Outage**

1. Navigate to an Outage detail page
2. Click "Add Impact" button
3. Verify form pre-fills with outage
4. Create an impact

Expected: Works identically to Maintenance flow

**Step 7: Document results**

```bash
git commit --allow-empty -m "test: verify embedded Impact creation works

Manual testing confirms:
- Add Impact button appears on Maintenance detail pages
- Add Impact button appears on Outage detail pages
- Form pre-fills event_content_type and event_object_id from URL
- Event fields are disabled in embedded context
- Form submission creates Impact with correct event linkage

Refs: docs/plans/2025-11-04-impact-form-object-picker-design.md"
```

---

## Task 9: Manual testing - Edit existing Impact

**Goal:** Verify form correctly populates when editing existing Impact

**Step 1: Navigate to existing Impact**

1. Navigate to: Plugins → Vendor Notification → Impacts
2. Click on an existing impact (created in previous tests)
3. Click "Edit" button

**Step 2: Verify fields populate correctly**

1. Verify "Event Type" shows correct content type (Maintenance or Outage)
2. Verify "Event" field shows selected event object
3. Verify "Target Type" shows correct content type
4. Verify "Target Object" field shows selected target object
5. Verify "Impact" level is selected

Expected: All fields populate with existing values

**Step 3: Test changing selections**

1. Change "Impact" level
2. Click "Update"

Expected: Impact updates successfully

**Step 4: Test changing content types**

1. Edit same impact again
2. Change "Target Type" to different type
3. Verify target object picker updates
4. Select new target object
5. Click "Update"

Expected: Impact updates with new target object

**Step 5: Document results**

```bash
git commit --allow-empty -m "test: verify Impact edit functionality works

Manual testing confirms:
- Edit form loads with all fields populated from instance
- Event choice field initializes with correct object
- Target choice field initializes with correct object
- Changing content types updates pickers correctly
- Form submission updates Impact successfully

Refs: docs/plans/2025-11-04-impact-form-object-picker-design.md"
```

---

## Task 10: Final code review and cleanup

**Files:**
- Review: `vendor_notification/forms.py`
- Review: `vendor_notification/template_content.py`

**Step 1: Run full linting**

```bash
/opt/netbox/venv/bin/ruff check vendor_notification/
```

Expected: No errors

**Step 2: Run formatting**

```bash
/opt/netbox/venv/bin/ruff format vendor_notification/
```

Expected: All files formatted

**Step 3: Verify no migrations needed**

```bash
make makemigrations
```

Expected: "No changes detected"

**Step 4: Review changes**

```bash
git diff main...HEAD --stat
git log main..HEAD --oneline
```

Expected: See all commits from this implementation

**Step 5: Final commit if any cleanup done**

If any formatting or cleanup was applied:

```bash
git add vendor_notification/
git commit -m "chore: final linting and formatting cleanup

Apply ruff formatting to all modified files.
Ensure code quality standards met.

Refs: docs/plans/2025-11-04-impact-form-object-picker-design.md"
```

---

## Completion Checklist

- [ ] Task 1: Updated ImpactForm imports and Meta class
- [ ] Task 2: Implemented ImpactForm __init__ method
- [ ] Task 3: Implemented init_event_choice helper method
- [ ] Task 4: Implemented init_target_choice helper method
- [ ] Task 5: Implemented ImpactForm clean method
- [ ] Task 6: Updated template_content.py for embedded context
- [ ] Task 7: Manual testing - Standalone Impact creation
- [ ] Task 8: Manual testing - Embedded Impact creation
- [ ] Task 9: Manual testing - Edit existing Impact
- [ ] Task 10: Final code review and cleanup

## Next Steps

After completing all tasks:

1. **Review all commits** - Ensure commit messages are clear and reference design doc
2. **Test edge cases** - Try creating impacts with various content types
3. **Update documentation** - Add screenshots if needed
4. **Create pull request** - Use superpowers:finishing-a-development-branch skill

## References

- **Design Document:** `docs/plans/2025-11-04-impact-form-object-picker-design.md`
- **NetBox EventRuleForm:** `/opt/netbox/netbox/extras/forms/model_forms.py:450-563`
- **CLAUDE.md:** Project instructions and conventions
