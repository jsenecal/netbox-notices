"""
Pytest configuration for notices tests.
Sets up Django and NetBox environment for testing.
"""

import os
import sys

import pytest

# Add NetBox to Python path BEFORE any imports
# Use PYTHONPATH if set (CI environment), otherwise use devcontainer path
netbox_path = os.environ.get("PYTHONPATH", "/opt/netbox/netbox")
if netbox_path not in sys.path:
    sys.path.insert(0, netbox_path)

# Set Django settings module
os.environ["DJANGO_SETTINGS_MODULE"] = "netbox.settings"

# Detect environment: CI vs DevContainer
# CI sets NETBOX_CONFIGURATION=netbox.configuration in workflow env
# DevContainer needs manual configuration
is_ci = "GITHUB_ACTIONS" in os.environ

if not is_ci:
    # DevContainer: Use configuration_testing and manually configure
    os.environ.setdefault("NETBOX_CONFIGURATION", "netbox.configuration_testing")

    # Import and configure testing settings BEFORE pytest starts
    from netbox import configuration_testing

    # Configure database for testing
    # Use PostgreSQL (required for NetBox - SQLite doesn't support array fields)
    configuration_testing.DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "netbox"),
            "USER": os.environ.get("DB_USER", "netbox"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "postgres"),
            "PORT": os.environ.get("DB_PORT", "5432"),
            "CONN_MAX_AGE": 300,
        }
    }

    # Configure Redis for testing (use container hostname instead of localhost)
    configuration_testing.REDIS = {
        "tasks": {
            "HOST": os.environ.get("REDIS_HOST", "redis"),
            "PORT": int(os.environ.get("REDIS_PORT", 6379)),
            "PASSWORD": os.environ.get("REDIS_PASSWORD", ""),
            "DATABASE": int(os.environ.get("REDIS_DATABASE", 0)),
            "SSL": os.environ.get("REDIS_SSL", "False").lower() == "true",
        },
        "caching": {
            "HOST": os.environ.get("REDIS_CACHE_HOST", os.environ.get("REDIS_HOST", "redis")),
            "PORT": int(os.environ.get("REDIS_CACHE_PORT", os.environ.get("REDIS_PORT", 6379))),
            "PASSWORD": os.environ.get("REDIS_CACHE_PASSWORD", os.environ.get("REDIS_PASSWORD", "")),
            "DATABASE": int(os.environ.get("REDIS_CACHE_DATABASE", 1)),
            "SSL": os.environ.get("REDIS_CACHE_SSL", os.environ.get("REDIS_SSL", "False")).lower() == "true",
        },
    }

    # Add notices to PLUGINS
    if not hasattr(configuration_testing, "PLUGINS"):
        configuration_testing.PLUGINS = []
    if "notices" not in configuration_testing.PLUGINS:
        configuration_testing.PLUGINS.append("notices")

    # Set default PLUGINS_CONFIG if not present
    if not hasattr(configuration_testing, "PLUGINS_CONFIG"):
        configuration_testing.PLUGINS_CONFIG = {}

    if "notices" not in configuration_testing.PLUGINS_CONFIG:
        configuration_testing.PLUGINS_CONFIG["notices"] = {}

# Initialize Django BEFORE test collection
import django  # noqa: E402

django.setup()


def pytest_configure(config):
    """
    Hook called after command line options have been parsed.
    Django is already set up at module import time above.
    """


# Common fixtures for all tests


@pytest.fixture
def provider(db):
    """Create a test provider."""
    from circuits.models import Provider

    return Provider.objects.create(name="Test Provider", slug="test-provider")


@pytest.fixture
def circuit_type(db):
    """Create a test circuit type."""
    from circuits.models import CircuitType

    return CircuitType.objects.create(name="Test Type", slug="test-type")


@pytest.fixture
def circuit(db, provider, circuit_type):
    """Create a test circuit."""
    from circuits.models import Circuit

    return Circuit.objects.create(
        cid="TEST-001",
        provider=provider,
        type=circuit_type,
    )


@pytest.fixture
def site(db):
    """Create a test site."""
    from dcim.models import Site

    return Site.objects.create(name="Test Site", slug="test-site")


@pytest.fixture
def device_role(db):
    """Create a test device role."""
    from dcim.models import DeviceRole

    return DeviceRole.objects.create(name="Test Role", slug="test-role")


@pytest.fixture
def manufacturer(db):
    """Create a test manufacturer."""
    from dcim.models import Manufacturer

    return Manufacturer.objects.create(name="Test Manufacturer", slug="test-manufacturer")


@pytest.fixture
def device_type(db, manufacturer):
    """Create a test device type."""
    from dcim.models import DeviceType

    return DeviceType.objects.create(
        manufacturer=manufacturer,
        model="Test Model",
        slug="test-model",
    )


@pytest.fixture
def device(db, site, device_role, device_type):
    """Create a test device."""
    from dcim.models import Device

    return Device.objects.create(
        name="test-device",
        site=site,
        role=device_role,
        device_type=device_type,
    )


