#!/usr/bin/env python
"""
Script to create migrations for vendor_notification plugin.
Uses NetBox's testing configuration.
"""
import os
import sys

# Add current directory and NetBox to Python path FIRST
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '/opt/netbox/netbox')

# Import and configure BEFORE Django setup
from netbox import configuration_testing

# Configure database
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
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.configuration_testing')

# NOW import Django and set it up
import django
django.setup()

# Verify the app is installed
from django.conf import settings
from django.apps import apps
print("INSTALLED_APPS with 'vendor':", [app for app in settings.INSTALLED_APPS if 'vendor' in app.lower()])
print("All app configs:", [app.name for app in apps.get_app_configs() if 'vendor' in app.name.lower()])

# Run makemigrations
from django.core.management import call_command
call_command('makemigrations', 'vendor_notification')
