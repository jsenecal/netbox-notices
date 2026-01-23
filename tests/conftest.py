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
    pass


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

    return Manufacturer.objects.create(
        name="Test Manufacturer", slug="test-manufacturer"
    )


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
