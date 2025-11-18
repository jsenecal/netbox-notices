"""Top-level package for NetBox Notices Plugin."""

__author__ = """Jonathan Senecal"""
__email__ = "contact@jonathansenecal.com"
__version__ = "0.1.1"


from netbox.plugins import PluginConfig

from .constants import DEFAULT_ALLOWED_CONTENT_TYPES


class NoticesConfig(PluginConfig):
    author = __author__
    author_email = __email__
    name = "notices"
    verbose_name = "Notices"
    description = "Track maintenance and outage events across various NetBox models"
    version = __version__
    min_version = "4.4.1"
    base_url = "notices"

    default_settings = {
        "allowed_content_types": DEFAULT_ALLOWED_CONTENT_TYPES,
        "ical_past_days_default": 30,
        "ical_cache_max_age": 900,
        "ical_token_placeholder": "changeme",
        "event_history_days": 30,
    }

    def ready(self):
        super().ready()
        from . import signals  # noqa: F401
        from . import widgets  # noqa: F401


config = NoticesConfig
