# Impact Form Object Picker Design

**Date:** 2025-11-04
**Status:** Approved
**Pattern:** NetBox EventRuleForm HTMX Pattern

## Overview

Replace manual PK entry in the Impact form with dynamic object pickers for both event (Maintenance/Outage) and target (Circuit/Device/VM/etc.) objects. This design follows NetBox's established pattern from EventRuleForm for handling GenericForeignKey relationships with HTMX-based dynamic form reloading.

## Problem Statement

Currently, the Impact form requires users to manually enter integer PKs for both the event object and target object. This is error-prone and provides poor UX. Users need a proper object picker with type-ahead search, similar to how the MaintenanceForm handles Provider selection.

## Design Goals

1. **User-friendly object selection** - Type-ahead search instead of manual PK entry
2. **Follow NetBox patterns** - Use established EventRuleForm pattern with HTMX
3. **Context-aware** - Support both standalone and embedded (from Event page) contexts
4. **No custom JavaScript** - Leverage NetBox's built-in HTMX infrastructure

## Architecture Overview

### Core Pattern: HTMX-based Dynamic Form Reload

Following NetBox's EventRuleForm (extras/forms/model_forms.py:450-563):

1. **Hidden fields** - `event_object_id` and `target_object_id` use `forms.HiddenInput`
2. **Separate choice fields** - Create `event_choice` and `target_choice` as DynamicModelChoiceFields
3. **HTMX widgets** - Use `HTMXSelect()` for content type dropdowns to trigger form reload
4. **Dynamic initialization** - Based on selected content type, initialize choice field with correct queryset
5. **Form clean()** - Extract ContentType and ID from selected objects

### Data Flow

```
User selects content type (e.g., "Maintenance")
    ↓
HTMXSelect widget triggers form reload
    ↓
Server detects content_type in form data
    ↓
__init__ creates DynamicModelChoiceField with Maintenance queryset
    ↓
Form renders with APISelect widget for object selection
    ↓
User searches/selects object
    ↓
clean() extracts ContentType and object.id
    ↓
Hidden fields populated with correct values
```

## Implementation Details

### Form Structure

```python
class ImpactForm(NetBoxModelForm):
    event_content_type = ContentTypeChoiceField(
        label="Event Type",
        queryset=ContentType.objects.filter(
            app_label="vendor_notification",
            model__in=["maintenance", "outage"]
        ),
    )

    target_content_type = ContentTypeChoiceField(
        label="Target Type",
        queryset=ContentType.objects.none(),  # Set in __init__
    )

    # Dynamic fields - created in __init__
    event_choice = None
    target_choice = None

    fieldsets = (
        FieldSet('event_content_type', 'event_choice', name='Event'),
        FieldSet('target_content_type', 'target_choice', name='Target'),
        FieldSet('impact', 'tags', name='Impact Details'),
    )

    class Meta:
        model = Impact
        fields = (
            'event_content_type', 'event_object_id',
            'target_content_type', 'target_object_id',
            'impact', 'tags',
        )
        widgets = {
            'event_content_type': HTMXSelect(),
            'target_content_type': HTMXSelect(),
            'event_object_id': forms.HiddenInput,
            'target_object_id': forms.HiddenInput,
        }
```

### Initialization Pattern

```python
def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

    # Make hidden fields not required
    self.fields['event_object_id'].required = False
    self.fields['target_object_id'].required = False

    # Set target content type queryset from plugin config
    allowed_types = get_allowed_content_types()
    target_content_types = []
    for type_string in allowed_types:
        try:
            app_label, model = type_string.lower().split(".")
            ct = ContentType.objects.filter(app_label=app_label, model=model).first()
            if ct:
                target_content_types.append(ct.pk)
        except (ValueError, AttributeError):
            continue

    self.fields["target_content_type"].queryset = ContentType.objects.filter(
        pk__in=target_content_types
    )

    # Initialize dynamic choice fields based on content type selection
    event_ct_id = get_field_value(self, 'event_content_type')
    if event_ct_id:
        self.init_event_choice(event_ct_id)

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

def init_event_choice(self, content_type_id):
    """Initialize event choice field based on selected content type"""
    initial = None
    try:
        content_type = ContentType.objects.get(pk=content_type_id)
        model_class = content_type.model_class()

        # Get initial value if editing
        event_id = get_field_value(self, 'event_object_id')
        if event_id:
            initial = model_class.objects.get(pk=event_id)

        self.fields['event_choice'] = DynamicModelChoiceField(
            label='Event',
            queryset=model_class.objects.all(),
            required=True,
            initial=initial
        )
    except (ContentType.DoesNotExist, ObjectDoesNotExist):
        pass

def init_target_choice(self, content_type_id):
    """Initialize target choice field based on selected content type"""
    initial = None
    try:
        content_type = ContentType.objects.get(pk=content_type_id)
        model_class = content_type.model_class()

        # Get initial value if editing
        target_id = get_field_value(self, 'target_object_id')
        if target_id:
            initial = model_class.objects.get(pk=target_id)

        self.fields['target_choice'] = DynamicModelChoiceField(
            label='Target Object',
            queryset=model_class.objects.all(),
            required=True,
            initial=initial
        )
    except (ContentType.DoesNotExist, ObjectDoesNotExist):
        pass
```

