"""
Constants for vendor notification plugin configuration
"""

# Default allowed content types for impact linking
DEFAULT_ALLOWED_CONTENT_TYPES = [
    "circuits.Circuit",
    "dcim.Device",
    "dcim.PowerFeed",
    "dcim.Site",
]

# Generating notifications creates, updates and deletes drafts, so it needs all three rights.
GENERATE_NOTIFICATIONS_PERMISSIONS = (
    "notices.add_preparednotification",
    "notices.change_preparednotification",
    "notices.delete_preparednotification",
)

# Upper bound for the duration_min / duration_max filters, in hours (about 11
# years). Larger values overflow timedelta and would surface as a server error.
MAX_DURATION_FILTER_HOURS = 100_000
