#!/usr/bin/env python3
"""
Load comprehensive demo data for the netbox-notices plugin.

This script creates sample data covering ALL use cases:
- Template inheritance (base templates, block extensions)
- All body formats (Markdown, HTML, Plain Text)
- All granularities (per_event, per_tenant, per_impact)
- All event types (maintenance, outage, both, standalone)
- Various CSS styles
- iCal templates
- Contact roles and priorities
- Template scopes with various configurations

Usage:
    /opt/netbox/venv/bin/python /opt/netbox-notices/.devcontainer/load_plugin_demo.py

Must be run after:
    1. make load-demo-data (loads NetBox demo data)
    2. make migrate (applies plugin migrations)
"""

import os
import sys
from datetime import timedelta

import django

# Setup Django
sys.path.insert(0, "/opt/netbox/netbox")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "netbox.settings")
django.setup()

# Now we can import Django models
from circuits.models import Circuit, Provider
from dcim.models import Device, Region, Site, SiteGroup
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from tenancy.models import Contact, ContactRole, Tenant, TenantGroup
from users.models import User
from virtualization.models import Cluster, VirtualMachine

from notices.choices import (
    BodyFormatChoices,
    ContactPriorityChoices,
    ImpactTypeChoices,
    MaintenanceTypeChoices,
    MessageEventTypeChoices,
    MessageGranularityChoices,
    OutageStatusChoices,
    PreparedNotificationStatusChoices,
)
from notices.models import (
    EventNotification,
    Impact,
    Maintenance,
    NotificationTemplate,
    Outage,
    PreparedNotification,
    TemplateScope,
)

# =============================================================================
# CSS STYLES
# =============================================================================

CSS_CORPORATE = """
/* Corporate Blue Theme */
body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    color: #333;
    line-height: 1.6;
    max-width: 800px;
    margin: 0 auto;
    padding: 20px;
}
h1, h2, h3 {
    color: #0066cc;
    border-bottom: 2px solid #0066cc;
    padding-bottom: 5px;
}
.alert-box {
    background-color: #fff3cd;
    border: 1px solid #ffc107;
    border-radius: 4px;
    padding: 15px;
    margin: 15px 0;
}
.info-table {
    width: 100%;
    border-collapse: collapse;
    margin: 15px 0;
}
.info-table th, .info-table td {
    border: 1px solid #ddd;
    padding: 10px;
    text-align: left;
}
.info-table th {
    background-color: #0066cc;
    color: white;
}
.status-confirmed { color: #28a745; font-weight: bold; }
.status-tentative { color: #ffc107; font-weight: bold; }
.status-cancelled { color: #dc3545; font-weight: bold; }
.impact-outage { background-color: #f8d7da; }
.impact-degraded { background-color: #fff3cd; }
.impact-reduced { background-color: #d4edda; }
"""

CSS_DARK_THEME = """
/* Dark Theme */
body {
    font-family: 'Monaco', 'Consolas', monospace;
    background-color: #1e1e1e;
    color: #d4d4d4;
    line-height: 1.5;
    max-width: 900px;
    margin: 0 auto;
    padding: 20px;
}
h1, h2, h3 {
    color: #569cd6;
    border-bottom: 1px solid #569cd6;
}
.alert-box {
    background-color: #3c3c3c;
    border-left: 4px solid #ce9178;
    padding: 15px;
    margin: 15px 0;
}
.urgent {
    border-left-color: #f44747;
    background-color: #4a2020;
}
code {
    background-color: #2d2d2d;
    padding: 2px 6px;
    border-radius: 3px;
    color: #ce9178;
}
table {
    width: 100%;
    border-collapse: collapse;
    margin: 15px 0;
    background-color: #2d2d2d;
}
th, td {
    border: 1px solid #404040;
    padding: 10px;
}
th {
    background-color: #264f78;
}
"""

CSS_MINIMAL = """
/* Minimal Clean Theme */
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Arial, sans-serif;
    color: #222;
    line-height: 1.7;
    max-width: 700px;
    margin: 40px auto;
    padding: 0 20px;
}
h1, h2, h3 {
    font-weight: 600;
    margin-top: 2em;
}
h1 { font-size: 1.8em; }
h2 { font-size: 1.4em; }
hr {
    border: none;
    border-top: 1px solid #eee;
    margin: 2em 0;
}
.highlight {
    background: linear-gradient(120deg, #ffeaa7 0%, #ffeaa7 100%);
    padding: 2px 4px;
}
"""

CSS_ALERT_FOCUSED = """
/* Alert-Focused Theme for Outages */
body {
    font-family: 'Roboto', Arial, sans-serif;
    margin: 0;
    padding: 0;
}
.header {
    background: linear-gradient(135deg, #c0392b 0%, #e74c3c 100%);
    color: white;
    padding: 30px;
    text-align: center;
}
.header h1 {
    margin: 0;
    font-size: 2em;
}
.content {
    padding: 30px;
    max-width: 800px;
    margin: 0 auto;
}
.severity-critical {
    background-color: #c0392b;
    color: white;
    padding: 5px 15px;
    border-radius: 20px;
    display: inline-block;
}
.severity-major {
    background-color: #e67e22;
    color: white;
    padding: 5px 15px;
    border-radius: 20px;
    display: inline-block;
}
.severity-minor {
    background-color: #f1c40f;
    color: #333;
    padding: 5px 15px;
    border-radius: 20px;
    display: inline-block;
}
.timeline {
    border-left: 3px solid #3498db;
    padding-left: 20px;
    margin: 20px 0;
}
.timeline-item {
    margin-bottom: 15px;
    position: relative;
}
.timeline-item::before {
    content: '';
    width: 12px;
    height: 12px;
    background: #3498db;
    border-radius: 50%;
    position: absolute;
    left: -26px;
    top: 5px;
}
"""

CSS_PRINT_FRIENDLY = """
/* Print-Friendly Theme */
body {
    font-family: 'Georgia', 'Times New Roman', serif;
    color: #000;
    line-height: 1.8;
    max-width: 100%;
    padding: 20px;
}
h1, h2, h3 {
    page-break-after: avoid;
}
table {
    page-break-inside: avoid;
    width: 100%;
    border-collapse: collapse;
}
th, td {
    border: 1px solid #000;
    padding: 8px;
}
@media print {
    body { font-size: 12pt; }
    .no-print { display: none; }
    a { text-decoration: none; color: #000; }
    a[href]::after { content: " (" attr(href) ")"; font-size: 0.8em; }
}
"""


# =============================================================================
# ICAL TEMPLATES
# =============================================================================

