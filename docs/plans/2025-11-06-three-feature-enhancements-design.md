# Three Feature Enhancements Design

**Date:** 2025-11-06
**Features:**
1. iCal button on calendar page
2. Event history tables on object detail pages
3. Reschedule functionality with self-referencing FK

## Overview

This document describes three independent but complementary enhancements to the vendor notification plugin:

1. **Calendar iCal Integration** - Add subscribe and download buttons to the calendar page
2. **Dynamic Event History** - Show recent and upcoming events on all impacted object detail pages
3. **Maintenance Reschedule** - Track rescheduled events with self-referencing relationships

## Configuration Changes

### New Plugin Settings

Add to `default_settings` in `__init__.py`:

```python
default_settings = {
    "allowed_content_types": DEFAULT_ALLOWED_CONTENT_TYPES,  # Existing
    "ical_past_days_default": 30,  # Existing
    "ical_cache_max_age": 900,  # Existing

    # NEW SETTINGS
    "ical_token_placeholder": "changeme",  # Token placeholder in subscribe URLs
    "event_history_days": 30,  # Days of past events to show in object detail pages
}
```

**Setting descriptions:**
- `ical_token_placeholder`: Default token string shown in subscription URLs (users replace with their actual token)
- `event_history_days`: How many days of past events to include in object detail page history tables

## Feature 1: iCal Button on Calendar Page

### Purpose

Allow users to subscribe to maintenance calendar feeds in external calendar applications (Google Calendar, Outlook, Apple Calendar) or download a one-time snapshot.

### UI Design

Add button group to calendar page header (top-right, before calendar):

```html
<div class="btn-group">
    <button type="button" class="btn btn-primary" id="icalSubscribeBtn">
        <i class="mdi mdi-calendar-sync"></i> Subscribe
    </button>
    <button type="button" class="btn btn-outline-primary" id="icalDownloadBtn">
        <i class="mdi mdi-download"></i> Download
    </button>
</div>
```

### Subscribe Button Behavior

1. Opens modal showing subscription URL
2. URL format: `https://your-netbox/plugins/vendor-notification/ical/maintenances.ics?token={placeholder}`
3. Placeholder comes from `ical_token_placeholder` setting (default: "changeme")
4. Modal includes:
   - Copy to clipboard button
   - Instructions to replace placeholder with user's actual API token
   - Quick guide for subscribing in popular calendar apps

**Modal content:**

```html
<div class="modal-body">
    <p>Use this URL to subscribe to the maintenance calendar in your calendar application:</p>

    <div class="input-group mb-3">
        <input type="text" class="form-control" id="icalSubscribeUrl" readonly>
        <button class="btn btn-outline-secondary" type="button" id="copyUrlBtn">
            <i class="mdi mdi-content-copy"></i> Copy
        </button>
    </div>

    <div class="alert alert-warning">
        <strong>Important:</strong> Replace 'changeme' in the URL with your NetBox API token.
    </div>

    <h6>How to subscribe:</h6>
    <ul>
        <li><strong>Google Calendar:</strong> Settings → Add calendar → From URL</li>
        <li><strong>Outlook:</strong> Calendar → Add calendar → Subscribe from web</li>
        <li><strong>Apple Calendar:</strong> File → New Calendar Subscription</li>
    </ul>
</div>
```

### Download Button Behavior

1. Triggers immediate download of .ics file
2. Uses session authentication (no token needed in URL)
3. Filename: `netbox-maintenance-{YYYY-MM-DD}.ics`
4. Downloads current view (respects date range visible in calendar)

### Implementation

**Template changes** (`calendar.html`):
- Add button group in card header
- Add subscription modal HTML
- Link to updated JavaScript

**JavaScript changes** (`calendar.js`):
- Add modal handling for subscribe button
- Add clipboard copy functionality
- Add download button handler
- Generate subscription URL from current page URL + `/ical/maintenances.ics`

**Backend changes** (`views.py`):
- Enhance `MaintenanceICalView` to detect download parameter
- If `?download=true`, add `Content-Disposition: attachment` header
- Otherwise, use existing inline display with caching

```python
def get(self, request):
    # ... existing authentication and filtering ...

    response = HttpResponse(ical.to_ical(), content_type='text/calendar; charset=utf-8')

    # Handle download vs subscription
    if request.GET.get('download'):
        filename = f'netbox-maintenance-{timezone.now().strftime("%Y-%m-%d")}.ics'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
    else:
        # Existing caching headers for subscription
        response['Cache-Control'] = f'public, max-age={cache_max_age}'
        response['ETag'] = etag

    return response
```

## Feature 2: Event History Tables on Object Detail Pages

### Purpose

