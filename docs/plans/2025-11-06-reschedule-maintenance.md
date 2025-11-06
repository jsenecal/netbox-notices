# Reschedule Maintenance Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add reschedule functionality that clones a maintenance event with a self-referencing FK to track replacement chain, automatically updating the original's status to "RE-SCHEDULED".

**Architecture:** Add nullable self-referencing ForeignKey `replaces` to Maintenance model. Create MaintenanceRescheduleView that extends ObjectEditView, pre-fills form with original data, and updates original status on save. Display replacement chain context on detail pages.

**Tech Stack:** Django models, NetBox generic views, Django templates, pytest

---

## Task 1: Add Model Field and Migration

**Files:**
- Modify: `vendor_notification/models.py:65-136`
- Create: `vendor_notification/migrations/000X_maintenance_replaces.py` (auto-generated)
- Test: `tests/test_reschedule_model.py` (new file)

**Step 1: Write failing test for model field**

Create file `tests/test_reschedule_model.py`:

```python
import pytest
from django.utils import timezone
from datetime import timedelta

from circuits.models import Provider
from vendor_notification.models import Maintenance


@pytest.mark.django_db
class TestMaintenanceReplaces:
    """Test the self-referencing replaces field on Maintenance model."""

    def test_replaces_field_exists(self):
        """Test that Maintenance model has replaces field."""
        assert hasattr(Maintenance, 'replaces')

    def test_replaces_field_is_nullable(self):
        """Test that replaces field can be null."""
        provider = Provider.objects.create(name="Test Provider", slug="test-provider")
        maintenance = Maintenance.objects.create(
            name="MAINT-001",
            summary="Test maintenance",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=2),
            status="CONFIRMED",
            replaces=None  # Should not raise error
        )
        assert maintenance.replaces is None

    def test_replaces_references_maintenance(self):
        """Test that replaces field can reference another maintenance."""
        provider = Provider.objects.create(name="Test Provider", slug="test-provider")

        original = Maintenance.objects.create(
            name="MAINT-001",
            summary="Original maintenance",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=2),
            status="CONFIRMED"
        )

        rescheduled = Maintenance.objects.create(
            name="MAINT-002",
            summary="Rescheduled maintenance",
            provider=provider,
            start=timezone.now() + timedelta(days=1),
            end=timezone.now() + timedelta(days=1, hours=2),
            status="CONFIRMED",
            replaces=original
        )

        assert rescheduled.replaces == original

    def test_reverse_relation_replaced_by_maintenance(self):
        """Test that replaced maintenance has reverse relation."""
        provider = Provider.objects.create(name="Test Provider", slug="test-provider")

        original = Maintenance.objects.create(
            name="MAINT-001",
            summary="Original maintenance",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=2),
            status="CONFIRMED"
        )

        rescheduled = Maintenance.objects.create(
            name="MAINT-002",
            summary="Rescheduled maintenance",
            provider=provider,
            start=timezone.now() + timedelta(days=1),
            end=timezone.now() + timedelta(days=1, hours=2),
            status="CONFIRMED",
            replaces=original
        )

        # Access reverse relation
        replacements = original.replaced_by_maintenance.all()
        assert rescheduled in replacements

    def test_replaces_on_delete_set_null(self):
        """Test that deleting original maintenance sets replaces to null."""
        provider = Provider.objects.create(name="Test Provider", slug="test-provider")

        original = Maintenance.objects.create(
            name="MAINT-001",
            summary="Original maintenance",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=2),
            status="CONFIRMED"
        )

        rescheduled = Maintenance.objects.create(
            name="MAINT-002",
            summary="Rescheduled maintenance",
            provider=provider,
            start=timezone.now() + timedelta(days=1),
            end=timezone.now() + timedelta(days=1, hours=2),
            status="CONFIRMED",
            replaces=original
        )

        original_id = original.pk
        original.delete()

        # Refresh from database
        rescheduled.refresh_from_db()
        assert rescheduled.replaces is None
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd /opt/netbox-vendor-notification/.worktrees/feature-reschedule
PYTHONPATH=/opt/netbox/netbox /opt/netbox/venv/bin/pytest tests/test_reschedule_model.py -v
```

