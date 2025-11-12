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

# Detect environment: CI uses pre-configured files, devcontainer uses configuration_testing
is_ci = "GITHUB_ACTIONS" in os.environ

if is_ci:
    # CI: Use the configuration.py and plugins.py already copied by workflow
    # These files already have notices configured in PLUGINS
    print("=== CI Environment Detected ===")
    print(f"PYTHONPATH: {os.environ.get('PYTHONPATH')}")
    print(f"DJANGO_SETTINGS_MODULE: {os.environ.get('DJANGO_SETTINGS_MODULE')}")

    # NetBox needs to know which configuration module to use
    os.environ["NETBOX_CONFIGURATION"] = "netbox.configuration"
    print(f"NETBOX_CONFIGURATION set to: {os.environ['NETBOX_CONFIGURATION']}")

    # Just set SECRET_KEY if not already set
    if not os.environ.get("SECRET_KEY"):
        os.environ["SECRET_KEY"] = "abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)"

    # Import configuration to verify PLUGINS
    try:
        from netbox import configuration
        print(f"PLUGINS from configuration: {getattr(configuration, 'PLUGINS', 'NOT FOUND')}")
    except Exception as e:
        print(f"Error importing configuration: {e}")
else:
    # DevContainer: Use configuration_testing and manually configure
    os.environ["NETBOX_CONFIGURATION"] = "netbox.configuration_testing"

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
