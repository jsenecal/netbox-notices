# Event Notification Form Object Picker - Design Document

**Date:** 2025-11-05
**Status:** Approved
**Author:** Design validated through brainstorming session

## Problem Statement

The EventNotificationForm currently lacks a user-friendly object picker for selecting the associated event (Maintenance or Outage). Users must manually enter the event_object_id as a number, which is error-prone and provides poor UX compared to the ImpactForm, which has dynamic HTMX-based object pickers.

**Current State:**
- ImpactForm: Has dynamic object pickers using HTMXSelect widgets and DynamicModelChoiceField
- EventNotificationForm: Basic integer input field for event_object_id

**Desired State:**
- EventNotificationForm: Same dynamic object picker pattern as ImpactForm
- Organized fieldsets for better form layout
- Shared code to reduce duplication

## Solution Overview

Implement a `GenericForeignKeyFormMixin` that encapsulates the HTMX pattern for GenericForeignKey object selection. Both ImpactForm and EventNotificationForm will inherit from this mixin, eliminating code duplication while providing consistent UX.

**Approach Selected:** Shared Mixin/Base Class
- **Rationale:** DRY principle, better maintainability, extensible for future forms with GenericFK relationships
- **Trade-offs:** Slightly more complex upfront, but cleaner long-term

## Architecture

### 1. Mixin Design

**GenericForeignKeyFormMixin** will provide:

1. **Dynamic field creation:**
   ```python
   def init_generic_choice(self, field_prefix, content_type_id):
       """
       Initialize a choice field based on selected content type.

       Args:
           field_prefix: Field name prefix (e.g., 'event', 'target')
           content_type_id: Primary key of selected ContentType
       """
   ```
   - Resolves ContentType and model class
   - Creates DynamicModelChoiceField with appropriate queryset
   - Handles initial values from existing instances
   - Handles list values from duplicate GET parameters (HTMX behavior)

2. **Configuration system:**
   - Subclasses declare: `generic_fk_fields = [('field_prefix', 'content_type_field', 'object_id_field')]`
   - Example: `[('event', 'event_content_type', 'event_object_id')]`
   - Tells mixin which GenericFK pairs to manage

3. **Clean method logic:**
   - Iterates through registered GFK fields
   - Extracts selected objects from choice fields
   - Populates hidden content_type and object_id fields
   - Enables proper model persistence

### 2. Form Changes

**ImpactForm Refactoring:**

Before (190 lines):
- Custom init_event_choice() method
- Custom init_target_choice() method
- Custom clean() logic for two GFK relationships
- Code duplication with similar patterns

After (60 lines):
```python
class ImpactForm(GenericForeignKeyFormMixin, NetBoxModelForm):
    generic_fk_fields = [
        ('event', 'event_content_type', 'event_object_id'),
        ('target', 'target_content_type', 'target_object_id')
    ]

    # Keep: fieldsets, Meta, custom queryset filtering in __init__
    # Remove: init_event_choice, init_target_choice, most clean() logic
```

**EventNotificationForm Enhancement:**

Before (31 lines):
- Basic ContentTypeChoiceField
- Integer input for event_object_id
- No fieldsets

After (50 lines):
```python
class EventNotificationForm(GenericForeignKeyFormMixin, NetBoxModelForm):
    generic_fk_fields = [
        ('event', 'event_content_type', 'event_object_id')
    ]

    fieldsets = (
        FieldSet('event_content_type', 'event_choice', name='Event'),
        FieldSet('subject', 'email_from', 'email_received', name='Email Details'),
        FieldSet('email_body', name='Message'),
    )

    # Add: HTMXSelect widget, __init__ for content type filtering
```

### 3. HTMX Data Flow

**User Interaction Sequence:**

1. **Initial Load:**
   - Form renders with event_content_type dropdown (HTMXSelect)
   - Hidden event_object_id field present
   - No event_choice field yet

2. **User Selects Content Type:**
   - User picks "Maintenance" or "Outage"
   - HTMXSelect triggers AJAX request
   - Request includes all form data (event_content_type in GET params)
   - Django re-renders form