ICAL_STANDARD = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//NetBox Notices//Maintenance Notification//EN
METHOD:PUBLISH
BEGIN:VEVENT
UID:{{ event.pk }}-{{ event.provider.slug }}@netbox-notices
DTSTAMP:{{ now|date:"Ymd" }}T{{ now|date:"His" }}Z
DTSTART:{{ event.start|date:"Ymd" }}T{{ event.start|date:"His" }}Z
DTEND:{{ event.end|date:"Ymd" }}T{{ event.end|date:"His" }}Z
SUMMARY:{{ event.name|truncatechars:75 }}
DESCRIPTION:Provider: {{ event.provider.name }}\\nStatus: {{ event.status }}\\n\\n{{ event.summary|truncatechars:500 }}
LOCATION:{{ event.provider.name }}
STATUS:{{ event.status|upper }}
CATEGORIES:MAINTENANCE,{{ event.provider.name|upper }}
ORGANIZER;CN={{ event.provider.name }}:mailto:noc@{{ event.provider.slug }}.example.com
END:VEVENT
END:VCALENDAR"""

ICAL_WITH_ALARM = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//NetBox Notices//Maintenance Notification//EN
METHOD:REQUEST
BEGIN:VEVENT
UID:{{ event.pk }}-{{ event.provider.slug }}@netbox-notices
DTSTAMP:{{ now|date:"Ymd" }}T{{ now|date:"His" }}Z
DTSTART:{{ event.start|date:"Ymd" }}T{{ event.start|date:"His" }}Z
DTEND:{{ event.end|date:"Ymd" }}T{{ event.end|date:"His" }}Z
SUMMARY:[MAINTENANCE] {{ event.name }}
DESCRIPTION:{{ event.summary }}\\n\\nAffected Services:\\n{% for impact in impacts %}- {{ impact.target }}\\n{% endfor %}
LOCATION:{{ event.provider.name }}
STATUS:CONFIRMED
PRIORITY:5
BEGIN:VALARM
TRIGGER:-P1D
ACTION:DISPLAY
DESCRIPTION:Maintenance starts in 24 hours: {{ event.name }}
END:VALARM
BEGIN:VALARM
TRIGGER:-PT1H
ACTION:DISPLAY
DESCRIPTION:Maintenance starts in 1 hour: {{ event.name }}
END:VALARM
END:VEVENT
END:VCALENDAR"""


# =============================================================================
# BODY TEMPLATES
# =============================================================================

# Base template that others can extend
BASE_TEMPLATE_BODY = """{% block header %}
# {{ title|default:"Notification" }}
---
{% endblock header %}

{% block event_details %}
**Event:** {{ event.name }}
**Provider:** {{ event.provider.name }}
**Status:** {{ event.status }}
{% endblock event_details %}

{% block timing %}
**Start:** {{ event.start|date:"F j, Y, g:i a T" }}
{% if event.end %}**End:** {{ event.end|date:"F j, Y, g:i a T" }}{% endif %}
{% endblock timing %}

{% block summary %}
## Summary
{{ event.summary }}
{% endblock summary %}

{% block impacts %}
{% if impacts %}
## Affected Services
{% for impact in impacts %}
- {{ impact.target }} — *{{ impact.get_impact_display }}*
{% endfor %}
{% endif %}
{% endblock impacts %}

{% block footer %}
---
*This notification was automatically generated by NetBox Notices.*
{% endblock footer %}
"""

# Child template that extends base
MAINTENANCE_CHILD_TEMPLATE = """{% extends "base_notification" %}

{% block header %}
# Scheduled Maintenance Notice
### {{ event.provider.name }}
---
{% endblock header %}

{% block timing %}
{{ block.super }}
**Duration:** {{ event.start|timesince:event.end }}
{% endblock timing %}

{% block footer %}
---
Please plan accordingly. Contact your account manager if you have questions.

*Network Operations Center*
{% endblock footer %}
"""

OUTAGE_CHILD_TEMPLATE = """{% extends "base_notification" %}

{% block header %}
# ⚠️ SERVICE OUTAGE ALERT
### {{ event.provider.name }}
---
{% endblock header %}

{% block timing %}
**Detected:** {{ event.start|date:"F j, Y, g:i a T" }}
{% if event.estimated_time_to_repair %}**Estimated Resolution:** {{ event.estimated_time_to_repair|date:"F j, Y, g:i a T" }}{% endif %}
{% if event.end %}**Resolved:** {{ event.end|date:"F j, Y, g:i a T" }}{% endif %}
{% endblock timing %}

{% block footer %}
---
Our team is actively working on this issue. Updates will be provided as available.

*Network Operations Center - Emergency Response*
{% endblock footer %}
"""

# HTML Template
HTML_TEMPLATE_BODY = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ event.name }}</title>
</head>
<body>
    <div class="header">
        <h1>{{ title|default:"Network Notification" }}</h1>
    </div>
    <div class="content">
        <div class="alert-box{% if event_type == 'outage' %} urgent{% endif %}">
            <strong>{{ event.name }}</strong>
        </div>

        <table class="info-table">
            <tr>
                <th>Provider</th>
                <td>{{ event.provider.name }}</td>
            </tr>
            <tr>
                <th>Status</th>
                <td><span class="status-{{ event.status|lower }}">{{ event.status }}</span></td>
            </tr>
            <tr>
                <th>Start Time</th>
                <td>{{ event.start|date:"F j, Y, g:i a T" }}</td>
            </tr>
            {% if event.end %}
            <tr>
                <th>End Time</th>
                <td>{{ event.end|date:"F j, Y, g:i a T" }}</td>
            </tr>
            {% endif %}
        </table>

        <h2>Summary</h2>
        <p>{{ event.summary }}</p>

        {% if impacts %}
        <h2>Affected Services</h2>
        <table class="info-table">
            <thead>
                <tr>
                    <th>Service</th>
                    <th>Impact Level</th>
                </tr>
            </thead>
            <tbody>
                {% for impact in impacts %}
                <tr class="impact-{{ impact.impact|lower }}">
                    <td>{{ impact.target }}</td>
                    <td>{{ impact.get_impact_display }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% endif %}

        <hr>
        <p><small>This notification was automatically generated by NetBox Notices.</small></p>
    </div>
</body>
</html>
"""

# Plain text template
PLAIN_TEXT_TEMPLATE = """{{ title|default:"NETWORK NOTIFICATION"|upper }}
{{ "="|ljust:60|slice:":60" }}

Event: {{ event.name }}
Provider: {{ event.provider.name }}
Status: {{ event.status }}

TIMING
{{ "-"|ljust:40|slice:":40" }}
Start: {{ event.start|date:"F j, Y, g:i a T" }}
{% if event.end %}End: {{ event.end|date:"F j, Y, g:i a T" }}{% endif %}
{% if event.estimated_time_to_repair %}ETR: {{ event.estimated_time_to_repair|date:"F j, Y, g:i a T" }}{% endif %}

SUMMARY
{{ "-"|ljust:40|slice:":40" }}
{{ event.summary }}

{% if impacts %}AFFECTED SERVICES
{{ "-"|ljust:40|slice:":40" }}
{% for impact in impacts %}* {{ impact.target }} ({{ impact.get_impact_display }})
{% endfor %}{% endif %}

{{ "="|ljust:60|slice:":60" }}
Network Operations Center
"""

# Per-tenant template
PER_TENANT_TEMPLATE = """# Notification for {{ tenant.name }}

Dear {{ tenant.name }} Team,

{% if event_type == 'maintenance' %}
We are writing to inform you about scheduled maintenance that may affect your services.
{% else %}
We are writing to inform you about a service disruption that may affect your operations.
{% endif %}

## Event Details
- **Event ID:** {{ event.name }}
- **Provider:** {{ event.provider.name }}
- **Status:** {{ event.status }}
- **Scheduled:** {{ event.start|date:"F j, Y, g:i a T" }}{% if event.end %} to {{ event.end|date:"F j, Y, g:i a T" }}{% endif %}

## Impact to Your Services
{% for impact in tenant_impacts %}
| Service | Impact Level | Notes |
|---------|--------------|-------|
| {{ impact.target }} | {{ impact.get_impact_display }} | {% if impact.impact == 'OUTAGE' %}Service will be unavailable{% elif impact.impact == 'DEGRADED' %}Performance may be affected{% else %}Minimal impact expected{% endif %} |
{% endfor %}

## Recommended Actions
{% if event_type == 'maintenance' %}
1. Schedule any critical operations outside the maintenance window
2. Notify your end users of potential service interruptions
3. Ensure failover systems are ready if applicable
{% else %}
1. Monitor your systems for any anomalies
2. Contact our support team if you experience issues
3. Check our status page for real-time updates
{% endif %}

Best regards,
Network Operations Team

