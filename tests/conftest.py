"""
Pytest configuration for vendor_notification tests.
Sets up Django and NetBox environment for testing.
"""
import os
import sys

# Add NetBox to Python path
sys.path.insert(0, '/opt/netbox/netbox')


def pytest_configure(config):
    """Configure pytest with Django settings before Django setup"""
    # Import settings module before Django setup
    from netbox import configuration_testing

    # Configure database for testing
    configuration_testing.DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
        }
    }

    # Add vendor_notification to PLUGINS
    if not hasattr(configuration_testing, 'PLUGINS'):
        configuration_testing.PLUGINS = []
    if 'vendor_notification' not in configuration_testing.PLUGINS:
        configuration_testing.PLUGINS.append('vendor_notification')

    # Set default PLUGINS_CONFIG if not present
    if not hasattr(configuration_testing, 'PLUGINS_CONFIG'):
        configuration_testing.PLUGINS_CONFIG = {}

    if 'vendor_notification' not in configuration_testing.PLUGINS_CONFIG:
        configuration_testing.PLUGINS_CONFIG['vendor_notification'] = {}

    # Set Django settings module
    os.environ['DJANGO_SETTINGS_MODULE'] = 'netbox.configuration_testing'