Show recent past events and all future events on object detail pages for any model type that can be impacted (circuits, devices, sites, VMs, etc.).

### Dynamic Template Extension Generation

Instead of hardcoding template extensions for each model, generate them dynamically based on `allowed_content_types` setting.

**Location:** `template_content.py` or `__init__.py` `ready()` method

```python
def create_event_history_extensions():
    """
    Dynamically create PluginTemplateExtension classes for all
    allowed_content_types to show event history tables.

    Returns list of extension classes to register.
    """
    from django.contrib.contenttypes.models import ContentType

    allowed_types = get_allowed_content_types()
    extensions = []

    for content_type_str in allowed_types:
        app_label, model = content_type_str.lower().split('.')
        model_name = f'{app_label}.{model}'

        # Create extension class dynamically
        extension_class = type(
            f'{model.capitalize()}EventHistory',
            (PluginTemplateExtension,),
            {
                'model': model_name,
                'left_page': lambda self: render_event_history(self.context['object'])
            }
        )
        extensions.append(extension_class)

    return extensions

def render_event_history(obj):
    """
    Render event history for a given object.
    Queries maintenances and outages that impact this object.
    """
    from django.contrib.contenttypes.models import ContentType
    from django.utils import timezone
    from datetime import timedelta
    from netbox.config import get_config

    config = get_config()
    days = config.PLUGINS_CONFIG.get('vendor_notification', {}).get('event_history_days', 30)
    cutoff_date = timezone.now() - timedelta(days=days)

    obj_ct = ContentType.objects.get_for_model(obj)

    # Get impacts for this object
    impacts = Impact.objects.filter(
        target_content_type=obj_ct,
        target_object_id=obj.pk
    ).select_related('event_content_type').prefetch_related('event')

    # Filter to recent/future events
    maintenances = []
    outages = []

    for impact in impacts:
        event = impact.event
        # Include if: starts after cutoff OR ends in future
        if event.start >= cutoff_date or (event.end and event.end >= timezone.now()):
            if impact.event_content_type.model == 'maintenance':
                maintenances.append({'event': event, 'impact': impact})
            elif impact.event_content_type.model == 'outage':
                outages.append({'event': event, 'impact': impact})

    return render_to_string(
        'vendor_notification/event_history_tabs.html',
        {
            'maintenances': maintenances,
            'outages': outages,
            'object': obj
        }
    )
```

**Registration in `__init__.py`:**

```python
def ready(self):
    from .widgets import load_widgets
    load_widgets()

    # Register dynamic template extensions
    from .template_content import create_event_history_extensions
    global template_extensions
    template_extensions.extend(create_event_history_extensions())
```

### Template Design

**New template: `event_history_tabs.html`**

```html
{% if maintenances or outages %}
<div class="card">
    <div class="card-header">
        <h5 class="card-title">Maintenance & Outage History</h5>
        <div class="card-subtitle text-muted">
            Past {{ event_history_days }} days and future events
        </div>
    </div>
    <div class="card-body">
        <!-- Nav tabs -->
        <ul class="nav nav-tabs mb-3" role="tablist">
            <li class="nav-item">
                <a class="nav-link active" data-bs-toggle="tab" href="#tab-maintenances">
                    Maintenances
                    <span class="badge bg-secondary">{{ maintenances|length }}</span>
                </a>
            </li>
            <li class="nav-item">
                <a class="nav-link" data-bs-toggle="tab" href="#tab-outages">
                    Outages
                    <span class="badge bg-secondary">{{ outages|length }}</span>
                </a>
            </li>
        </ul>

        <!-- Tab content -->
        <div class="tab-content">
            <div id="tab-maintenances" class="tab-pane active">
                {% if maintenances %}
                    {% include 'vendor_notification/event_history_table.html' with events=maintenances %}
                {% else %}
                    <p class="text-muted">No maintenances in this period</p>
                {% endif %}
            </div>
            <div id="tab-outages" class="tab-pane">
                {% if outages %}
                    {% include 'vendor_notification/event_history_table.html' with events=outages %}
                {% else %}
                    <p class="text-muted">No outages in this period</p>
                {% endif %}
            </div>
        </div>
    </div>
</div>
{% endif %}
```

**New template: `event_history_table.html`**