---
*Tenant ID: {{ tenant.pk }} | Account Manager: {{ tenant.group.name|default:"Unassigned" }}*
"""

# Per-impact template (one notification per affected service)
PER_IMPACT_TEMPLATE = """# Service Impact Notice

## Affected Service
**{{ impact.target }}**

## Impact Level
**{{ impact.get_impact_display }}**

{% if impact.impact == 'OUTAGE' %}
⛔ **CRITICAL:** This service will be completely unavailable during the event window.
{% elif impact.impact == 'DEGRADED' %}
⚠️ **WARNING:** This service may experience degraded performance or intermittent issues.
{% elif impact.impact == 'REDUCED-REDUNDANCY' %}
ℹ️ **NOTICE:** Redundancy for this service will be temporarily reduced.
{% else %}
✅ **INFO:** No significant impact expected for this service.
{% endif %}

## Event Information
- **Event:** {{ event.name }}
- **Provider:** {{ event.provider.name }}
- **Type:** {{ event_type|title }}
- **Window:** {{ event.start|date:"M j, Y g:i a" }}{% if event.end %} — {{ event.end|date:"M j, Y g:i a" }}{% endif %}

## Description
{{ event.summary }}

---
*Impact ID: {{ impact.pk }} | Generated: {{ now|date:"c" }}*
"""

# Standalone template (no event association)
STANDALONE_TEMPLATE = """# {{ subject|default:"General Notice" }}

{{ body|default:"No content provided." }}

---
*Sent via NetBox Notices*
"""


def get_or_create_contact_roles():
    """Ensure required contact roles exist."""
    print("Ensuring contact roles exist...")

    roles_data = [
        {"name": "NOC Contact", "slug": "noc-contact", "description": "Network Operations Center contacts"},
        {"name": "Technical Contact", "slug": "technical-contact", "description": "Technical escalation contacts"},
        {"name": "Emergency Contact", "slug": "emergency-contact", "description": "Emergency notification contacts"},
        {"name": "Management", "slug": "management", "description": "Management notification contacts"},
    ]

    created = []
    for role_data in roles_data:
        role, was_created = ContactRole.objects.get_or_create(
            slug=role_data["slug"],
            defaults=role_data,
        )
        if was_created:
            print(f"  Created role: {role.name}")
            created.append(role)
        else:
            print(f"  Exists role: {role.name}")

    return ContactRole.objects.filter(slug__in=[r["slug"] for r in roles_data])


def create_notification_templates(contact_roles):
    """Create comprehensive notification templates covering all use cases."""
    print("Creating notification templates...")

    noc_role = contact_roles.filter(slug="noc-contact").first()
    tech_role = contact_roles.filter(slug="technical-contact").first()
    emergency_role = contact_roles.filter(slug="emergency-contact").first()
    mgmt_role = contact_roles.filter(slug="management").first()

    templates_data = [
        # =====================================================================
        # BASE TEMPLATES (for inheritance)
        # =====================================================================
        {
            "name": "Base Notification Template",
            "slug": "base-notification",
            "description": "Base template with blocks that child templates can override. Not meant to be used directly.",
            "event_type": MessageEventTypeChoices.BOTH,
            "granularity": MessageGranularityChoices.PER_EVENT,
            "body_format": BodyFormatChoices.MARKDOWN,
            "subject_template": "[{{ event.provider.name }}] {{ event.name }}",
            "body_template": BASE_TEMPLATE_BODY,
            "css_template": CSS_MINIMAL,
            "is_base_template": True,
            "include_ical": False,
            "weight": 100,
            "contact_priorities": [],
        },
        # =====================================================================
        # MAINTENANCE TEMPLATES
        # =====================================================================
        {
            "name": "Standard Maintenance - Markdown",
            "slug": "maintenance-standard-md",
            "description": "Standard maintenance template using Markdown format. Extends base template.",
            "event_type": MessageEventTypeChoices.MAINTENANCE,
            "granularity": MessageGranularityChoices.PER_EVENT,
            "body_format": BodyFormatChoices.MARKDOWN,
            "subject_template": "[MAINTENANCE] {{ event.provider.name }}: {{ event.name }}",
            "body_template": MAINTENANCE_CHILD_TEMPLATE,
            "css_template": CSS_CORPORATE,
            "is_base_template": False,
            "extends_slug": "base-notification",
            "include_ical": True,
            "ical_template": ICAL_STANDARD,
            "weight": 1000,
            "contact_priorities": [ContactPriorityChoices.PRIMARY, ContactPriorityChoices.SECONDARY],
            "contact_roles_slugs": ["noc-contact", "technical-contact"],
        },
        {
            "name": "Maintenance - HTML Corporate",
            "slug": "maintenance-html-corporate",
            "description": "HTML maintenance template with corporate styling",
            "event_type": MessageEventTypeChoices.MAINTENANCE,
            "granularity": MessageGranularityChoices.PER_EVENT,
            "body_format": BodyFormatChoices.HTML,
            "subject_template": "[{{ event.provider.name }}] Scheduled Maintenance: {{ event.name }}",
            "body_template": HTML_TEMPLATE_BODY,
            "css_template": CSS_CORPORATE,
            "is_base_template": False,
            "include_ical": True,
            "ical_template": ICAL_WITH_ALARM,
            "weight": 1100,
            "contact_priorities": [ContactPriorityChoices.PRIMARY],
            "contact_roles_slugs": ["noc-contact"],
        },
        {
            "name": "Maintenance - Plain Text",
            "slug": "maintenance-plain-text",
            "description": "Plain text maintenance template for legacy systems",
            "event_type": MessageEventTypeChoices.MAINTENANCE,
            "granularity": MessageGranularityChoices.PER_EVENT,
            "body_format": BodyFormatChoices.TEXT,
            "subject_template": "MAINTENANCE: {{ event.name }} ({{ event.provider.name }})",
            "body_template": PLAIN_TEXT_TEMPLATE,
            "css_template": "",
            "is_base_template": False,
            "include_ical": True,
            "ical_template": ICAL_STANDARD,
            "weight": 900,
            "contact_priorities": [
                ContactPriorityChoices.PRIMARY,
                ContactPriorityChoices.SECONDARY,
                ContactPriorityChoices.TERTIARY,
            ],
        },
        {
            "name": "Maintenance - Per Tenant",
            "slug": "maintenance-per-tenant",
            "description": "Maintenance template that generates one notification per affected tenant",
            "event_type": MessageEventTypeChoices.MAINTENANCE,
            "granularity": MessageGranularityChoices.PER_TENANT,
            "body_format": BodyFormatChoices.MARKDOWN,
            "subject_template": "[{{ tenant.name }}] Maintenance Notice: {{ event.name }}",
            "body_template": PER_TENANT_TEMPLATE,
            "css_template": CSS_MINIMAL,
            "is_base_template": False,
            "include_ical": True,
            "ical_template": ICAL_STANDARD,
            "weight": 1200,
            "contact_priorities": [ContactPriorityChoices.PRIMARY],
            "contact_roles_slugs": ["technical-contact", "management"],
        },
        {
            "name": "Maintenance - Per Impact",
            "slug": "maintenance-per-impact",
            "description": "Maintenance template that generates one notification per impacted service",
            "event_type": MessageEventTypeChoices.MAINTENANCE,
            "granularity": MessageGranularityChoices.PER_IMPACT,
            "body_format": BodyFormatChoices.MARKDOWN,
            "subject_template": "[{{ impact.target }}] Maintenance Impact: {{ event.name }}",
            "body_template": PER_IMPACT_TEMPLATE,
            "css_template": CSS_MINIMAL,
            "is_base_template": False,
            "include_ical": False,
            "weight": 800,
            "contact_priorities": [ContactPriorityChoices.PRIMARY],
        },
        {
            "name": "Maintenance - Print Friendly",
            "slug": "maintenance-print-friendly",
            "description": "Print-optimized maintenance template for physical distribution",
            "event_type": MessageEventTypeChoices.MAINTENANCE,
            "granularity": MessageGranularityChoices.PER_EVENT,
            "body_format": BodyFormatChoices.HTML,
            "subject_template": "Maintenance Notice - {{ event.provider.name }} - {{ event.start|date:'Y-m-d' }}",
            "body_template": HTML_TEMPLATE_BODY,
            "css_template": CSS_PRINT_FRIENDLY,
            "is_base_template": False,
            "include_ical": False,
            "weight": 700,
        },
        # =====================================================================
        # OUTAGE TEMPLATES
        # =====================================================================
        {
            "name": "Outage Alert - Markdown",
            "slug": "outage-alert-md",
            "description": "Urgent outage alert template using Markdown. Extends base template.",
            "event_type": MessageEventTypeChoices.OUTAGE,
            "granularity": MessageGranularityChoices.PER_EVENT,
            "body_format": BodyFormatChoices.MARKDOWN,
            "subject_template": "[OUTAGE] {{ event.provider.name }}: {{ event.name }}",
            "body_template": OUTAGE_CHILD_TEMPLATE,
            "css_template": CSS_ALERT_FOCUSED,
            "is_base_template": False,
            "extends_slug": "base-notification",
            "include_ical": False,
            "weight": 1500,
            "contact_priorities": [ContactPriorityChoices.PRIMARY, ContactPriorityChoices.SECONDARY],
            "contact_roles_slugs": ["emergency-contact", "noc-contact"],
        },
        {
            "name": "Outage Alert - HTML",
            "slug": "outage-alert-html",
            "description": "HTML outage alert with prominent visual styling",
            "event_type": MessageEventTypeChoices.OUTAGE,
            "granularity": MessageGranularityChoices.PER_EVENT,
            "body_format": BodyFormatChoices.HTML,
            "subject_template": "🚨 OUTAGE: {{ event.name }} - {{ event.provider.name }}",
            "body_template": HTML_TEMPLATE_BODY,
            "css_template": CSS_ALERT_FOCUSED,
            "is_base_template": False,
            "include_ical": False,
            "weight": 1600,
            "contact_priorities": [ContactPriorityChoices.PRIMARY],
            "contact_roles_slugs": ["emergency-contact"],
        },
        {
            "name": "Outage - Dark Theme",
            "slug": "outage-dark-theme",
            "description": "Dark-themed outage template for NOC displays",
            "event_type": MessageEventTypeChoices.OUTAGE,
            "granularity": MessageGranularityChoices.PER_EVENT,
            "body_format": BodyFormatChoices.HTML,
            "subject_template": "[ALERT] Service Outage: {{ event.name }}",
            "body_template": HTML_TEMPLATE_BODY,
            "css_template": CSS_DARK_THEME,
            "is_base_template": False,
            "include_ical": False,
            "weight": 1400,
        },
        {
            "name": "Outage - Per Tenant",
            "slug": "outage-per-tenant",
            "description": "Outage template that generates one notification per affected tenant",
            "event_type": MessageEventTypeChoices.OUTAGE,
            "granularity": MessageGranularityChoices.PER_TENANT,
            "body_format": BodyFormatChoices.MARKDOWN,
            "subject_template": "[{{ tenant.name }}] URGENT: Service Outage - {{ event.name }}",
            "body_template": PER_TENANT_TEMPLATE,
            "css_template": CSS_ALERT_FOCUSED,
            "is_base_template": False,
            "include_ical": False,
            "weight": 1700,
            "contact_priorities": [ContactPriorityChoices.PRIMARY, ContactPriorityChoices.SECONDARY],
            "contact_roles_slugs": ["emergency-contact", "management"],
        },
        # =====================================================================
        # COMBINED (BOTH) TEMPLATES
        # =====================================================================
        {
            "name": "Universal Event Template",
            "slug": "universal-event",
            "description": "Template that works for both maintenance and outage events",
            "event_type": MessageEventTypeChoices.BOTH,
            "granularity": MessageGranularityChoices.PER_EVENT,
            "body_format": BodyFormatChoices.MARKDOWN,
            "subject_template": "[{{ event_type|upper }}] {{ event.provider.name }}: {{ event.name }}",
            "body_template": """# {% if event_type == 'maintenance' %}Scheduled Maintenance{% else %}Service Alert{% endif %}

