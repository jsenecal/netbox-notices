"""
Tracking Lambda — Process SES delivery events and update notification status in NetBox.

Receives SNS messages containing SES event notifications. Extracts the
notification_id from the mail tags and maps SES event types to NetBox
status transitions or journal entries.

Event → Action mapping:
  Delivery           → PATCH status to "delivered"
  Bounce             → PATCH status to "failed"
  Complaint          → PATCH status to "failed"
  Reject             → PATCH status to "failed"
  RenderingFailure   → PATCH status to "failed"
  Send               → Journal entry only (informational)
  Open               → Journal entry only (informational)
  Click              → Journal entry only (informational)
  DeliveryDelay      → Journal entry only (informational)
"""

import json
import logging
import os

import requests

logger = logging.getLogger()
logger.setLevel(logging.INFO)

NETBOX_URL = os.environ["NETBOX_URL"].rstrip("/")
NETBOX_API_TOKEN = os.environ["NETBOX_API_TOKEN"]

HEADERS = {
    "Authorization": f"Token {NETBOX_API_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# SES events that trigger a status change
STATUS_EVENTS = {
    "Delivery": "delivered",
    "Bounce": "failed",
    "Complaint": "failed",
    "Reject": "failed",
    "Rendering Failure": "failed",
}

# SES events that only create a journal entry
JOURNAL_ONLY_EVENTS = {"Send", "Open", "Click", "DeliveryDelay"}


def _extract_notification_id(ses_event):
    """Extract notification_id from SES mail tags."""
    mail = ses_event.get("mail", {})
    tags = mail.get("tags", {})

    # SES tags are key → [list of values]
    ids = tags.get("notification_id", [])
    if ids:
        return ids[0]
    return None


def _build_message(event_type, ses_event):
    """Build a human-readable message from the SES event."""
    if event_type == "Delivery":
        delivery = ses_event.get("delivery", {})
        recipients = delivery.get("recipients", [])
        smtp_response = delivery.get("smtpResponse", "")
        return f"Delivered to {', '.join(recipients)}. SMTP: {smtp_response}"

    if event_type == "Bounce":
        bounce = ses_event.get("bounce", {})
        bounce_type = bounce.get("bounceType", "unknown")
        bounce_sub = bounce.get("bounceSubType", "unknown")
        recipients = [r.get("emailAddress", "") for r in bounce.get("bouncedRecipients", [])]
        return f"Bounce ({bounce_type}/{bounce_sub}) for {', '.join(recipients)}"

    if event_type == "Complaint":
        complaint = ses_event.get("complaint", {})
        feedback = complaint.get("complaintFeedbackType", "unknown")
        recipients = [r.get("emailAddress", "") for r in complaint.get("complainedRecipients", [])]
        return f"Complaint ({feedback}) from {', '.join(recipients)}"

    if event_type == "Reject":
        reason = ses_event.get("reject", {}).get("reason", "unknown")
        return f"Rejected: {reason}"

    if event_type == "Rendering Failure":
        failure = ses_event.get("failure", {})
        error = failure.get("errorMessage", "unknown")
        return f"Rendering failure: {error}"

    if event_type == "Send":
        return "Email accepted by SES for delivery"

    if event_type == "Open":
        open_data = ses_event.get("open", {})
        ip = open_data.get("ipAddress", "unknown")
        ua = open_data.get("userAgent", "unknown")
        return f"Opened from {ip} ({ua})"

    if event_type == "Click":
        click = ses_event.get("click", {})
        link = click.get("link", "unknown")
        return f"Link clicked: {link}"

    if event_type == "DeliveryDelay":
        delay = ses_event.get("deliveryDelay", {})
        delay_type = delay.get("delayType", "unknown")
        return f"Delivery delayed: {delay_type}"

    return f"SES event: {event_type}"


def _patch_status(notification_id, status, message):
    """Update notification status in NetBox via PATCH."""
    url = f"{NETBOX_URL}/api/plugins/notices/prepared-notifications/{notification_id}/"
    payload = {
        "status": status,
        "message": message,
    }
    resp = requests.patch(url, json=payload, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _create_journal_entry(notification_id, message):
    """Create a journal entry on the PreparedNotification in NetBox."""
    # First, get the notification to find its content type
    url = f"{NETBOX_URL}/api/plugins/notices/prepared-notifications/{notification_id}/"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    # Create journal entry via the extras API
    journal_url = f"{NETBOX_URL}/api/extras/journal-entries/"
    payload = {
        "assigned_object_type": "notices.preparednotification",
        "assigned_object_id": int(notification_id),
        "kind": "info",
        "comments": message,
    }
    resp = requests.post(journal_url, json=payload, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _process_ses_event(ses_event):
    """Process a single SES event notification."""
    event_type = ses_event.get("eventType", "")
    notification_id = _extract_notification_id(ses_event)

    if not notification_id:
        logger.warning("No notification_id tag found in SES event, skipping")
        return

    logger.info("Processing %s event for notification %s", event_type, notification_id)
    message = _build_message(event_type, ses_event)

    if event_type in STATUS_EVENTS:
        new_status = STATUS_EVENTS[event_type]
        logger.info("Updating notification %s to status '%s'", notification_id, new_status)
        _patch_status(notification_id, new_status, message)

    elif event_type in JOURNAL_ONLY_EVENTS:
        logger.info("Creating journal entry for notification %s: %s", notification_id, event_type)
        _create_journal_entry(notification_id, f"[SES {event_type}] {message}")

    else:
        logger.warning("Unknown SES event type: %s", event_type)


def lambda_handler(event, context):
    """Main entry point — processes SNS messages containing SES events."""
    records = event.get("Records", [])
    logger.info("Received %d SNS record(s)", len(records))

    for record in records:
        sns_message = record.get("Sns", {}).get("Message", "{}")

        try:
            ses_event = json.loads(sns_message)
        except json.JSONDecodeError:
            logger.exception("Failed to parse SNS message as JSON")
            continue

        try:
            _process_ses_event(ses_event)
        except Exception:
            logger.exception("Error processing SES event")

    return {"processed": len(records)}
