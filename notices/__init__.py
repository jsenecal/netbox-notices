"""Top-level package for NetBox Notices Plugin."""

import logging

__author__ = """Jonathan Senecal"""
__email__ = "contact@jonathansenecal.com"
__version__ = "1.1.2"


from netbox.plugins import PluginConfig

from .constants import DEFAULT_ALLOWED_CONTENT_TYPES

logger = logging.getLogger(__name__)


class NoticesConfig(PluginConfig):
    author = __author__
    author_email = __email__
    name = "notices"
    verbose_name = "Notices"
    description = "Track maintenance and outage events across various NetBox models"
    version = __version__
    min_version = "4.5.0"
    base_url = "notices"
    graphql_schema = "graphql.schema.schema"

    default_settings = {
        "allowed_content_types": DEFAULT_ALLOWED_CONTENT_TYPES,
        "ical_past_days_default": 30,
        "ical_cache_max_age": 900,
        "ical_token_placeholder": "changeme",
        "event_history_days": 30,
    }

    def ready(self):
        super().ready()
        from . import (
            checks,  # noqa: F401
            resolvers,  # noqa: F401
            signals,  # noqa: F401
            widgets,  # noqa: F401
        )

        logger.info("%s plugin loaded", self.name)


config = NoticesConfig
