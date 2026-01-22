from utilities.choices import ChoiceSet


class TimeZoneChoices(ChoiceSet):
    """
    Timezone choices grouped by region for maintenance event scheduling.
    Uses IANA timezone database names.
    """

    key = "Maintenance.TimeZone"

    # Common/UTC timezones
    COMMON_CHOICES = [
        ("UTC", "UTC"),
        ("GMT", "GMT"),
    ]

    # Build regional timezone choices
    AFRICA_CHOICES = [
        (tz, tz)
        for tz in sorted(
            [
                "Africa/Cairo",
                "Africa/Johannesburg",
                "Africa/Lagos",
                "Africa/Nairobi",
                "Africa/Casablanca",
            ]
        )
    ]

    AMERICA_CHOICES = [
        (tz, tz)
        for tz in sorted(
            [
                "America/New_York",
                "America/Chicago",
                "America/Denver",
                "America/Los_Angeles",
                "America/Phoenix",
                "America/Anchorage",
                "America/Toronto",
                "America/Vancouver",
                "America/Montreal",
                "America/Mexico_City",
                "America/Sao_Paulo",
                "America/Buenos_Aires",
                "America/Santiago",
                "America/Bogota",
                "America/Lima",
            ]
        )
    ]

    ASIA_CHOICES = [
        (tz, tz)
        for tz in sorted(
            [
                "Asia/Dubai",
                "Asia/Kabul",
                "Asia/Kolkata",
                "Asia/Dhaka",
                "Asia/Bangkok",
                "Asia/Singapore",
                "Asia/Hong_Kong",
                "Asia/Shanghai",
                "Asia/Tokyo",
                "Asia/Seoul",
                "Asia/Manila",
                "Asia/Jakarta",
                "Asia/Tehran",
                "Asia/Jerusalem",
                "Asia/Karachi",
            ]
        )
    ]

    ATLANTIC_CHOICES = [
        (tz, tz)
        for tz in sorted(
            ["Atlantic/Azores", "Atlantic/Cape_Verde", "Atlantic/Reykjavik"]
        )
    ]

    AUSTRALIA_CHOICES = [
        (tz, tz)
        for tz in sorted(
            [
                "Australia/Perth",
                "Australia/Adelaide",
                "Australia/Darwin",
                "Australia/Brisbane",
                "Australia/Sydney",
                "Australia/Melbourne",
                "Australia/Hobart",
            ]
        )
    ]

    EUROPE_CHOICES = [
        (tz, tz)
        for tz in sorted(
            [
                "Europe/London",
                "Europe/Dublin",
                "Europe/Lisbon",
                "Europe/Paris",
                "Europe/Brussels",
                "Europe/Amsterdam",
                "Europe/Berlin",
                "Europe/Rome",
                "Europe/Madrid",
                "Europe/Zurich",
                "Europe/Vienna",
                "Europe/Prague",
                "Europe/Warsaw",
                "Europe/Budapest",
                "Europe/Athens",
                "Europe/Helsinki",
                "Europe/Stockholm",
                "Europe/Moscow",
                "Europe/Istanbul",
            ]
        )
    ]

    PACIFIC_CHOICES = [
        (tz, tz)
        for tz in sorted(
            [
                "Pacific/Auckland",
                "Pacific/Fiji",
                "Pacific/Honolulu",
                "Pacific/Guam",
                "Pacific/Port_Moresby",
            ]
        )
    ]

    CHOICES = [
        ("Common", COMMON_CHOICES),
        ("Africa", AFRICA_CHOICES),
        ("America", AMERICA_CHOICES),
        ("Asia", ASIA_CHOICES),
        ("Atlantic", ATLANTIC_CHOICES),
        ("Australia", AUSTRALIA_CHOICES),
        ("Europe", EUROPE_CHOICES),
        ("Pacific", PACIFIC_CHOICES),
    ]