**Provider:** {{ event.provider.name }}
**Event:** {{ event.name }}
**Status:** {{ event.status }}

## Timing
- **Start:** {{ event.start|date:"F j, Y, g:i a T" }}
{% if event.end %}- **End:** {{ event.end|date:"F j, Y, g:i a T" }}{% endif %}
{% if event.estimated_time_to_repair %}- **ETR:** {{ event.estimated_time_to_repair|date:"F j, Y, g:i a T" }}{% endif %}

## Description
{{ event.summary }}

{% if impacts %}
## Affected Services
| Service | Impact |
|---------|--------|
{% for impact in impacts %}| {{ impact.target }} | {{ impact.get_impact_display }} |
{% endfor %}
{% endif %}

---
*Event Type: {{ event_type|title }}*
""",
            "css_template": CSS_CORPORATE,
            "is_base_template": False,
            "include_ical": True,
            "ical_template": ICAL_STANDARD,
            "weight": 500,
            "contact_priorities": [ContactPriorityChoices.PRIMARY],
            "contact_roles_slugs": ["noc-contact"],
        },
        # =====================================================================
        # STANDALONE TEMPLATES (no event)
        # =====================================================================
        {
            "name": "Standalone Announcement",
            "slug": "standalone-announcement",
            "description": "Template for general announcements not tied to specific events",
            "event_type": MessageEventTypeChoices.NONE,
            "granularity": MessageGranularityChoices.PER_EVENT,
            "body_format": BodyFormatChoices.MARKDOWN,
            "subject_template": "{{ subject|default:'Network Announcement' }}",
            "body_template": STANDALONE_TEMPLATE,
            "css_template": CSS_MINIMAL,
            "is_base_template": False,
            "include_ical": False,
            "weight": 100,
        },
        {
            "name": "Ad-hoc HTML Notice",
            "slug": "adhoc-html-notice",
            "description": "HTML template for ad-hoc notifications without events",
            "event_type": MessageEventTypeChoices.NONE,
            "granularity": MessageGranularityChoices.PER_EVENT,
            "body_format": BodyFormatChoices.HTML,
            "subject_template": "{{ subject|default:'Notice from Network Operations' }}",
            "body_template": """<!DOCTYPE html>
<html>
<head><title>{{ subject }}</title></head>
<body>
<div style="max-width: 600px; margin: 0 auto; font-family: Arial, sans-serif;">
    <h1 style="color: #0066cc; border-bottom: 2px solid #0066cc;">{{ subject }}</h1>
    <div style="padding: 20px 0;">
        {{ body|safe }}
    </div>
    <hr style="border: none; border-top: 1px solid #ddd;">
    <p style="color: #666; font-size: 12px;">
        Network Operations Center<br>
        Generated: {{ now|date:"F j, Y, g:i a" }}
    </p>