Expected output: Multiple failures because `replaces` field doesn't exist

**Step 3: Add replaces field to Maintenance model**

Edit `vendor_notification/models.py`, add after line 89 (after impacts field):

```python
    # Reverse relation for GenericForeignKey in Impact model
    impacts = GenericRelation(
        to="vendor_notification.Impact",
        content_type_field="event_content_type",
        object_id_field="event_object_id",
        related_query_name="maintenance",
    )

    # Self-referencing FK for rescheduled maintenance tracking
    replaces = models.ForeignKey(
        to='self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='replaced_by_maintenance',
        verbose_name='Replaces Maintenance',
        help_text='The maintenance event that this event replaces (for rescheduled events)'
    )

    class Meta:
        ordering = ("-created",)
```

**Step 4: Create migration**

Run:
```bash
cd /opt/netbox-vendor-notification/.worktrees/feature-reschedule
PYTHONPATH=/opt/netbox/netbox DJANGO_SETTINGS_MODULE=netbox.settings /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py makemigrations vendor_notification
```

Expected output: Creates migration file like `vendor_notification/migrations/0007_maintenance_replaces.py`

**Step 5: Apply migration**

Run:
```bash
PYTHONPATH=/opt/netbox/netbox DJANGO_SETTINGS_MODULE=netbox.settings /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py migrate vendor_notification
```

Expected output: Migration applied successfully

**Step 6: Run tests to verify they pass**

Run:
```bash
PYTHONPATH=/opt/netbox/netbox /opt/netbox/venv/bin/pytest tests/test_reschedule_model.py -v
```

Expected output: All 5 tests pass

**Step 7: Commit**

```bash
git add vendor_notification/models.py vendor_notification/migrations/ tests/test_reschedule_model.py
git commit -m "feat: add replaces field to Maintenance model

Add self-referencing ForeignKey to track rescheduled maintenance events.
Includes database migration and comprehensive model tests."
```

---

## Task 2: Update MaintenanceForm

**Files:**
- Modify: `vendor_notification/forms.py:104-184`
- Test: `tests/test_reschedule_form.py` (new file)

**Step 1: Write failing test for form field**

Create file `tests/test_reschedule_form.py`:

```python
import pytest
from django.utils import timezone
from datetime import timedelta

from circuits.models import Provider
from vendor_notification.models import Maintenance
from vendor_notification.forms import MaintenanceForm


@pytest.mark.django_db
class TestMaintenanceFormReplaces:
    """Test that MaintenanceForm includes replaces field."""

    def test_replaces_field_in_form(self):
        """Test that form includes replaces field."""
        form = MaintenanceForm()
        assert 'replaces' in form.fields

    def test_replaces_field_is_optional(self):
        """Test that replaces field is not required."""
        form = MaintenanceForm()
        assert form.fields['replaces'].required is False

    def test_form_saves_with_replaces(self):
        """Test that form correctly saves replaces relationship."""
        provider = Provider.objects.create(name="Test Provider", slug="test-provider")

        original = Maintenance.objects.create(
            name="MAINT-001",
            summary="Original maintenance",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=2),
            status="CONFIRMED"
        )

        form_data = {
            'name': 'MAINT-002',
            'summary': 'Rescheduled maintenance',
            'provider': provider.pk,
            'start': timezone.now() + timedelta(days=1),
            'end': timezone.now() + timedelta(days=1, hours=2),
            'status': 'CONFIRMED',
            'replaces': original.pk,
        }

        form = MaintenanceForm(data=form_data)
        assert form.is_valid(), form.errors

        maintenance = form.save()
        assert maintenance.replaces == original

    def test_form_saves_without_replaces(self):
        """Test that form works when replaces is not provided."""
        provider = Provider.objects.create(name="Test Provider", slug="test-provider")

        form_data = {
            'name': 'MAINT-001',
            'summary': 'New maintenance',
            'provider': provider.pk,
            'start': timezone.now(),
            'end': timezone.now() + timedelta(hours=2),
            'status': 'CONFIRMED',
        }

        form = MaintenanceForm(data=form_data)
        assert form.is_valid(), form.errors

        maintenance = form.save()
        assert maintenance.replaces is None
```

