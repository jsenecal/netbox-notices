"""
Utility functions for vendor notification plugin
"""
from django.conf import settings
from .constants import DEFAULT_ALLOWED_CONTENT_TYPES


def get_allowed_content_types():
    """
    Get list of allowed content types from plugin config.

    Returns list from PLUGINS_CONFIG['vendor_notification']['allowed_content_types']
    or DEFAULT_ALLOWED_CONTENT_TYPES if not configured.
    """
    return settings.PLUGINS_CONFIG.get('vendor_notification', {}).get(
        'allowed_content_types',
        DEFAULT_ALLOWED_CONTENT_TYPES
    )
