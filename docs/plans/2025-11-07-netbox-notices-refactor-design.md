# Refactoring Design: netbox-vendor-notification → netbox-notices

**Date:** 2025-11-07
**Status:** Approved
**Approach:** Clean break (no database migration)

## Overview

Refactor the project from "netbox-vendor-notification" to "netbox-notices" to reflect a broader scope that is neutral about the source (vendor vs internal observation) and encompasses both planned maintenance and unplanned outages.

## Design Decisions

### Database Migration Strategy
**Decision:** Clean break - new plugin, no migration
**Rationale:** Simpler implementation without migration complexity. Users will need to manually migrate data if they have existing installations.

### URL Structure
**Decision:** Use `/plugins/notices/` base path
**Rationale:** Consistent with NetBox plugin conventions and reflects the broader "notices" scope.

### UI Terminology
**Decision:** Rename only - keep 'Maintenance' and 'Outage' terms
**Rationale:** Preserve clear, established terminology while the package name indicates broader scope. Model names remain: `Maintenance`, `Outage`, `Impact` (not MaintenanceNotice, OutageNotice, etc.).

## Section 1: Package and Module Structure

### Package Changes
- PyPI package: `netbox-vendor-notification` → `netbox-notices`
- Python module: `vendor_notification/` → `notices/`
- Egg info: `netbox_vendor_notification.egg-info` → `netbox_notices.egg-info`

### Directory Structure After Rename
```
/opt/netbox-notices/
├── notices/                    # renamed from vendor_notification/
│   ├── __init__.py
│   ├── models.py              # Maintenance, Outage, Impact (unchanged)
│   ├── api/
│   ├── forms.py
│   ├── views.py
│   ├── urls.py
│   ├── templates/notices/     # renamed from vendor_notification/
│   └── static/notices/        # renamed from vendor_notification/
├── tests/
├── pyproject.toml
└── README.md
```

### Plugin Configuration
- Plugin name in `__init__.py`: `VendorNotificationConfig` → `NoticesConfig`
- Django app label: `vendor_notification` → `notices`
- Database tables will be: `notices_maintenance`, `notices_outage`, `notices_impact`

### Model Names (Unchanged)
- `Maintenance` (not MaintenanceNotice)
- `Outage` (not OutageNotice)
- `Impact` (not ImpactNotice)

## Section 2: URL Routing and API Endpoints

### Web UI URLs
Base path changes from `/maintenance/` to `/plugins/notices/`

**Example URL transformations:**
- `/maintenance/` → `/plugins/notices/maintenance/`
- `/maintenance/123/` → `/plugins/notices/maintenance/123/`
- `/maintenance/calendar/` → `/plugins/notices/calendar/`
- `/plugins/vendor-notification/ical/maintenances.ics` → `/plugins/notices/ical/maintenances.ics`

### API Endpoints
- API namespace: `plugins-api:vendor_notification-api` → `plugins-api:notices-api`
- Base API path: `/api/plugins/vendor-notification/` → `/api/plugins/notices/`

**Endpoint examples:**
- `/api/plugins/vendor-notification/maintenance/` → `/api/plugins/notices/maintenance/`
- `/api/plugins/vendor-notification/outage/` → `/api/plugins/notices/outage/`
- `/api/plugins/vendor-notification/impact/` → `/api/plugins/notices/impact/`

### Navigation Menu
- Top-level menu item: "Maintenance" → "Notices"
- Submenu items remain: "Maintenances", "Outages", "Impacts", "Calendar"

### Files to Update
- `notices/urls.py` - update urlpatterns and app_name
- `notices/api/urls.py` - update API router registration
- `notices/navigation.py` - update menu items
- All internal URL reversals using `{% url %}` tags and `reverse()` calls

## Section 3: Configuration and Static Assets

### Plugin Configuration

In `notices/__init__.py`:
```python
class NoticesConfig(PluginConfig):
    name = 'notices'
    verbose_name = 'Notices'
    description = 'Track maintenance and outage events'
    version = '0.1.0'
    base_url = 'notices'
```

### NetBox configuration.py Changes

Old:
```python
PLUGINS = ['vendor_notification']
PLUGINS_CONFIG = {
    'vendor_notification': {
        'ical_token_placeholder': 'YOUR_TOKEN_HERE',
        'event_history_days': 30,
        'allowed_content_types': ['dcim.device', 'virtualization.virtualmachine', ...]
    }
}
```