```html
<div class="table-responsive">
    <table class="table table-hover">
        <thead>
            <tr>
                <th>Event</th>
                <th>Provider</th>
                <th>Status</th>
                <th>Start</th>
                <th>End</th>
                <th>Impact</th>
            </tr>
        </thead>
        <tbody>
            {% for item in events %}
            <tr>
                <td>
                    <a href="{{ item.event.get_absolute_url }}">{{ item.event.name }}</a>
                </td>
                <td>
                    <a href="{{ item.event.provider.get_absolute_url }}">
                        {{ item.event.provider }}
                    </a>
                </td>
                <td>
                    <span class="badge bg-{{ item.event.get_status_color }}">
                        {{ item.event.get_status_display }}
                    </span>
                </td>
                <td>{{ item.event.start|date:"Y-m-d H:i" }}</td>
                <td>
                    {% if item.event.end %}
                        {{ item.event.end|date:"Y-m-d H:i" }}
                    {% else %}
                        <em>Ongoing</em>
                    {% endif %}
                </td>
                <td>
                    <span class="badge bg-{{ item.impact.get_impact_color }}">
                        {{ item.impact.get_impact_display }}
                    </span>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
```

### Querying Logic

Events are included if they meet ANY of these criteria:
1. Start date is within past N days (configurable via `event_history_days`)
2. End date is in the future (show all upcoming events regardless of start)

This ensures:
- Long-running events that started before the cutoff are still shown
- All future events are visible
- Old completed events eventually fall off

## Feature 3: Reschedule Functionality

### Purpose

Track rescheduled maintenance events with proper lineage. When a maintenance is rescheduled, create a new event that references the original, and automatically update the original's status.

### Model Changes

**Add to `Maintenance` model in `models.py`:**

```python
class Maintenance(BaseEvent):
    # ... existing fields ...

    replaces = models.ForeignKey(
        to='self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='replaced_by_maintenance',
        verbose_name='Replaces Maintenance',
        help_text='The maintenance event that this event replaces (for rescheduled events)'
    )
```

**Migration required:** Yes - add nullable ForeignKey field

### Relationship Direction

- **Forward**: New maintenance points to old via `replaces` field
- **Reverse**: Old maintenance accessed via `replaced_by_maintenance` relation
- **Chain support**: Can track multiple reschedules (A→B→C→D)

Example queries:
```python
# What did this maintenance replace?
new_maintenance.replaces  # Returns old Maintenance or None

# What replaced this maintenance?
old_maintenance.replaced_by_maintenance.first()  # Returns new Maintenance or None
```

### Reschedule Button

**Location:** Maintenance detail page, in action buttons area (near Edit/Delete)

**Visibility conditions:**
- User has `vendor_notification.add_maintenance` permission
- Maintenance status is NOT "COMPLETED" or "CANCELLED"

**Button HTML:**

```html
{% if perms.vendor_notification.add_maintenance and object.status not in ['COMPLETED', 'CANCELLED'] %}
<a href="{% url 'plugins:vendor_notification:maintenance_reschedule' pk=object.pk %}"
   class="btn btn-warning">
    <i class="mdi mdi-calendar-refresh"></i> Reschedule
</a>
{% endif %}
```

### Reschedule View

**New view in `views.py`:**

```python
class MaintenanceRescheduleView(generic.ObjectEditView):
    """
    Clone a maintenance and mark it as rescheduled.

    Workflow:
    1. Pre-fill form with existing maintenance data
    2. Set 'replaces' field to original maintenance
    3. On save, update original maintenance status to 'RE-SCHEDULED'
    """
    queryset = models.Maintenance.objects.all()
    form = forms.MaintenanceForm
    template_name = 'vendor_notification/maintenance_reschedule.html'

    def get_object(self, **kwargs):
        """
        Return None to create new object, but store original for cloning.
        """
        # Get original maintenance
        self.original_maintenance = get_object_or_404(
            models.Maintenance,
            pk=self.kwargs['pk']
        )
        # Return None to trigger create mode
        return None

    def get_initial(self):
        """
        Pre-fill form with original maintenance data.
        """
        initial = super().get_initial()

        # Clone all fields from original
        for field in self.original_maintenance._meta.fields:
            if field.name not in ['id', 'created', 'last_updated']:
                initial[field.name] = getattr(self.original_maintenance, field.name)

        # Set replaces to original
        initial['replaces'] = self.original_maintenance.pk

        # Reset status to TENTATIVE
        initial['status'] = 'TENTATIVE'

        return initial

    def form_valid(self, form):
        """
        Save new maintenance and update original status.
        """
        response = super().form_valid(form)

        # Update original maintenance status
        self.original_maintenance.status = 'RE-SCHEDULED'
        self.original_maintenance.save()

        return response

    def get_extra_context(self, request, instance):
        context = super().get_extra_context(request, instance)
        context['original_maintenance'] = self.original_maintenance
        return context
```

**New URL in `urls.py`:**

```python
path(
    'maintenance/<int:pk>/reschedule/',
    views.MaintenanceRescheduleView.as_view(),
    name='maintenance_reschedule',
),
```

### Reschedule Template

**New template: `maintenance_reschedule.html`**

Extends the standard edit form template but adds context about the reschedule operation:

