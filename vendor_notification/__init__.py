"""Top-level package for NetBox Vendor Notification Plugin."""

__author__ = """Jonathan Senecal"""
__email__ = "contact@jonathansenecal.com"
__version__ = "0.0.1"


from netbox.plugins import PluginConfig
from .constants import DEFAULT_ALLOWED_CONTENT_TYPES


class VendorNotificationConfig(PluginConfig):
    author = __author__
    author_email = __email__
    name = "vendor_notification"
    verbose_name = "NetBox Vendor Notification Plugin"
    description = "Track maintenance and outage events across various NetBox models"
    version = __version__
    min_version = "4.4.0"
    base_url = "vendor-notification"

    default_settings = {
        'allowed_content_types': DEFAULT_ALLOWED_CONTENT_TYPES
    }

    def ready(self):
        super().ready()
        from . import widgets


config = VendorNotificationConfig