</div>
</body>
</html>
""",
            "css_template": "",
            "is_base_template": False,
            "include_ical": False,
            "weight": 100,
        },
    ]

    created_templates = []
    extends_mapping = {}  # slug -> template object for linking extends

    # First pass: create all templates without extends relationships
    for tmpl_data in templates_data:
        extends_slug = tmpl_data.pop("extends_slug", None)
        contact_roles_slugs = tmpl_data.pop("contact_roles_slugs", [])

        # Store for second pass
        if extends_slug:
            extends_mapping[tmpl_data["slug"]] = extends_slug

        template, was_created = NotificationTemplate.objects.get_or_create(
            slug=tmpl_data["slug"],
            defaults=tmpl_data,
        )

        # Add contact roles
        if contact_roles_slugs:
            roles = ContactRole.objects.filter(slug__in=contact_roles_slugs)
            template.contact_roles.set(roles)

        if was_created:
            print(f"  Created: {template.name}")
            created_templates.append(template)
        else:
            print(f"  Exists: {template.name}")

    # Second pass: set extends relationships
    for child_slug, parent_slug in extends_mapping.items():
        try:
            child = NotificationTemplate.objects.get(slug=child_slug)
            parent = NotificationTemplate.objects.get(slug=parent_slug)
            if child.extends != parent:
                child.extends = parent
                child.save()
                print(f"  Linked: {child.name} extends {parent.name}")
        except NotificationTemplate.DoesNotExist:
            print(f"  Warning: Could not link {child_slug} -> {parent_slug}")

    return NotificationTemplate.objects.all()


def create_template_scopes(templates):
    """Create template scopes linking templates to various objects."""
    print("Creating template scopes...")

    providers = list(Provider.objects.all()[:5])
    sites = list(Site.objects.all()[:5])
    regions = list(Region.objects.all()[:3])
    site_groups = list(SiteGroup.objects.all()[:3])
    tenants = list(Tenant.objects.all()[:5])
    tenant_groups = list(TenantGroup.objects.all()[:3])

    provider_ct = ContentType.objects.get_for_model(Provider)
    site_ct = ContentType.objects.get_for_model(Site)
    region_ct = ContentType.objects.get_for_model(Region)
    site_group_ct = ContentType.objects.get_for_model(SiteGroup)
    tenant_ct = ContentType.objects.get_for_model(Tenant)
    tenant_group_ct = ContentType.objects.get_for_model(TenantGroup)

    created = []

    # Provider-specific scopes
    if providers:
        for template in templates.filter(slug__in=["maintenance-standard-md", "outage-alert-md"])[:2]:
            for i, provider in enumerate(providers[:3]):
                scope, was_created = TemplateScope.objects.get_or_create(
                    template=template,
                    content_type=provider_ct,
                    object_id=provider.pk,
                    defaults={
                        "event_type": template.event_type,
                        "weight": template.weight + (i * 10),
                    },
                )
                if was_created:
                    print(f"  Created scope: {template.name} -> Provider:{provider.name}")
                    created.append(scope)

    # Site-specific scopes
    if sites:
        for template in templates.filter(slug__in=["maintenance-html-corporate", "outage-alert-html"])[:2]:
            for site in sites[:2]:
                scope, was_created = TemplateScope.objects.get_or_create(
                    template=template,
                    content_type=site_ct,
                    object_id=site.pk,
                    defaults={
                        "event_type": template.event_type,
                        "weight": template.weight,
                    },
                )
                if was_created:
                    print(f"  Created scope: {template.name} -> Site:{site.name}")
                    created.append(scope)

    # Region-wide scopes (object_id=None means "all of this type")
    if regions:
        for template in templates.filter(slug="universal-event")[:1]:
            for region in regions[:2]:
                scope, was_created = TemplateScope.objects.get_or_create(
                    template=template,
                    content_type=region_ct,
                    object_id=region.pk,
                    defaults={
                        "event_type": MessageEventTypeChoices.BOTH,
                        "weight": 600,
                    },
                )
                if was_created:
                    print(f"  Created scope: {template.name} -> Region:{region.name}")
                    created.append(scope)

    # Tenant-specific scopes (for per-tenant templates)
    if tenants:
        for template in templates.filter(slug__in=["maintenance-per-tenant", "outage-per-tenant"]):
            for tenant in tenants[:3]:
                scope, was_created = TemplateScope.objects.get_or_create(
                    template=template,
                    content_type=tenant_ct,
                    object_id=tenant.pk,
                    defaults={
                        "event_type": template.event_type,
                        "weight": template.weight,
                    },
                )
                if was_created:
                    print(f"  Created scope: {template.name} -> Tenant:{tenant.name}")
                    created.append(scope)

    # Tenant group scopes
    if tenant_groups:
        for template in templates.filter(slug="maintenance-per-tenant")[:1]:
            for tg in tenant_groups[:2]:
                scope, was_created = TemplateScope.objects.get_or_create(
                    template=template,
                    content_type=tenant_group_ct,
                    object_id=tg.pk,
                    defaults={
                        "event_type": MessageEventTypeChoices.MAINTENANCE,
                        "weight": 1300,
                    },
                )
                if was_created:
                    print(f"  Created scope: {template.name} -> TenantGroup:{tg.name}")
                    created.append(scope)

    # Status-specific scopes
    status_templates = templates.filter(slug__in=["maintenance-standard-md"])
    for template in status_templates:
        for status in [MaintenanceTypeChoices.STATUS_CONFIRMED, MaintenanceTypeChoices.STATUS_IN_PROCESS]:
            if providers:
                scope, was_created = TemplateScope.objects.get_or_create(
                    template=template,
                    content_type=provider_ct,
                    object_id=providers[0].pk,
                    event_status=status,
                    defaults={
                        "event_type": MessageEventTypeChoices.MAINTENANCE,
                        "weight": 1500 if status == MaintenanceTypeChoices.STATUS_IN_PROCESS else 1000,
                    },
                )
                if was_created:
                    print(f"  Created scope: {template.name} -> Provider:{providers[0].name} (status={status})")
                    created.append(scope)

    return created


def create_maintenances():
    """Create maintenance events with various statuses."""
    print("Creating maintenance events...")

    providers = list(Provider.objects.all()[:6])
    if not providers:
        print("  No providers found in demo data!")
        return []

    now = timezone.now()

    maintenances_data = [
        {
            "name": "MAINT-2024-001: Core Router Upgrade",
            "provider": providers[0],
            "status": MaintenanceTypeChoices.STATUS_CONFIRMED,
            "start": now + timedelta(days=7),
            "end": now + timedelta(days=7, hours=4),
            "summary": "Upgrading core routers to latest firmware version. Expected brief traffic disruption during failover.",
            "acknowledged": True,
            "internal_ticket": "CHG0012345",
            "original_timezone": "America/New_York",
        },
        {
            "name": "MAINT-2024-002: Fiber Splice Work",
            "provider": providers[1] if len(providers) > 1 else providers[0],
            "status": MaintenanceTypeChoices.STATUS_TENTATIVE,
            "start": now + timedelta(days=14),
            "end": now + timedelta(days=14, hours=6),
            "summary": "Scheduled fiber splice work on backbone ring. Redundant path available.",
            "acknowledged": False,
            "original_timezone": "America/Chicago",
        },
        {
            "name": "MAINT-2024-003: DC Power Maintenance",
            "provider": providers[2] if len(providers) > 2 else providers[0],
            "status": MaintenanceTypeChoices.STATUS_IN_PROCESS,
            "start": now - timedelta(hours=2),
            "end": now + timedelta(hours=2),
            "summary": "Data center power system maintenance. Currently operating on generator backup.",
            "acknowledged": True,
            "internal_ticket": "CHG0012400",
        },
        {
            "name": "MAINT-2024-004: Completed Switch Replacement",
            "provider": providers[0],
            "status": MaintenanceTypeChoices.STATUS_COMPLETED,
            "start": now - timedelta(days=3),
            "end": now - timedelta(days=3) + timedelta(hours=2),
            "summary": "Successfully replaced end-of-life access switches in distribution layer.",
            "acknowledged": True,
            "internal_ticket": "CHG0012100",
        },
        {
            "name": "MAINT-2024-005: Cancelled Window",
            "provider": providers[3] if len(providers) > 3 else providers[0],
            "status": MaintenanceTypeChoices.STATUS_CANCELLED,
            "start": now + timedelta(days=5),
            "end": now + timedelta(days=5, hours=3),
            "summary": "Maintenance cancelled due to vendor equipment delay. Will be rescheduled.",
            "acknowledged": True,
        },
        {
            "name": "MAINT-2024-006: Rescheduled Firmware Update",
            "provider": providers[4] if len(providers) > 4 else providers[0],
            "status": MaintenanceTypeChoices.STATUS_RESCHEDULED,
            "start": now + timedelta(days=21),
            "end": now + timedelta(days=21, hours=4),
            "summary": "Firmware update rescheduled from original date. New security patches included.",
            "acknowledged": False,
            "internal_ticket": "CHG0012500",
        },
        {
            "name": "MAINT-2024-007: Unknown Status Event",
            "provider": providers[5] if len(providers) > 5 else providers[0],
            "status": MaintenanceTypeChoices.STATUS_UNKNOWN,
            "start": now + timedelta(days=30),
            "end": now + timedelta(days=30, hours=8),
            "summary": "Provider notification received but details unclear. Awaiting clarification.",
            "acknowledged": False,
        },
        {
            "name": "MAINT-2024-008: Multi-Site Backbone Work",
            "provider": providers[0],
            "status": MaintenanceTypeChoices.STATUS_CONFIRMED,
            "start": now + timedelta(days=10),
            "end": now + timedelta(days=10, hours=12),
            "summary": "Major backbone upgrade affecting multiple sites. Traffic will be rerouted via secondary paths.",
            "acknowledged": True,
            "internal_ticket": "CHG0012600",
            "impact": "Services may experience increased latency during the maintenance window.",
        },
    ]

    created = []
    for maint_data in maintenances_data:
        maint, was_created = Maintenance.objects.get_or_create(
            name=maint_data["name"],
            provider=maint_data["provider"],
            defaults=maint_data,
        )
        if was_created:
            print(f"  Created: {maint.name} ({maint.status})")
            created.append(maint)
        else:
            print(f"  Exists: {maint.name}")

    return list(Maintenance.objects.all())


def create_outages():
    """Create outage events with various statuses."""
    print("Creating outage events...")

    providers = list(Provider.objects.all()[:5])
    if not providers:
        print("  No providers found in demo data!")
        return []

    now = timezone.now()

    outages_data = [
        {
            "name": "OUT-2024-001: Regional Network Disruption",
            "provider": providers[0],
            "status": OutageStatusChoices.STATUS_INVESTIGATING,
            "start": now - timedelta(hours=1),
            "reported_at": now - timedelta(minutes=50),
            "end": None,
            "summary": "Multiple customer reports of connectivity issues in northeast region. Engineering investigating.",
            "acknowledged": True,
            "internal_ticket": "INC0098765",
        },
        {
            "name": "OUT-2024-002: DNS Resolution Failure",
            "provider": providers[1] if len(providers) > 1 else providers[0],
            "status": OutageStatusChoices.STATUS_RESOLVED,
            "start": now - timedelta(days=1),
            "reported_at": now - timedelta(days=1),
            "end": now - timedelta(days=1) + timedelta(hours=1),
            "summary": "DNS resolver misconfiguration caused resolution failures. Issue identified and corrected.",
            "acknowledged": True,
            "internal_ticket": "INC0098700",
        },
        {
            "name": "OUT-2024-003: Circuit Hard Down",
            "provider": providers[2] if len(providers) > 2 else providers[0],
            "status": OutageStatusChoices.STATUS_IDENTIFIED,
            "start": now - timedelta(minutes=30),
            "reported_at": now - timedelta(minutes=25),
            "end": None,
            "estimated_time_to_repair": now + timedelta(hours=2),
            "summary": "Fiber cut identified on primary circuit. Repair crew dispatched. ETR 2 hours.",
            "acknowledged": True,
            "internal_ticket": "INC0098800",
        },
        {
            "name": "OUT-2024-004: Monitoring Alert",
            "provider": providers[3] if len(providers) > 3 else providers[0],
            "status": OutageStatusChoices.STATUS_MONITORING,
            "start": now - timedelta(hours=4),
            "reported_at": now - timedelta(hours=4),
            "end": None,
            "estimated_time_to_repair": now + timedelta(hours=1),
            "summary": "Intermittent packet loss detected. Root cause addressed, monitoring for recurrence.",
            "acknowledged": True,
        },
        {
            "name": "OUT-2024-005: New Outage Report",
            "provider": providers[0],
            "status": OutageStatusChoices.STATUS_REPORTED,
            "start": now - timedelta(minutes=5),
            "reported_at": now - timedelta(minutes=3),
            "end": None,
            "summary": "Customer reported complete loss of connectivity. Initial triage in progress.",
            "acknowledged": False,
        },
    ]

    created = []
    for outage_data in outages_data:
        outage, was_created = Outage.objects.get_or_create(
            name=outage_data["name"],
            provider=outage_data["provider"],
            defaults=outage_data,
        )
        if was_created:
            print(f"  Created: {outage.name} ({outage.status})")
            created.append(outage)
        else:
            print(f"  Exists: {outage.name}")

    return list(Outage.objects.all())


def create_impacts(maintenances, outages):
    """Create comprehensive impact records."""
    print("Creating impact records...")

    circuits = list(Circuit.objects.all()[:15])
    devices = list(Device.objects.all()[:15])
    sites = list(Site.objects.all()[:10])
    vms = list(VirtualMachine.objects.all()[:10])
    clusters = list(Cluster.objects.all()[:5])

    circuit_ct = ContentType.objects.get_for_model(Circuit)
    device_ct = ContentType.objects.get_for_model(Device)
    site_ct = ContentType.objects.get_for_model(Site)
    vm_ct = ContentType.objects.get_for_model(VirtualMachine)
    cluster_ct = ContentType.objects.get_for_model(Cluster)
    maintenance_ct = ContentType.objects.get_for_model(Maintenance)
    outage_ct = ContentType.objects.get_for_model(Outage)

    created = []

    # Active maintenances get impacts
    active_maintenances = [
        m
        for m in maintenances
        if m.status not in [MaintenanceTypeChoices.STATUS_COMPLETED, MaintenanceTypeChoices.STATUS_CANCELLED]
    ]

    for i, maint in enumerate(active_maintenances):
        impacts_to_create = []

        # Circuits - primary impact type for network maintenance
        if circuits:
            for j in range(min(3, len(circuits))):
                idx = (i + j) % len(circuits)
                impacts_to_create.append(
                    {
                        "target_content_type": circuit_ct,
                        "target_object_id": circuits[idx].pk,
                        "impact": [
                            ImpactTypeChoices.IMPACT_DEGRADED,
                            ImpactTypeChoices.IMPACT_REDUCED_REDUNDANCY,
                            ImpactTypeChoices.IMPACT_NO_IMPACT,
                        ][j % 3],
                    }
                )

        # Devices
        if devices and i % 2 == 0:
            for j in range(min(2, len(devices))):
                idx = (i + j) % len(devices)
                impacts_to_create.append(
                    {
                        "target_content_type": device_ct,
                        "target_object_id": devices[idx].pk,
                        "impact": ImpactTypeChoices.IMPACT_REDUCED_REDUNDANCY,
                    }
                )

        # Sites
        if sites and i % 3 == 0:
            idx = i % len(sites)
            impacts_to_create.append(
                {
                    "target_content_type": site_ct,
                    "target_object_id": sites[idx].pk,
                    "impact": ImpactTypeChoices.IMPACT_NO_IMPACT,
                }
            )

        # VMs
        if vms and i % 2 == 1:
            idx = i % len(vms)
            impacts_to_create.append(
                {
                    "target_content_type": vm_ct,
                    "target_object_id": vms[idx].pk,
                    "impact": ImpactTypeChoices.IMPACT_DEGRADED,
                }
            )

        for impact_data in impacts_to_create:
            impact, was_created = Impact.objects.get_or_create(
                event_content_type=maintenance_ct,
                event_object_id=maint.pk,
                target_content_type=impact_data["target_content_type"],
                target_object_id=impact_data["target_object_id"],
                defaults={"impact": impact_data["impact"]},
            )
            if was_created:
                print(f"  Created: {maint.name} -> {impact.target} ({impact_data['impact']})")
                created.append(impact)

    # Active outages get more severe impacts
    active_outages = [o for o in outages if o.status != OutageStatusChoices.STATUS_RESOLVED]

    for i, outage in enumerate(active_outages):
        impacts_to_create = []

        # Circuits - outages typically mean full outage
        if circuits:
            for j in range(min(2, len(circuits))):
                idx = (i * 3 + j + 5) % len(circuits)
                impacts_to_create.append(
                    {
                        "target_content_type": circuit_ct,
                        "target_object_id": circuits[idx].pk,
                        "impact": ImpactTypeChoices.IMPACT_OUTAGE,
                    }
                )

        # Devices
        if devices:
            idx = (i * 2 + 3) % len(devices)
            impacts_to_create.append(
                {
                    "target_content_type": device_ct,
                    "target_object_id": devices[idx].pk,
                    "impact": ImpactTypeChoices.IMPACT_OUTAGE,
                }
            )

        # VMs
        if vms:
            idx = (i + 2) % len(vms)
            impacts_to_create.append(
                {
                    "target_content_type": vm_ct,
                    "target_object_id": vms[idx].pk,
                    "impact": ImpactTypeChoices.IMPACT_OUTAGE,
                }
            )

        # Clusters
        if clusters and i == 0:
            impacts_to_create.append(
                {
                    "target_content_type": cluster_ct,
                    "target_object_id": clusters[0].pk,
                    "impact": ImpactTypeChoices.IMPACT_DEGRADED,
                }
            )

        for impact_data in impacts_to_create:
            impact, was_created = Impact.objects.get_or_create(
                event_content_type=outage_ct,
                event_object_id=outage.pk,
                target_content_type=impact_data["target_content_type"],
                target_object_id=impact_data["target_object_id"],
                defaults={"impact": impact_data["impact"]},
            )
            if was_created:
                print(f"  Created: {outage.name} -> {impact.target} ({impact_data['impact']})")
                created.append(impact)

    return created


def create_event_notifications(maintenances, outages):
    """Create event notifications (received from providers)."""
    print("Creating event notifications...")

    events = maintenances[:5] + outages[:3]
    now = timezone.now()
    maintenance_ct = ContentType.objects.get_for_model(Maintenance)
    outage_ct = ContentType.objects.get_for_model(Outage)

    created = []
    for i, event in enumerate(events):
        if isinstance(event, Maintenance):
            event_ct = maintenance_ct
            notif_type = "Maintenance"
        else:
            event_ct = outage_ct
            notif_type = "Outage"

        # Create multiple notifications per event (initial + updates)
        for update_num in range(1, 3 if i < 3 else 2):
            email_body = f"""From: NOC <noc@{event.provider.slug}.example.com>