@pytest.fixture
def tenant(db):
    """Create a test tenant."""
    from tenancy.models import Tenant

    return Tenant.objects.create(
        name="Test Tenant",
        slug="test-tenant",
    )


@pytest.fixture
def contact():
    """Create a test contact with email."""
    from tenancy.models import Contact

    return Contact.objects.create(
        name="Test Contact",
        email="test@example.com",
    )


@pytest.fixture
def make_maintenance(provider):
    """Factory for saved Maintenances: `make_maintenance(name, hours=2, **overrides)`.

    A CONFIRMED maintenance of the `provider` fixture, summarised by its name,
    starting now unless `start` is given and lasting `hours`.
    """
    from datetime import timedelta

    from django.utils import timezone

    from notices.models import Maintenance

    def make(name, hours=2, start=None, **overrides):
        start = start or timezone.now()
        fields = {
            "name": name,
            "summary": name,
            "provider": provider,
            "status": "CONFIRMED",
            "start": start,
            "end": start + timedelta(hours=hours),
            **overrides,
        }
        return Maintenance.objects.create(**fields)

    return make


@pytest.fixture
def maintenance(make_maintenance):
    """Create a test maintenance event."""
    return make_maintenance("MAINT-001", hours=4, summary="Test maintenance event")


@pytest.fixture
def maintenance_with_two_tenants(maintenance, provider, circuit_type):
    """A maintenance impacting one circuit of each of two tenants, each with a primary NOC contact."""
    from circuits.models import Circuit
    from tenancy.models import Contact, ContactAssignment, ContactRole, Tenant

    from notices.models import Impact

    role = ContactRole.objects.create(name="NOC", slug="noc")
    tenants = []
    for idx in (1, 2):
        tenant = Tenant.objects.create(name=f"Tenant {idx}", slug=f"tenant-{idx}")
        contact = Contact.objects.create(name=f"Contact {idx}", email=f"c{idx}@example.com")
        ContactAssignment.objects.create(object=tenant, contact=contact, role=role, priority="primary")
        circuit = Circuit.objects.create(cid=f"CID-{idx}", provider=provider, type=circuit_type, tenant=tenant)
        Impact.objects.create(event=maintenance, target=circuit, impact="OUTAGE")
        tenants.append(tenant)
    return maintenance, tenants[0], tenants[1]


@pytest.fixture
def make_template(db):
    """Factory for saved NotificationTemplates: `make_template(slug, **overrides)`."""
    from notices.models import NotificationTemplate

    def make(slug, **overrides):
        fields = {
            "name": slug,
            "slug": slug,
            "event_type": "maintenance",
            "granularity": "per_event",
            "subject_template": "S",
            "body_template": "B",
            "body_format": "text",
            **overrides,
        }
        return NotificationTemplate.objects.create(**fields)

    return make


@pytest.fixture
def make_notification(make_template):
    """Factory for saved PreparedNotifications: `make_notification(status="sent", **fields)`.

    A sent or delivered notification defaults to having been sent an hour ago.
    """
    from datetime import timedelta

    from django.utils import timezone

    from notices.choices import PreparedNotificationStatusChoices as Status
    from notices.models import PreparedNotification

    template = make_template("notification-kind")

    def make(status=Status.SENT, **fields):
        if status in (Status.SENT, Status.DELIVERED):
            fields.setdefault("sent_at", timezone.now() - timedelta(hours=1))
        return PreparedNotification.objects.create(
            template=template, subject="S", body_text="B", status=status, **fields
        )

    return make


@pytest.fixture
def api_client_for(db):
    """Factory: `api_client_for(user)` is a REST API client authenticated as `user`."""
    from rest_framework.test import APIClient

    def make(user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    return make


@pytest.fixture
def admin_api(api_client_for):
    """A REST API client authenticated as a superuser."""
    from django.contrib.auth import get_user_model

    user = get_user_model().objects.create_superuser(username="api-admin", password="x", email="api-admin@example.com")
    return api_client_for(user)


@pytest.fixture
def notification_template(make_template):
    """Create a test notification template."""
    return make_template(
        "test-template",
        name="Test Template",
        subject_template="Test Subject: {{ maintenance.name }}",
        body_template="Test body for {{ maintenance.name }}",
    )


@pytest.fixture
def grant_permission(db):
    """Grant an ObjectPermission: `grant_permission(user, actions, *model_names, constraints=None)`.

    Model names are notices models, e.g. "preparednotification".
    """
    from core.models import ObjectType
    from users.models import ObjectPermission

    def grant(user, actions, *model_names, constraints=None):
        perm = ObjectPermission.objects.create(
            name=f"{user.username}: {'/'.join(actions)} on {'/'.join(model_names)}",
            actions=actions,
            constraints=constraints,
        )
        perm.object_types.add(*[ObjectType.objects.get(app_label="notices", model=m) for m in model_names])
        perm.users.add(user)
        return perm

    return grant