**Step 2: Run test to verify it fails**

Run:
```bash
PYTHONPATH=/opt/netbox/netbox /opt/netbox/venv/bin/pytest tests/test_reschedule_form.py::TestMaintenanceFormReplaces::test_replaces_field_in_form -v
```

Expected output: FAILED - 'replaces' not in form.fields

**Step 3: Add replaces field to MaintenanceForm**

Edit `vendor_notification/forms.py:104-129`:

```python
class MaintenanceForm(NetBoxModelForm):
    provider = DynamicModelChoiceField(queryset=Provider.objects.all())

    replaces = DynamicModelChoiceField(
        queryset=Maintenance.objects.all(),
        required=False,
        label='Replaces',
        help_text='The maintenance this event replaces (for rescheduled events)'
    )

    original_timezone = forms.ChoiceField(
        choices=TimeZoneChoices,
        required=False,
        label="Timezone",
        help_text="Timezone for the start/end times (converted to system timezone on save)",
    )

    class Meta:
        model = Maintenance
        fields = (
            "name",
            "summary",
            "status",
            "provider",
            "start",
            "end",
            "original_timezone",
            "internal_ticket",
            "acknowledged",
            "comments",
            "replaces",  # Add here
            "tags",
        )
        widgets = {"start": DateTimePicker(), "end": DateTimePicker()}
```

**Step 4: Run tests to verify they pass**

Run:
```bash
PYTHONPATH=/opt/netbox/netbox /opt/netbox/venv/bin/pytest tests/test_reschedule_form.py -v
```

Expected output: All 4 tests pass

**Step 5: Commit**

```bash
git add vendor_notification/forms.py tests/test_reschedule_form.py
git commit -m "feat: add replaces field to MaintenanceForm

Allow users to specify which maintenance an event replaces.
Field is optional and uses DynamicModelChoiceField for object selection."
```

---

## Task 3: Create MaintenanceRescheduleView

**Files:**
- Modify: `vendor_notification/views.py:50-57`
- Test: `tests/test_reschedule_view.py` (new file)

**Step 1: Write failing test for reschedule view**

Create file `tests/test_reschedule_view.py`:

```python
import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from circuits.models import Provider
from vendor_notification.models import Maintenance

User = get_user_model()


@pytest.mark.django_db
class TestMaintenanceRescheduleView:
    """Test the MaintenanceRescheduleView."""

    @pytest.fixture
    def user(self):
        """Create a superuser for testing."""
        return User.objects.create_superuser(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    @pytest.fixture
    def client(self, user):
        """Create authenticated client."""
        client = Client()
        client.force_login(user)
        return client

    @pytest.fixture
    def provider(self):
        """Create a test provider."""
        return Provider.objects.create(name="Test Provider", slug="test-provider")

    @pytest.fixture
    def original_maintenance(self, provider):
        """Create original maintenance to be rescheduled."""
        return Maintenance.objects.create(
            name="MAINT-001",
            summary="Original maintenance",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=2),
            status="CONFIRMED",
            internal_ticket="TICKET-123",
            comments="Original comments"
        )

    def test_reschedule_url_exists(self, client, original_maintenance):
        """Test that reschedule URL is accessible."""
        url = reverse('plugins:vendor_notification:maintenance_reschedule',
                     args=[original_maintenance.pk])
        response = client.get(url)
        assert response.status_code == 200

    def test_reschedule_form_prefilled(self, client, original_maintenance):
        """Test that reschedule form is pre-filled with original data."""
        url = reverse('plugins:vendor_notification:maintenance_reschedule',
                     args=[original_maintenance.pk])
        response = client.get(url)

        # Check that form has initial values from original
        form = response.context['form']
        assert form.initial['name'] == original_maintenance.name
        assert form.initial['summary'] == original_maintenance.summary
        assert form.initial['provider'] == original_maintenance.provider.pk
        assert form.initial['internal_ticket'] == original_maintenance.internal_ticket
        assert form.initial['comments'] == original_maintenance.comments

    def test_reschedule_sets_replaces_field(self, client, original_maintenance):
        """Test that reschedule form sets replaces to original."""
        url = reverse('plugins:vendor_notification:maintenance_reschedule',
                     args=[original_maintenance.pk])
        response = client.get(url)

        form = response.context['form']
        assert form.initial['replaces'] == original_maintenance.pk

    def test_reschedule_resets_status_to_tentative(self, client, original_maintenance):
        """Test that new maintenance starts with TENTATIVE status."""
        url = reverse('plugins:vendor_notification:maintenance_reschedule',
                     args=[original_maintenance.pk])
        response = client.get(url)

        form = response.context['form']
        assert form.initial['status'] == 'TENTATIVE'

    def test_reschedule_post_creates_new_maintenance(self, client, original_maintenance, provider):
        """Test that posting reschedule form creates new maintenance."""
        url = reverse('plugins:vendor_notification:maintenance_reschedule',
                     args=[original_maintenance.pk])

        new_start = timezone.now() + timedelta(days=1)
        new_end = new_start + timedelta(hours=2)

        data = {
            'name': 'MAINT-002',
            'summary': 'Rescheduled maintenance',
            'provider': provider.pk,
            'start': new_start.strftime('%Y-%m-%d %H:%M:%S'),
            'end': new_end.strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'TENTATIVE',
            'replaces': original_maintenance.pk,
        }

        response = client.post(url, data)

        # Should redirect to new maintenance
        assert response.status_code == 302

        # Check new maintenance was created
        new_maintenance = Maintenance.objects.get(name='MAINT-002')
        assert new_maintenance.replaces == original_maintenance

    def test_reschedule_updates_original_status(self, client, original_maintenance, provider):
        """Test that rescheduling updates original status to RE-SCHEDULED."""
        url = reverse('plugins:vendor_notification:maintenance_reschedule',
                     args=[original_maintenance.pk])

        new_start = timezone.now() + timedelta(days=1)
        new_end = new_start + timedelta(hours=2)

        data = {
            'name': 'MAINT-002',
            'summary': 'Rescheduled maintenance',
            'provider': provider.pk,
            'start': new_start.strftime('%Y-%m-%d %H:%M:%S'),
            'end': new_end.strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'TENTATIVE',
            'replaces': original_maintenance.pk,
        }

        client.post(url, data)

        # Refresh original from database
        original_maintenance.refresh_from_db()
        assert original_maintenance.status == 'RE-SCHEDULED'

    def test_reschedule_requires_permission(self):
        """Test that reschedule requires add_maintenance permission."""
        # Create user without permissions
        user = User.objects.create_user(username='noauth', password='test')
        client = Client()
        client.force_login(user)

        provider = Provider.objects.create(name="Test Provider", slug="test-provider")
        maintenance = Maintenance.objects.create(
            name="MAINT-001",
            summary="Test",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=2),
            status="CONFIRMED"
        )

        url = reverse('plugins:vendor_notification:maintenance_reschedule', args=[maintenance.pk])
        response = client.get(url)

        # Should be forbidden or redirect to login
        assert response.status_code in [302, 403]
```

**Step 2: Run test to verify it fails**

Run:
```bash
PYTHONPATH=/opt/netbox/netbox /opt/netbox/venv/bin/pytest tests/test_reschedule_view.py::TestMaintenanceRescheduleView::test_reschedule_url_exists -v
```

Expected output: FAILED - NoReverseMatch for 'maintenance_reschedule'

**Step 3: Create MaintenanceRescheduleView**

Edit `vendor_notification/views.py`, add after MaintenanceDeleteView (after line 56):