New:
```python
PLUGINS = ['notices']
PLUGINS_CONFIG = {
    'notices': {
        'ical_token_placeholder': 'YOUR_TOKEN_HERE',
        'event_history_days': 30,
        'allowed_content_types': ['dcim.device', 'virtualization.virtualmachine', ...]
    }
}
```

### Static Files
- Directory: `vendor_notification/static/vendor_notification/` → `notices/static/notices/`
- Template references: `{% static 'vendor_notification/css/...' %}` → `{% static 'notices/css/...' %}`

**Files affected:**
- `css/calendar-overrides.css`
- `js/calendar.js`
- `js/fullcalendar/index.global.min.js`

### Templates
- Directory: `vendor_notification/templates/vendor_notification/` → `notices/templates/notices/`
- Template extends and includes need updating
- All template files maintain their names (e.g., `calendar.html`, `event_history_tabs.html`)

### DevContainer Configuration
- `.devcontainer/configuration/plugins.py` - update plugin name reference
- Repository mount path can remain `/opt/netbox-vendor-notification` (or rename to `/opt/netbox-notices`)

## Section 4: Testing and Documentation

### Test Updates

All test files in `tests/` directory will need import statement changes:

Old:
```python
from vendor_notification.models import Maintenance, Outage, Impact
from vendor_notification.forms import MaintenanceForm
from vendor_notification.api.serializers import MaintenanceSerializer
```

New:
```python
from notices.models import Maintenance, Outage, Impact
from notices.forms import MaintenanceForm
from notices.api.serializers import MaintenanceSerializer
```

### Test Configuration Changes
- URL reversals: `reverse('plugins:vendor_notification:maintenance_list')` → `reverse('plugins:notices:maintenance_list')`
- API URL paths: `/api/plugins/vendor-notification/` → `/api/plugins/notices/`
- Plugin config: `PLUGINS_CONFIG['vendor_notification']` → `PLUGINS_CONFIG['notices']`

### Documentation Updates

**Files requiring content updates:**
- `README.md` - Update project name, description, installation instructions, GitHub URLs
- `CLAUDE.md` - Update all references to package/module names, URLs, examples
- `CONTRIBUTING.md` - Update repository URLs and setup instructions
- `docs/` directory - Update all documentation with new names
- `pyproject.toml` - Update package name, URLs, description

### Repository References
- GitHub URL remains: `https://github.com/jsenecal/netbox-vendor-notification` (repository can be renamed separately)
- PyPI package name: `netbox-notices`
- Installation command: `pip install netbox-notices`

### Makefile Updates
- PYTHONPATH references if any
- Test commands should work without changes (they use relative paths)

## Section 5: Implementation Strategy

### Execution Order

1. **Directory rename and imports** - Use git mv to preserve history:
   ```bash
   git mv vendor_notification notices
   ```
   Then bulk replace all import statements across codebase.

2. **Update core configuration** - Modify `__init__.py`, `pyproject.toml`, and plugin registration.

3. **Update URLs and routing** - Change URL patterns, namespaces, and all reverse() calls.

4. **Update templates and static files** - Change template paths, static file references, and extends/includes.

5. **Update tests** - Fix all import statements and URL references in test files.

6. **Update documentation** - Revise README, CLAUDE.md, and other docs.

7. **Clean database and regenerate migrations** - Since this is a clean break:
   ```bash
   # Remove old migrations
   rm -rf notices/migrations/
   # Create fresh migrations with new app label
   python manage.py makemigrations notices
   ```

8. **Verification** - Run full test suite and manual testing:
   ```bash
   pytest tests/ -v
   python manage.py check
   python manage.py migrate
   ```

### Risk Mitigation
- The clean break approach means no database migration complexity
- All model and API logic remains unchanged, reducing risk
- Tests provide safety net for import and URL changes
- Can be implemented in a feature branch and tested thoroughly before merge

### Post-Implementation
- Update GitHub repository name (optional)
- Publish new package to PyPI as `netbox-notices`
- Create migration guide for users (document config changes needed)

## Summary

This refactoring renames the project to better reflect its broader scope while maintaining all existing functionality. The clean break approach simplifies implementation at the cost of requiring manual data migration for existing users. The model names and core business logic remain unchanged, focusing the refactoring on package structure, URLs, and configuration.