To: notifications@example.com
Subject: [{notif_type}] {event.name} - Update #{update_num}
Date: {(now - timedelta(days=i, hours=update_num)).strftime('%a, %d %b %Y %H:%M:%S %z')}
Content-Type: text/plain; charset="UTF-8"
X-Priority: {'1 (Highest)' if isinstance(event, Outage) else '3 (Normal)'}

{'=' * 60}
{notif_type.upper()} NOTIFICATION - UPDATE #{update_num}
{'=' * 60}

Event ID: {event.name}
Provider: {event.provider.name}
Status: {event.status}

Start Time: {event.start.strftime('%Y-%m-%d %H:%M %Z')}
{'End Time: ' + event.end.strftime('%Y-%m-%d %H:%M %Z') if event.end else 'End Time: TBD'}

SUMMARY
{'-' * 40}
{event.summary}

{'This is update #' + str(update_num) + ' for this event.' if update_num > 1 else 'Initial notification.'}

{'=' * 60}
This is an automated notification from {event.provider.name}.
For questions, contact: noc@{event.provider.slug}.example.com
{'=' * 60}
"""
            subject = f"[{event.provider.name}] {event.name}"
            if update_num > 1:
                subject += f" - Update #{update_num}"

            notification_data = {
                "event_content_type": event_ct,
                "event_object_id": event.pk,
                "subject": subject[:100],
                "email_from": f"noc@{event.provider.slug}.example.com",
                "email_received": now - timedelta(days=i, hours=update_num),
                "email": email_body.encode("utf-8"),
                "email_body": email_body,
            }

            exists = EventNotification.objects.filter(
                event_content_type=notification_data["event_content_type"],
                event_object_id=notification_data["event_object_id"],
                subject=notification_data["subject"],
            ).exists()

            if not exists:
                notification = EventNotification.objects.create(**notification_data)
                print(f"  Created: {notification.subject}")
                created.append(notification)
            else:
                print(f"  Exists: {notification_data['subject']}")

    return created


def create_prepared_notifications(maintenances, outages, templates):
    """Create prepared notifications in various statuses."""
    print("Creating prepared notifications...")

    admin_user = User.objects.filter(is_superuser=True).first()
    now = timezone.now()
    maintenance_ct = ContentType.objects.get_for_model(Maintenance)
    outage_ct = ContentType.objects.get_for_model(Outage)

    # Get contacts for assignment
    contacts = list(Contact.objects.all()[:10])

    created = []
    all_statuses = [
        PreparedNotificationStatusChoices.DRAFT,
        PreparedNotificationStatusChoices.READY,
        PreparedNotificationStatusChoices.SENT,
        PreparedNotificationStatusChoices.DELIVERED,
        PreparedNotificationStatusChoices.FAILED,
    ]

    # Create notifications for maintenances
    maintenance_templates = templates.filter(
        event_type__in=[MessageEventTypeChoices.MAINTENANCE, MessageEventTypeChoices.BOTH]
    )[:4]

    for i, maint in enumerate(maintenances[:6]):
        template = list(maintenance_templates)[i % len(maintenance_templates)] if maintenance_templates else None
        if not template:
            continue

        status = all_statuses[i % len(all_statuses)]

        body_text = f"""Dear Customer,

