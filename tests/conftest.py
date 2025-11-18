"""
Pytest configuration for notices tests.
Sets up Django and NetBox environment for testing.
"""

import os
import sys

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