```python
class MaintenanceDeleteView(generic.ObjectDeleteView):
    queryset = models.Maintenance.objects.all()


class MaintenanceRescheduleView(generic.ObjectEditView):
    """
    Clone a maintenance and mark original as rescheduled.

    Workflow:
    1. Pre-fill form with existing maintenance data
    2. Set 'replaces' field to original maintenance
    3. On save, update original maintenance status to 'RE-SCHEDULED'
    """
    queryset = models.Maintenance.objects.all()
    form = forms.MaintenanceForm

    def get_object(self, **kwargs):
        """
        Return None to create new object, but store original for cloning.
        """
        # Get original maintenance via URL parameter
        from django.shortcuts import get_object_or_404
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

        # Clone all fields from original (except auto fields)
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
        """Add original maintenance to context."""
        context = super().get_extra_context(request, instance)
        context['original_maintenance'] = self.original_maintenance
        return context


# Outage Views
```

**Step 4: Add URL route**

Edit `vendor_notification/urls.py`, add after maintenance_delete route (after line 31):

```python
    path(
        "maintenance/<int:pk>/delete/",
        views.MaintenanceDeleteView.as_view(),
        name="maintenance_delete",
    ),
    path(
        "maintenance/<int:pk>/reschedule/",
        views.MaintenanceRescheduleView.as_view(),
        name="maintenance_reschedule",
    ),
    path(
        "maintenance/<int:pk>/changelog/",
        ObjectChangeLogView.as_view(),
        name="maintenance_changelog",
        kwargs={"model": models.Maintenance},
    ),
```

**Step 5: Run tests to verify they pass**

Run:
```bash
PYTHONPATH=/opt/netbox/netbox /opt/netbox/venv/bin/pytest tests/test_reschedule_view.py -v
```

Expected output: All 8 tests pass

**Step 6: Commit**

```bash
git add vendor_notification/views.py vendor_notification/urls.py tests/test_reschedule_view.py
git commit -m "feat: add MaintenanceRescheduleView

Create view that clones maintenance with pre-filled data,
sets replaces field, and updates original status to RE-SCHEDULED.
Includes URL route and comprehensive view tests."
```

---

## Task 4: Add Reschedule Button to Detail Page

**Files:**
- Modify: `vendor_notification/templates/vendor_notification/maintenance.html`
- Test: Manual testing (template rendering)

**Step 1: Read current maintenance template**

Run:
```bash
cat vendor_notification/templates/vendor_notification/maintenance.html
```

**Step 2: Add reschedule button**

NetBox uses a standard object detail template pattern. The reschedule button should appear in the action buttons area. Edit `vendor_notification/templates/vendor_notification/maintenance.html`:

If the template extends `generic/object.html` or similar, add a `buttons` block:

```django
{% extends 'generic/object.html' %}

{% block buttons %}
    {{ block.super }}

    {% if perms.vendor_notification.add_maintenance and object.status not in 'COMPLETED,CANCELLED' %}
    <a href="{% url 'plugins:vendor_notification:maintenance_reschedule' pk=object.pk %}"
       class="btn btn-warning">
        <i class="mdi mdi-calendar-refresh"></i> Reschedule
    </a>
    {% endif %}
{% endblock %}
```

If template structure is different, place button near edit/delete buttons with same permissions check.

**Step 3: Manual test**

Run NetBox dev server:
```bash
cd /opt/netbox/netbox
python manage.py runserver 0.0.0.0:8000
```

Navigate to a maintenance detail page and verify:
- Reschedule button appears
- Button hidden for COMPLETED/CANCELLED events
- Button hidden for users without add_maintenance permission
- Clicking button opens form with pre-filled data

**Step 4: Commit**

```bash
git add vendor_notification/templates/vendor_notification/maintenance.html
git commit -m "feat: add reschedule button to maintenance detail

Add button that triggers MaintenanceRescheduleView.
Button hidden for completed/cancelled events and users without permission."
```

---

## Task 5: Display Replacement Chain

**Files:**
- Modify: `vendor_notification/templates/vendor_notification/maintenance.html`
- Test: Manual testing