This is a notification regarding: {maint.name}

Provider: {maint.provider.name}
Status: {maint.status}
Scheduled: {maint.start.strftime('%B %d, %Y at %I:%M %p')} to {maint.end.strftime('%B %d, %Y at %I:%M %p') if maint.end else 'TBD'}

{maint.summary}

Please contact your account manager if you have questions.

Best regards,
Network Operations
"""

        notification_data = {
            "template": template,
            "event_content_type": maintenance_ct,
            "event_id": maint.pk,
            "subject": f"[{maint.provider.name}] {maint.name}",
            "body_text": body_text,
            "body_html": f"<html><body><pre>{body_text}</pre></body></html>",
            "status": status,
            "headers": {"X-Event-Type": "maintenance", "X-Event-ID": str(maint.pk)},
            "recipients": [{"email": f"user{j}@example.com", "name": f"User {j}"} for j in range(3)],
            "css": template.css_template,
        }

        if status in [
            PreparedNotificationStatusChoices.READY,
            PreparedNotificationStatusChoices.SENT,
            PreparedNotificationStatusChoices.DELIVERED,
        ]:
            notification_data["approved_by"] = admin_user
            notification_data["approved_at"] = now - timedelta(hours=i + 2)

        if status in [PreparedNotificationStatusChoices.SENT, PreparedNotificationStatusChoices.DELIVERED]:
            notification_data["sent_at"] = now - timedelta(hours=i + 1)

        if status == PreparedNotificationStatusChoices.DELIVERED:
            notification_data["delivered_at"] = now - timedelta(hours=i, minutes=30)
            notification_data["viewed_at"] = now - timedelta(hours=i, minutes=15)

        exists = PreparedNotification.objects.filter(
            event_content_type=notification_data["event_content_type"],
            event_id=notification_data["event_id"],
            template=notification_data["template"],
        ).exists()

        if not exists:
            notification = PreparedNotification.objects.create(**notification_data)
            # Assign contacts
            if contacts and status != PreparedNotificationStatusChoices.DRAFT:
                notification.contacts.set(contacts[: min(5, len(contacts))])
            print(f"  Created: {notification.subject} ({status})")
            created.append(notification)
        else:
            print(f"  Exists: Notification for {maint.name}")

    # Create notifications for outages
    outage_templates = templates.filter(event_type__in=[MessageEventTypeChoices.OUTAGE, MessageEventTypeChoices.BOTH])[
        :3
    ]

    for i, outage in enumerate(outages[:4]):
        template = list(outage_templates)[i % len(outage_templates)] if outage_templates else None
        if not template:
            continue

        status = all_statuses[(i + 2) % len(all_statuses)]

        body_text = f"""URGENT: Service Outage Alert

