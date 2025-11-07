"""Top-level package for NetBox Vendor Notification Plugin."""

__author__ = """Jonathan Senecal"""
__email__ = "contact@jonathansenecal.com"
__version__ = "0.0.1"


from netbox.plugins import PluginConfig

from .constants import DEFAULT_ALLOWED_CONTENT_TYPES

# Template extensions will be populated dynamically in ready()
template_extensions = []


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
        "allowed_content_types": DEFAULT_ALLOWED_CONTENT_TYPES,
        "ical_past_days_default": 30,
        "ical_cache_max_age": 900,
        "ical_token_placeholder": "changeme",
        "event_history_days": 30,
    }

    def ready(self):
        super().ready()
        from . import widgets  # noqa: F401

        # Register dynamic template extensions
        from .template_content import create_event_history_extensions

        global template_extensions
        template_extensions.extend(create_event_history_extensions())


config = VendorNotificationConfig