**Step 1: Add replacement chain alerts**

Edit `vendor_notification/templates/vendor_notification/maintenance.html`, add after page header/title but before main content:

```django
{% block content %}
    {# Show if this maintenance replaces another #}
    {% if object.replaces %}
    <div class="alert alert-warning mb-3">
        <i class="mdi mdi-alert"></i>
        <strong>This maintenance replaces:</strong>
        <a href="{{ object.replaces.get_absolute_url }}">{{ object.replaces.name }}</a>
        ({{ object.replaces.start|date:"Y-m-d H:i" }})
    </div>
    {% endif %}

    {# Show if this maintenance was rescheduled #}
    {% if object.replaced_by_maintenance.exists %}
    <div class="alert alert-info mb-3">
        <i class="mdi mdi-information"></i>
        <strong>This maintenance was rescheduled:</strong>
        {% for replacement in object.replaced_by_maintenance.all %}
            <a href="{{ replacement.get_absolute_url }}">{{ replacement.name }}</a>
            ({{ replacement.start|date:"Y-m-d H:i" }}){% if not forloop.last %}, {% endif %}
        {% endfor %}
    </div>
    {% endif %}

    {{ block.super }}
{% endblock %}
```

**Step 2: Manual test**

Run NetBox dev server and create test scenario:
1. Create original maintenance
2. Reschedule it
3. View original - should show "was rescheduled" alert
4. View new maintenance - should show "replaces" alert

**Step 3: Commit**

```bash
git add vendor_notification/templates/vendor_notification/maintenance.html
git commit -m "feat: display replacement chain in maintenance detail

Show alerts when maintenance replaces another or was rescheduled.
Includes links to related maintenance events."
```

---

## Task 6: Create Reschedule Template

**Files:**
- Create: `vendor_notification/templates/vendor_notification/maintenance_reschedule.html`
- Test: Manual testing

**Step 1: Create reschedule template**

Create file `vendor_notification/templates/vendor_notification/maintenance_reschedule.html`:

```django
{% extends 'generic/object_edit.html' %}

{% block form %}
<div class="alert alert-info mb-3">
    <h5 class="alert-heading">
        <i class="mdi mdi-calendar-refresh"></i> Rescheduling Maintenance
    </h5>
    <p class="mb-0">
        You are creating a new maintenance that replaces:
        <a href="{{ original_maintenance.get_absolute_url }}" target="_blank" class="alert-link">
            {{ original_maintenance.name }}
        </a>
    </p>
    <p class="mb-0 mt-2">
        <small class="text-muted">
            The original maintenance will be automatically marked as "RE-SCHEDULED" when you save.
        </small>
    </p>
</div>

{{ block.super }}
{% endblock %}
```

**Step 2: Manual test**

Run NetBox dev server:
1. Click reschedule button on a maintenance
2. Verify info alert appears at top of form
3. Verify alert shows original maintenance name with link
4. Verify form fields are pre-filled

**Step 3: Commit**

```bash
git add vendor_notification/templates/vendor_notification/maintenance_reschedule.html
git commit -m "feat: create reschedule template with context alert

Add custom template extending object_edit with info alert
showing which maintenance is being replaced."
```

---

## Task 7: Add API Serializer Support

**Files:**
- Modify: `vendor_notification/api/serializers.py`
- Test: `tests/test_reschedule_api.py` (new file)

**Step 1: Write failing test for API**

Create file `tests/test_reschedule_api.py`:

```python
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient

from circuits.models import Provider
from vendor_notification.models import Maintenance

User = get_user_model()


@pytest.mark.django_db
class TestMaintenanceRescheduleAPI:
    """Test API support for replaces field."""

    @pytest.fixture
    def user(self):
        """Create superuser for API testing."""
        return User.objects.create_superuser(
            username='apiuser',
            email='api@example.com',
            password='apipass123'
        )

    @pytest.fixture
    def api_client(self, user):
        """Create authenticated API client."""
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    @pytest.fixture
    def provider(self):
        """Create test provider."""
        return Provider.objects.create(name="Test Provider", slug="test-provider")

    def test_api_includes_replaces_field(self, api_client, provider):
        """Test that API response includes replaces field."""
        maintenance = Maintenance.objects.create(
            name="MAINT-001",
            summary="Test",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=2),
            status="CONFIRMED"
        )

        url = f'/api/plugins/vendor-notification/maintenances/{maintenance.pk}/'
        response = api_client.get(url)

        assert response.status_code == 200
        assert 'replaces' in response.data

    def test_api_create_with_replaces(self, api_client, provider):
        """Test creating maintenance with replaces via API."""
        original = Maintenance.objects.create(
            name="MAINT-001",
            summary="Original",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=2),
            status="CONFIRMED"
        )

        url = '/api/plugins/vendor-notification/maintenances/'
        data = {
            'name': 'MAINT-002',
            'summary': 'Rescheduled',
            'provider': provider.pk,
            'start': (timezone.now() + timedelta(days=1)).isoformat(),
            'end': (timezone.now() + timedelta(days=1, hours=2)).isoformat(),
            'status': 'TENTATIVE',
            'replaces': original.pk
        }

        response = api_client.post(url, data, format='json')

        assert response.status_code == 201
        assert response.data['replaces'] == original.pk

        # Verify in database
        new_maintenance = Maintenance.objects.get(name='MAINT-002')
        assert new_maintenance.replaces == original
```

**Step 2: Run test to verify it fails**

Run:
```bash
PYTHONPATH=/opt/netbox/netbox /opt/netbox/venv/bin/pytest tests/test_reschedule_api.py::TestMaintenanceRescheduleAPI::test_api_includes_replaces_field -v
```

Expected output: FAILED - 'replaces' not in response.data

**Step 3: Add replaces to MaintenanceSerializer**

Edit `vendor_notification/api/serializers.py`, locate `MaintenanceSerializer` and add `replaces` to fields:

```python
class MaintenanceSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name="plugins-api:vendor_notification-api:maintenance-detail"
    )
    provider = ProviderSerializer(nested=True)

    # Add nested serializer for replaces
    replaces = serializers.PrimaryKeyRelatedField(
        queryset=Maintenance.objects.all(),
        required=False,
        allow_null=True
    )

    class Meta:
        model = Maintenance
        fields = (
            "id",
            "url",
            "display",
            "name",
            "provider",
            "summary",
            "status",
            "start",
            "end",
            "original_timezone",
            "internal_ticket",
            "acknowledged",
            "comments",
            "replaces",  # Add here
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )
```

**Step 4: Run tests to verify they pass**

Run:
```bash
PYTHONPATH=/opt/netbox/netbox /opt/netbox/venv/bin/pytest tests/test_reschedule_api.py -v
```

Expected output: All 2 tests pass

**Step 5: Commit**

```bash
git add vendor_notification/api/serializers.py tests/test_reschedule_api.py
git commit -m "feat: add replaces field to API serializer

Enable API clients to create/update maintenance with replaces relationship.
Includes API integration tests."
```

---

## Task 8: Update FilterSet (Optional)

**Files:**
- Modify: `vendor_notification/filtersets.py`
- Test: Manual testing

**Step 1: Add replaces filter**

Edit `vendor_notification/filtersets.py`, add to `MaintenanceFilterSet`:

```python
class MaintenanceFilterSet(NetBoxModelFilterSet):
    # ... existing filters ...

    replaces_id = django_filters.ModelMultipleChoiceFilter(
        queryset=Maintenance.objects.all(),
        label='Replaces (ID)',
    )

    has_replaces = django_filters.BooleanFilter(
        method='filter_has_replaces',
        label='Has replacement',
    )

    def filter_has_replaces(self, queryset, name, value):
        """Filter maintenances that have been rescheduled."""
        if value:
            return queryset.exclude(replaced_by_maintenance=None)
        return queryset.filter(replaced_by_maintenance=None)
```

**Step 2: Test via UI**

