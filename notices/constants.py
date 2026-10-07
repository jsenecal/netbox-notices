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
