import pytest
from django.test import override_settings
from vendor_notification.utils import get_allowed_content_types
from vendor_notification.constants import DEFAULT_ALLOWED_CONTENT_TYPES


class TestPluginConfiguration:
    """Test plugin configuration and allowed content types"""

    def test_default_allowed_types(self):
        """Test default allowed_content_types from constants"""
        allowed = get_allowed_content_types()
        assert 'circuits.Circuit' in allowed
        assert 'dcim.PowerFeed' in allowed
        assert 'dcim.Site' in allowed
        assert allowed == DEFAULT_ALLOWED_CONTENT_TYPES

    @override_settings(
        PLUGINS_CONFIG={
            'vendor_notification': {
                'allowed_content_types': ['dcim.Device', 'virtualization.VirtualMachine']
            }
        }
    )
    def test_custom_allowed_types(self):
        """Test custom configuration overrides defaults"""
        allowed = get_allowed_content_types()
        assert len(allowed) == 2
        assert 'dcim.Device' in allowed
        assert 'virtualization.VirtualMachine' in allowed
        assert 'circuits.Circuit' not in allowed