```html
{% extends 'generic/object_edit.html' %}

{% block form %}
<div class="alert alert-info mb-3">
    <h5 class="alert-heading">
        <i class="mdi mdi-calendar-refresh"></i> Rescheduling Maintenance
    </h5>
    <p class="mb-0">
        You are creating a new maintenance that replaces:
        <a href="{{ original_maintenance.get_absolute_url }}" target="_blank">
            {{ original_maintenance.name }}
        </a>
    </p>
    <p class="mb-0 mt-2">
        <small>
            The original maintenance will be automatically marked as "RE-SCHEDULED" when you save.
        </small>
    </p>
</div>

{{ block.super }}
{% endblock %}
```

### Form Changes

**Update `MaintenanceForm` in `forms.py`:**

```python
class MaintenanceForm(NetBoxModelForm):
    # ... existing fields ...

    replaces = DynamicModelChoiceField(
        queryset=Maintenance.objects.all(),
        required=False,
        label='Replaces',
        help_text='The maintenance this event replaces',
        widget=HTMXSelect()
    )

    class Meta:
        model = Maintenance
        fields = [
            'name', 'provider', 'status', 'start', 'end',
            'original_timezone', 'summary', 'internal_ticket',
            'acknowledged', 'comments', 'replaces', 'tags'
        ]
```

### Display Replacement Chain

On maintenance detail page, show replacement relationship context:

**Template changes to `maintenance.html` (or detail template):**

```html
{% if object.replaces %}
<div class="alert alert-warning">
    <strong>This maintenance replaces:</strong>
    <a href="{{ object.replaces.get_absolute_url }}">{{ object.replaces.name }}</a>
    ({{ object.replaces.start|date:"Y-m-d H:i" }})
</div>
{% endif %}

{% if object.replaced_by_maintenance.exists %}
<div class="alert alert-info">
    <strong>This maintenance was rescheduled:</strong>
    {% for replacement in object.replaced_by_maintenance.all %}
        <a href="{{ replacement.get_absolute_url }}">{{ replacement.name }}</a>
        ({{ replacement.start|date:"Y-m-d H:i" }})
    {% endfor %}
</div>
{% endif %}
```

## Migration Strategy

### Order of Implementation

1. **Feature 3 (Reschedule)** - Requires database migration, implement first
2. **Feature 2 (Event History)** - No migrations, depends on template infrastructure
3. **Feature 1 (iCal Button)** - Pure frontend, implement last

### Database Migration

Create migration for `replaces` field:

```bash
make makemigrations
make migrate
```

Expected migration:

```python
operations = [
    migrations.AddField(
        model_name='maintenance',
        name='replaces',
        field=models.ForeignKey(
            blank=True,
            null=True,
            on_delete=django.db.models.deletion.SET_NULL,
            related_name='replaced_by_maintenance',
            to='vendor_notification.maintenance'
        ),
    ),
]
```

### Backward Compatibility

All three features are additive and backward compatible:
- New settings have defaults
- New model field is nullable
- Existing templates continue to work
- No breaking API changes

## Testing Considerations

### Feature 1: iCal Button
- Test subscribe URL generation with custom `ical_token_placeholder`
- Test download with session auth
- Test clipboard copy functionality
- Test modal display/dismiss

### Feature 2: Event History
- Test dynamic extension generation for various content types
- Test date filtering (past N days + future events)
- Test tab switching between maintenances and outages
- Test empty state display
- Test with objects that have no impacts

### Feature 3: Reschedule
- Test reschedule button visibility conditions
- Test form pre-population
- Test original status update to "RE-SCHEDULED"
- Test replacement chain display
- Test with already-rescheduled events
- Test permissions

## Documentation Updates

### README.md

Add to configuration section:

```markdown
#### iCal Feed Settings

- `ical_token_placeholder`: Default token string in subscribe URLs (default: `"changeme"`)
- `ical_cache_max_age`: Cache duration in seconds (default: `900`)
- `ical_past_days_default`: Days of past events in feed (default: `30`)

#### Event History Settings

- `event_history_days`: Days of past events to show on object detail pages (default: `30`)
```

### User Guide

Add new sections:
1. "Subscribing to Calendar Feeds" - How to use the iCal button
2. "Viewing Object Event History" - Understanding the event history tables
3. "Rescheduling Maintenance Events" - How to use the reschedule feature

## Future Enhancements

Potential future additions (not in scope for this design):

- Allow reschedule of outages (currently maintenances only)
- Add "View Replacement Chain" page showing full lineage
- Add filtering to event history tables (by status, date range)
- Add export button for event history (CSV/Excel)
- Add calendar feed for individual objects (per-circuit subscriptions)
- Add notification when rescheduled event approaches
