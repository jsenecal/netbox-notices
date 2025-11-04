#!/usr/bin/env python
"""
Script to create migrations for vendor_notification plugin.
Uses NetBox's testing configuration.
"""
import os
import sys
import importlib

# Add current directory and NetBox to Python path FIRST
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
sys.path.insert(0, '/opt/netbox/netbox')

# Import the configuration module
from netbox import configuration_testing

# Modify it BEFORE Django is set up
# Configure database
configuration_testing.DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Replace PLUGINS list entirely
configuration_testing.PLUGINS = ['vendor_notification']

# Set default PLUGINS_CONFIG
if not hasattr(configuration_testing, 'PLUGINS_CONFIG'):
    configuration_testing.PLUGINS_CONFIG = {}

configuration_testing.PLUGINS_CONFIG['vendor_notification'] = {
    'allowed_content_types': [
        'circuits.Circuit',
        'dcim.PowerFeed',
        'dcim.Site',
    ]
}

# Set Django settings module
os.environ['DJANGO_SETTINGS_MODULE'] = 'netbox.configuration_testing'

# Print configuration for debugging
print("PLUGINS:", configuration_testing.PLUGINS)
print("Python path includes vendor_notification dir:", current_dir in sys.path)

# NOW import and setup Django
import django
django.setup()

# Verify plugin is loaded
from django.apps import apps
from django.conf import settings

print("\nDjango apps loaded:")
for app in apps.get_app_configs():
    if 'vendor' in app.name.lower() or app.name == 'vendor_notification':
        print(f"  - {app.name} ({app.label})")

# Try to get the vendor_notification app
try:
    vendor_app = apps.get_app_config('vendor_notification')
    print(f"\nvendor_notification app found: {vendor_app.name}")
    print(f"Models path: {vendor_app.models_module}")
except LookupError as e:
    print(f"\nERROR: vendor_notification app not found: {e}")
    print("\nAll installed apps:")
    for app in settings.INSTALLED_APPS:
        print(f"  - {app}")
    sys.exit(1)

# Run makemigrations
from django.core.management import call_command
print("\nRunning makemigrations...")
call_command('makemigrations', 'vendor_notification', verbosity=2)