Event: {outage.name}
Provider: {outage.provider.name}
Status: {outage.status}
Detected: {outage.start.strftime('%B %d, %Y at %I:%M %p')}
{'ETR: ' + outage.estimated_time_to_repair.strftime('%B %d, %Y at %I:%M %p') if outage.estimated_time_to_repair else ''}

{outage.summary}

Our team is working to resolve this issue. Updates will follow.

Network Operations Center
"""

        notification_data = {
            "template": template,
            "event_content_type": outage_ct,
            "event_id": outage.pk,
            "subject": f"[OUTAGE] {outage.provider.name}: {outage.name}",
            "body_text": body_text,
            "body_html": f"<html><body><div style='color:red;font-weight:bold;'>OUTAGE ALERT</div><pre>{body_text}</pre></body></html>",
            "status": status,
            "headers": {"X-Event-Type": "outage", "X-Event-ID": str(outage.pk), "X-Priority": "1"},
            "recipients": [{"email": f"oncall{j}@example.com", "name": f"On-Call {j}"} for j in range(2)],
            "css": template.css_template,
        }

        if status in [
            PreparedNotificationStatusChoices.READY,
            PreparedNotificationStatusChoices.SENT,
            PreparedNotificationStatusChoices.DELIVERED,
        ]:
            notification_data["approved_by"] = admin_user
            notification_data["approved_at"] = now - timedelta(minutes=30 + i * 10)

        if status in [PreparedNotificationStatusChoices.SENT, PreparedNotificationStatusChoices.DELIVERED]:
            notification_data["sent_at"] = now - timedelta(minutes=20 + i * 5)

        if status == PreparedNotificationStatusChoices.DELIVERED:
            notification_data["delivered_at"] = now - timedelta(minutes=15 + i * 3)

        exists = PreparedNotification.objects.filter(
            event_content_type=notification_data["event_content_type"],
            event_id=notification_data["event_id"],
            template=notification_data["template"],
        ).exists()

        if not exists:
            notification = PreparedNotification.objects.create(**notification_data)
            if contacts:
                notification.contacts.set(contacts[2 : min(7, len(contacts))])
            print(f"  Created: {notification.subject} ({status})")
            created.append(notification)
        else:
            print(f"  Exists: Notification for {outage.name}")

    # Create standalone notifications (no event)
    standalone_templates = templates.filter(event_type=MessageEventTypeChoices.NONE)
    for i, template in enumerate(standalone_templates[:2]):
        notification_data = {
            "template": template,
            "event_content_type": None,
            "event_id": None,
            "subject": f"Network Operations Update #{i + 1}",
            "body_text": f"This is a standalone notification #{i + 1} for general announcements.",
            "body_html": f"<p>This is a standalone notification #{i + 1} for general announcements.</p>",
            "status": PreparedNotificationStatusChoices.DRAFT,
            "headers": {},
            "recipients": [],
        }

        exists = PreparedNotification.objects.filter(
            template=template,
            subject=notification_data["subject"],
        ).exists()

        if not exists:
            notification = PreparedNotification.objects.create(**notification_data)
            print(f"  Created: {notification.subject} (standalone)")
            created.append(notification)

    return created


def main():
    """Load all comprehensive demo data."""
    print("=" * 70)
    print("Loading COMPREHENSIVE netbox-notices plugin demo data")
    print("=" * 70)
    print()

    # Create contact roles first
    contact_roles = get_or_create_contact_roles()
    print()

    # Create templates with all variations
    templates = create_notification_templates(contact_roles)
    print()

    # Create template scopes
    create_template_scopes(templates)
    print()

    # Create events
    maintenances = create_maintenances()
    print()

    outages = create_outages()
    print()

    # Create impacts
    create_impacts(maintenances, outages)
    print()

    # Create event notifications
    create_event_notifications(maintenances, outages)
    print()

    # Create prepared notifications
    create_prepared_notifications(maintenances, outages, templates)
    print()

    # Summary
    print("=" * 70)
    print("DEMO DATA SUMMARY")
    print("=" * 70)
    print(f"  Contact Roles: {ContactRole.objects.count()}")
    print(f"  Notification Templates: {NotificationTemplate.objects.count()}")
    print(f"    - Base templates: {NotificationTemplate.objects.filter(is_base_template=True).count()}")
    print(f"    - Child templates: {NotificationTemplate.objects.filter(extends__isnull=False).count()}")
    print(
        f"    - Maintenance: {NotificationTemplate.objects.filter(event_type=MessageEventTypeChoices.MAINTENANCE).count()}"
    )
    print(f"    - Outage: {NotificationTemplate.objects.filter(event_type=MessageEventTypeChoices.OUTAGE).count()}")
    print(f"    - Both: {NotificationTemplate.objects.filter(event_type=MessageEventTypeChoices.BOTH).count()}")
    print(f"    - Standalone: {NotificationTemplate.objects.filter(event_type=MessageEventTypeChoices.NONE).count()}")
    print(f"  Template Scopes: {TemplateScope.objects.count()}")
    print(f"  Maintenances: {Maintenance.objects.count()}")
    print(f"  Outages: {Outage.objects.count()}")
    print(f"  Impacts: {Impact.objects.count()}")
    print(f"  Event Notifications (received): {EventNotification.objects.count()}")
    print(f"  Prepared Notifications: {PreparedNotification.objects.count()}")
    print(f"    - Draft: {PreparedNotification.objects.filter(status=PreparedNotificationStatusChoices.DRAFT).count()}")
    print(f"    - Ready: {PreparedNotification.objects.filter(status=PreparedNotificationStatusChoices.READY).count()}")
    print(f"    - Sent: {PreparedNotification.objects.filter(status=PreparedNotificationStatusChoices.SENT).count()}")
    print(
        f"    - Delivered: {PreparedNotification.objects.filter(status=PreparedNotificationStatusChoices.DELIVERED).count()}"
    )
    print(
        f"    - Failed: {PreparedNotification.objects.filter(status=PreparedNotificationStatusChoices.FAILED).count()}"
    )
    print("=" * 70)
    print("Demo data loading complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