3. **Form Re-initialization:**
   - `get_field_value(self, 'event_content_type')` extracts selected type
   - Mixin's `init_generic_choice('event', content_type_id)` called
   - Creates event_choice DynamicModelChoiceField
   - Field renders with searchable dropdown

4. **User Selects Object:**
   - User picks actual Maintenance/Outage from dropdown
   - Value stored in event_choice field

5. **Form Submission:**
   - Mixin's clean() extracts selected object
   - Populates hidden fields: event_content_type, event_object_id
   - Model saves with proper GenericForeignKey values

**Key Integration Points:**
- HTMXSelect widget provided by NetBox core (utilities.forms.widgets)
- Pattern matches NetBox's EventRuleForm implementation
- DynamicModelChoiceField handles AJAX search/filtering

## Implementation Details

### File Changes

**vendor_notification/forms.py** (single file change):

1. **Add GenericForeignKeyFormMixin** (~80 lines):
   - Location: After imports, before existing form classes
   - Methods: init_generic_choice(), clean()
   - Class attribute: generic_fk_fields = []

2. **Refactor ImpactForm** (190 → 60 lines):
   - Change: Inherit from GenericForeignKeyFormMixin
   - Keep: fieldsets, Meta, queryset filtering in __init__
   - Remove: init_event_choice(), init_target_choice(), clean() logic
   - Add: Calls to self.init_generic_choice() in __init__

3. **Update EventNotificationForm** (31 → 50 lines):
   - Change: Inherit from GenericForeignKeyFormMixin
   - Add: generic_fk_fields, fieldsets, HTMXSelect widget config
   - Add: __init__ method for setup
   - Remove: Basic event_object_id field configuration

### Code Metrics

**Line Count:**
- Mixin: ~80 lines
- ImpactForm: ~60 lines (down from ~190)
- EventNotificationForm: ~50 lines (up from ~31)
- **Total:** ~190 lines (vs. ~221 current)
- **Net:** Slight reduction with better organization

**Complexity:**
- Added: Mixin abstraction layer
- Reduced: Form-specific duplication
- Justified by: DRY principle, extensibility for future GenericFK forms

### Backward Compatibility

**No Breaking Changes:**
- No model changes required
- No database migration needed
- Existing Impact records work unchanged
- ImpactForm behavior identical to current implementation
- EventNotificationForm only adds features (no removal)

**Data Safety:**
- GenericForeignKey relationships preserved
- Form validation logic unchanged
- Clean method ensures data integrity

## Testing Considerations

**Manual Testing Required:**
1. **ImpactForm regression:**
   - Create new Impact (select event type → pick event, select target type → pick target)
   - Edit existing Impact (fields pre-populate correctly)
   - Verify HTMX dropdown behavior
   - Test with both Maintenance and Outage events

2. **EventNotificationForm enhancement:**
   - Create new EventNotification with object picker
   - Select Maintenance → verify Maintenance dropdown appears
   - Select Outage → verify Outage dropdown appears
   - Edit existing EventNotification (pre-population works)

3. **Edge cases:**
   - Invalid content type IDs (should fail gracefully)
   - Duplicate GET parameters from HTMX (handled by list logic)
   - Missing content type selection (validation catches it)

**No Automated Tests:**
- Testing HTMX forms requires browser automation
- NetBox plugin test patterns don't typically cover form rendering
- Manual testing sufficient for form UI changes

## Rollout Plan

**Single-Step Deployment:**
1. Implement changes to forms.py
2. Run linting: `ruff format && ruff check --fix`
3. Manual testing in devcontainer
4. Commit changes
5. Deploy to production (no migration required)

**Rollback Plan:**
- Revert single commit if issues arise
- No data migration to rollback
- Forms immediately revert to previous behavior

## Future Enhancements

**Potential Extensions:**
1. Additional forms with GenericFK relationships can inherit the mixin
2. Mixin could support custom queryset filters per field
3. Add validation helpers to mixin for common GFK patterns
4. Extract to NetBox core if pattern proves broadly useful

**Not Included in This Design:**
- Changes to other forms (MaintenanceForm, OutageForm)
- API serializer changes (not needed for UI forms)
- Template modifications (forms handle rendering)
