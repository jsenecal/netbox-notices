# Permission Model for netbox-notices

This document describes how permissions are enforced in the netbox-notices plugin.

## Overview

The netbox-notices plugin uses Django's standard permission system, which is automatically enforced by NetBox's generic views and Django REST Framework's API views. All models require appropriate permissions for viewing, adding, changing, and deleting operations.

## Model Permissions

Django automatically creates four permissions for each model:

### Maintenance Model
- `notices.view_maintenance` - Required to view maintenance events
- `notices.add_maintenance` - Required to create new maintenance events
- `notices.change_maintenance` - Required to modify existing maintenance events
- `notices.delete_maintenance` - Required to delete maintenance events

### Outage Model
- `notices.view_outage` - Required to view outages
- `notices.add_outage` - Required to create new outages
- `notices.change_outage` - Required to modify existing outages
- `notices.delete_outage` - Required to delete outages

### Impact Model
- `notices.view_impact` - Required to view impacts
- `notices.add_impact` - Required to create new impacts
- `notices.change_impact` - Required to modify existing impacts
- `notices.delete_impact` - Required to delete impacts

### EventNotification Model
- `notices.view_eventnotification` - Required to view event notifications
- `notices.add_eventnotification` - Required to create new event notifications
- `notices.change_eventnotification` - Required to modify existing event notifications
- `notices.delete_eventnotification` - Required to delete event notifications

## Permission Enforcement

### UI Views (Web Interface)

All UI views inherit from NetBox's generic view classes which automatically enforce permissions:

- **`ObjectView`** (detail pages) - Requires `view_<model>` permission
- **`ObjectListView`** (list pages) - Requires `view_<model>` permission
- **`ObjectEditView`** (create/edit forms) - Requires `add_<model>` or `change_<model>` permission
- **`ObjectDeleteView`** (delete confirmation) - Requires `delete_<model>` permission

Examples from `notices/views.py`:
```python
class MaintenanceView(generic.ObjectView):  # Requires notices.view_maintenance
    queryset = models.Maintenance.objects.all()

class MaintenanceEditView(generic.ObjectEditView):  # Requires notices.add_maintenance or notices.change_maintenance
    queryset = models.Maintenance.objects.all()
    form = forms.MaintenanceForm

class MaintenanceDeleteView(generic.ObjectDeleteView):  # Requires notices.delete_maintenance
    queryset = models.Maintenance.objects.all()
```

### API Views (REST API)

All API views use `NetBoxModelViewSet` which integrates with Django REST Framework's permission system:

```python
class MaintenanceViewSet(NetBoxModelViewSet):
    queryset = models.Maintenance.objects.prefetch_related("tags")
    serializer_class = MaintenanceSerializer
```

API permission enforcement:
- **GET (list/detail)** - Requires `view_<model>` permission
- **POST** - Requires `add_<model>` permission
- **PUT/PATCH** - Requires `change_<model>` permission
- **DELETE** - Requires `delete_<model>` permission

### Special Views

#### MaintenanceCalendarView
Uses `PermissionRequiredMixin` to require `notices.view_maintenance`:
```python
class MaintenanceCalendarView(PermissionRequiredMixin, View):
    permission_required = "notices.view_maintenance"
```

#### MaintenanceICalView
Manually checks permissions in the `get()` method:
```python
def get(self, request):
    user = self._authenticate_request(request)
    if not user:
        return HttpResponseForbidden("Authentication required")

    if not user.has_perm("notices.view_maintenance"):
        return HttpResponseForbidden("Permission denied")
```

Supports three authentication methods:
1. Token in URL parameter (`?token=xxx`)
2. Authorization header (`Authorization: Token xxx`)
3. Session authentication (browser)

## Granting Permissions

### Via NetBox Admin UI

1. Navigate to **Admin** → **Users & Groups**
2. Select a user or group
3. Under **Permissions**, add the required notices permissions
4. Save

### Via Django Admin

1. Navigate to **Admin** → **Authentication and Authorization** → **Users**
2. Select a user
3. Scroll to **User permissions**
4. Add notices permissions (e.g., `notices | maintenance | Can view Maintenance`)
5. Save

### Programmatically

```python
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from notices.models import Maintenance

# Get the user
user = User.objects.get(username='example_user')

# Get the permission
content_type = ContentType.objects.get_for_model(Maintenance)
permission = Permission.objects.get(
    content_type=content_type,
    codename='view_maintenance'
)

# Grant permission
user.user_permissions.add(permission)
```

## Testing Permissions

All tests in the test suite use superusers to bypass permission checks:

```python
@pytest.fixture
def user(self):
    """Create a superuser for testing."""
    return User.objects.create_superuser(
        username="testuser",
        email="test@example.com",
        password="testpass123"
    )
```

For testing permission enforcement specifically, create regular users without superuser privileges:

```python
def test_requires_permission(self):
    """Test that view requires proper permission."""
    # Create user without permissions
    user = User.objects.create_user(username="noauth", password="test")
    client = Client()
    client.force_login(user)

    # Attempt to access protected resource
    response = client.get(url)

    # Should be forbidden or redirect to login
    assert response.status_code in [302, 403]
```

## Navigation Menu Permissions

The plugin menu in NetBox's navigation also enforces permissions. Menu items and buttons are only visible to users with the appropriate permissions:

**Menu Items:**
- **Inbound (EventNotifications)** - Requires `notices.view_eventnotification`
  - "Add" button - Requires `notices.add_eventnotification`
- **Planned Maintenances** - Requires `notices.view_maintenance`
  - "Add" button - Requires `notices.add_maintenance`
- **Outages** - Requires `notices.view_outage`
  - "Add" button - Requires `notices.add_outage`
- **Calendar** - Requires `notices.view_maintenance`

This is configured in `notices/navigation.py` using the `permissions` parameter on `PluginMenuItem` and `PluginMenuButton` objects.

## Summary

**All views and API endpoints in netbox-notices properly enforce Django permissions.** There is no way to view, create, modify, or delete any data without the appropriate permission. This is enforced at multiple levels:

1. **NetBox Generic Views** - Automatic permission checking via `get_required_permission()`
2. **Django REST Framework** - Permission classes on `NetBoxModelViewSet`
3. **Manual Checks** - Explicit `user.has_perm()` calls in custom views
4. **Navigation Menu** - Menu items and buttons hidden from users without permissions

Users must be explicitly granted permissions through NetBox's user/group management system or Django admin.