**Key NetBox utilities:**
- `get_field_value(form, field_name)` - Gets value from instance, initial, or POST/GET data (in that order)
- `HTMXSelect()` - Widget that triggers form reload on change via HTMX
- `DynamicModelChoiceField` - NetBox's API-backed select field

### Validation Pattern

```python
def clean(self):
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

**Benefits:**
- `ContentType.objects.get_for_model()` automatically gets correct ContentType
- No manual validation needed - if choice exists, it's valid
- Existing model-level validation (Impact.clean()) still runs

## Context-Aware Behavior

### Standalone Context

**URL:** `/plugins/vendor-notification/impacts/add/`

**Behavior:**
- All fields visible and editable
- No pre-filled values
- Standard creation flow

### Embedded Context (from Event detail page)

**URL:** `/plugins/vendor-notification/impacts/add/?event_content_type=X&event_object_id=Y`

**Behavior:**
- Event content type and object pre-filled from URL parameters
- Event fields disabled (read-only)
- User only selects target_content_type and target_object
- Streamlined workflow when adding impacts from Event page

**Implementation:**
- Form detects URL params via `get_field_value()`
- Disables event fields when pre-filled
- Add Impact button on Event detail pages includes URL parameters

## Template Changes

### No Custom JavaScript Required

Since we're using HTMX with NetBox's standard patterns:
- HTMXSelect widget handles form reloading automatically
- No custom JavaScript file needed
- Standard template: `generic/object_edit.html`

### Field Organization

Use fieldsets to group related fields logically:

```python
fieldsets = (
    FieldSet('event_content_type', 'event_choice', name='Event'),
    FieldSet('target_content_type', 'target_choice', name='Target'),
    FieldSet('impact', 'tags', name='Impact Details'),
)
```

## View Updates

### Add Impact Button on Event Detail Pages

**Location:** `template_content.py`

Add button to Maintenance and Outage detail pages:

```python
# In template_content.py
def add_impact_button(obj):
    """Add 'Add Impact' button to event detail pages"""
    ct = ContentType.objects.get_for_model(obj)
    url = f"{reverse('plugins:vendor_notification:impact_add')}?event_content_type={ct.pk}&event_object_id={obj.pk}"
    return f'<a href="{url}" class="btn btn-primary">Add Impact</a>'
```

## Error Handling

### Form Validation Errors

- Django form validation automatically preserves field values on error
- HTMX re-renders form with error messages
- Hidden fields maintain correct values
- Dynamic choice fields reconstruct with proper queryset via `get_field_value()`

### Edge Cases

1. **Content type selected but no object chosen** - Required field validation handles this
2. **Content type changes after object selected** - HTMX form reload clears object field
3. **Invalid object ID from URL params** - Form validation catches this, shows error
4. **Edit existing Impact** - Load both content_type and object from instance via `get_field_value()`
5. **Form submission errors** - Preserved state via `get_field_value()` from POST data

## Migration Path

### Backward Compatibility

- Existing Impact records work without changes
- API remains unchanged - still accepts content_type ID + object_id
- Form still reads/writes same model fields

### Deprecation

- Old IntegerField widgets for object_id fields replaced with HiddenInput
- No breaking changes for existing integrations

## Testing Strategy

1. **Create Impact (standalone)** - Select event and target via pickers
2. **Create Impact (embedded)** - From Maintenance/Outage detail page with pre-filled event
3. **Edit Impact** - Verify fields populate correctly
4. **Content type switching** - Ensure object picker updates correctly
5. **Form validation errors** - Verify state preservation
6. **API compatibility** - Ensure existing API clients still work

## Implementation Checklist

- [ ] Update ImpactForm in forms.py
  - [ ] Add HTMXSelect widgets for content type fields
  - [ ] Add hidden widgets for object_id fields
  - [ ] Implement `__init__` with get_field_value logic
  - [ ] Implement init_event_choice method
  - [ ] Implement init_target_choice method
  - [ ] Implement clean method
  - [ ] Add fieldsets
- [ ] Add get_field_value import from NetBox utilities
- [ ] Update template_content.py
  - [ ] Add "Add Impact" button to Maintenance detail page
  - [ ] Add "Add Impact" button to Outage detail page
- [ ] Test all contexts
  - [ ] Standalone creation
  - [ ] Embedded creation from Maintenance page
  - [ ] Embedded creation from Outage page
  - [ ] Edit existing Impact
  - [ ] Form validation error handling
- [ ] Update EventNotificationForm using same pattern (if needed)
- [ ] Documentation updates
  - [ ] Update README with new form behavior
  - [ ] Add screenshots of new picker UI

## References

- **NetBox EventRuleForm pattern:** `/opt/netbox/netbox/extras/forms/model_forms.py:450-563`
- **DynamicModelChoiceField:** `/opt/netbox/netbox/utilities/forms/fields/dynamic.py`
- **HTMXSelect widget:** NetBox utilities forms widgets
- **get_field_value utility:** NetBox forms utilities