Navigate to maintenance list page and test filtering:
- Filter by "replaces ID"
- Filter by "has replacement"

**Step 3: Commit**

```bash
git add vendor_notification/filtersets.py
git commit -m "feat: add replaces filters to MaintenanceFilterSet

Allow filtering maintenances by replacement relationship.
Includes has_replaces boolean filter for finding rescheduled events."
```

---

## Task 9: Run Full Test Suite

**Files:**
- All test files

**Step 1: Run complete test suite**

Run:
```bash
cd /opt/netbox-vendor-notification/.worktrees/feature-reschedule
PYTHONPATH=/opt/netbox/netbox /opt/netbox/venv/bin/pytest tests/ -v --tb=short
```

Expected output: All tests pass (including new reschedule tests)

**Step 2: Run linter**

Run:
```bash
/opt/netbox/venv/bin/ruff check vendor_notification/ tests/
```

Expected output: No errors

**Step 3: Format code**

Run:
```bash
/opt/netbox/venv/bin/ruff format vendor_notification/ tests/
```

---

## Task 10: Final Integration Test

**Files:**
- Manual testing

**Step 1: Start dev server**

```bash
cd /opt/netbox/netbox
python manage.py runserver 0.0.0.0:8000
```

**Step 2: Test complete workflow**

1. Create a maintenance event (MAINT-001, status=CONFIRMED)
2. Add some impacts to it
3. Click "Reschedule" button
4. Verify form is pre-filled with original data
5. Change dates and submit
6. Verify new maintenance created (MAINT-002, status=TENTATIVE)
7. Verify new maintenance has replaces=MAINT-001
8. Verify original maintenance status is now RE-SCHEDULED
9. View original maintenance - see "was rescheduled" alert
10. View new maintenance - see "replaces" alert
11. Click links between them

**Step 3: Test API workflow**

```bash
# Get token
curl -X POST http://localhost:8000/api/users/tokens/provision/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}'

# Create maintenance
curl -X POST http://localhost:8000/api/plugins/vendor-notification/maintenances/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "API-MAINT-001", ...}'

# Create rescheduled maintenance
curl -X POST http://localhost:8000/api/plugins/vendor-notification/maintenances/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "API-MAINT-002", "replaces": 1, ...}'

# Verify replaces relationship
curl http://localhost:8000/api/plugins/vendor-notification/maintenances/2/ \
  -H "Authorization: Token YOUR_TOKEN"
```

---

## Verification Checklist

Before considering this feature complete, verify:

- [ ] Model field added with migration
- [ ] Form includes replaces field
- [ ] Reschedule view clones data correctly
- [ ] Original status updated to RE-SCHEDULED on reschedule
- [ ] Reschedule button appears on detail page
- [ ] Reschedule button hidden for COMPLETED/CANCELLED
- [ ] Replacement chain alerts display correctly
- [ ] Reschedule template shows context info
- [ ] API serializer includes replaces field
- [ ] All tests pass
- [ ] Code passes linting
- [ ] Manual UI workflow works end-to-end
- [ ] Manual API workflow works

---

## Notes for Engineer

**NetBox Conventions:**
- Use `NetBoxModel` as base class for models
- Use `NetBoxModelForm` for forms
- Use `generic.ObjectEditView` for views
- Migrations auto-generated with `manage.py makemigrations`
- Templates extend `generic/object.html` or `generic/object_edit.html`

**Testing:**
- All Django tests require `@pytest.mark.django_db` decorator
- Use `force_login()` for authenticated client
- Use `refresh_from_db()` to reload model after changes
- API tests use `APIClient` from DRF

**Development Environment:**
- NetBox runs at `http://localhost:8000`
- Default admin credentials: admin/admin
- Plugin installed in editable mode: `/opt/netbox-vendor-notification`
- NetBox code at: `/opt/netbox/netbox`

**Git Workflow:**
- Make small, focused commits after each passing test
- Write descriptive commit messages
- Follow conventional commit format: `feat:`, `fix:`, `test:`, `docs:`