class MaintenanceTypeChoices(ChoiceSet):
    """Valid maintenance status choices from BCOP standard"""

    key = "DocTypeChoices.Maintenance"

    STATUS_TENTATIVE = "TENTATIVE"
    STATUS_CONFIRMED = "CONFIRMED"
    STATUS_CANCELLED = "CANCELLED"
    STATUS_IN_PROCESS = "IN-PROCESS"
    STATUS_COMPLETED = "COMPLETED"
    STATUS_RESCHEDULED = "RE-SCHEDULED"
    STATUS_UNKNOWN = "UNKNOWN"

    CHOICES = [
        (STATUS_TENTATIVE, "Tentative", "yellow"),
        (STATUS_CONFIRMED, "Confirmed", "green"),
        (STATUS_CANCELLED, "Cancelled", "gray"),
        (STATUS_IN_PROCESS, "In-Progress", "orange"),
        (STATUS_COMPLETED, "Completed", "indigo"),
        (STATUS_RESCHEDULED, "Rescheduled", "teal"),
        (STATUS_UNKNOWN, "Unknown", "blue"),
    ]


class ImpactTypeChoices(ChoiceSet):
    """Valid impact level choices from BCOP standard"""

    key = "DocTypeChoices.Impact"

    IMPACT_NO_IMPACT = "NO-IMPACT"
    IMPACT_REDUCED_REDUNDANCY = "REDUCED-REDUNDANCY"
    IMPACT_DEGRADED = "DEGRADED"
    IMPACT_OUTAGE = "OUTAGE"

    CHOICES = [
        (IMPACT_NO_IMPACT, "No-Impact", "green"),
        (IMPACT_REDUCED_REDUNDANCY, "Reduced Redundancy", "yellow"),
        (IMPACT_DEGRADED, "Degraded", "orange"),
        (IMPACT_OUTAGE, "Outage", "red"),
    ]


class OutageStatusChoices(ChoiceSet):
    """Status choices for unplanned outage events"""

    key = "Outage.Status"

    STATUS_REPORTED = "REPORTED"
    STATUS_INVESTIGATING = "INVESTIGATING"
    STATUS_IDENTIFIED = "IDENTIFIED"
    STATUS_MONITORING = "MONITORING"
    STATUS_RESOLVED = "RESOLVED"

    CHOICES = [
        (STATUS_REPORTED, "Reported", "red"),
        (STATUS_INVESTIGATING, "Investigating", "orange"),
        (STATUS_IDENTIFIED, "Identified", "yellow"),
        (STATUS_MONITORING, "Monitoring", "blue"),
        (STATUS_RESOLVED, "Resolved", "green"),
    ]


class MessageEventTypeChoices(ChoiceSet):
    """Event type choices for message templates."""

    MAINTENANCE = "maintenance"
    OUTAGE = "outage"
    BOTH = "both"
    NONE = "none"

    CHOICES = [
        (MAINTENANCE, "Maintenance"),
        (OUTAGE, "Outage"),
        (BOTH, "Both"),
        (NONE, "None (Standalone)"),
    ]


class MessageGranularityChoices(ChoiceSet):
    """Granularity choices for message generation."""

    PER_EVENT = "per_event"
    PER_TENANT = "per_tenant"
    PER_IMPACT = "per_impact"

    CHOICES = [
        (PER_EVENT, "Per Event"),
        (PER_TENANT, "Per Tenant"),
        (PER_IMPACT, "Per Impact"),
    ]


class BodyFormatChoices(ChoiceSet):
    """Body format choices for templates."""

    MARKDOWN = "markdown"
    HTML = "html"
    TEXT = "text"

    CHOICES = [
        (MARKDOWN, "Markdown"),
        (HTML, "HTML"),
        (TEXT, "Plain Text"),
    ]


class PreparedMessageStatusChoices(ChoiceSet):
    """Status choices for prepared messages."""

    DRAFT = "draft"
    READY = "ready"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"

    CHOICES = [
        (DRAFT, "Draft"),
        (READY, "Ready"),
        (SENT, "Sent"),
        (DELIVERED, "Delivered"),
        (FAILED, "Failed"),
    ]


class ContactPriorityChoices(ChoiceSet):
    """Contact priority choices (mirrors NetBox's ContactPriorityChoices)."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    TERTIARY = "tertiary"

    CHOICES = [
        (PRIMARY, "Primary"),
        (SECONDARY, "Secondary"),
        (TERTIARY, "Tertiary"),
    ]
