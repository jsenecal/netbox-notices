"""
Outbound Lambda — Send prepared notifications via SES.

Supports two trigger modes:

1. **Schedule (EventBridge)** — Polls NetBox for all notifications in "ready"
   status and sends each one. This is the default mode.

2. **Webhook (API Gateway)** — Receives a NetBox Event Rule webhook POST when a
   single notification transitions to "ready" status. Validates the
   X-Hook-Signature header (HMAC-SHA512) and sends that one notification
   immediately.

For each notification:
  1. Build a MIME message (HTML + text + optional iCal attachment + custom headers)
  2. Send via ses:SendRawEmail with Configuration Set and notification_id tag
  3. PATCH status to "sent" (or "failed" on error)
"""

import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timezone
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import boto3
import requests

logger = logging.getLogger()
logger.setLevel(logging.INFO)

NETBOX_URL = os.environ["NETBOX_URL"].rstrip("/")
NETBOX_API_TOKEN = os.environ["NETBOX_API_TOKEN"]
SES_FROM_ADDRESS = os.environ["SES_FROM_ADDRESS"]
SES_CONFIGURATION_SET = os.environ.get("SES_CONFIGURATION_SET", "")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")

HEADERS = {
    "Authorization": f"Token {NETBOX_API_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

ses_client = boto3.client("ses")


def _build_mime(notification):
    """Build a MIME message from a prepared notification."""
    recipients = notification.get("recipients") or []
    to_addrs = [r["email"] for r in recipients if r.get("email")]

    if not to_addrs:
        raise ValueError("No recipient email addresses found")

    msg = MIMEMultipart("mixed")
    msg["Subject"] = notification.get("subject", "")
    msg["From"] = SES_FROM_ADDRESS
    msg["To"] = ", ".join(to_addrs)

    # Add custom headers from the notification
    headers = notification.get("headers") or {}
    for name, value in headers.items():
        msg[name] = str(value)

    # Build the body (alternative part for text + HTML)
    body_text = notification.get("body_text") or ""
    body_html = notification.get("body_html") or ""

    if body_html:
        alt = MIMEMultipart("alternative")
        if body_text:
            alt.attach(MIMEText(body_text, "plain", "utf-8"))
        # Inline CSS into a full HTML document if CSS is present
        css = notification.get("css") or ""
        if css:
            html_content = f"<html><head><style>{css}</style></head><body>{body_html}</body></html>"
        else:
            html_content = body_html
        alt.attach(MIMEText(html_content, "html", "utf-8"))
        msg.attach(alt)
    elif body_text:
        msg.attach(MIMEText(body_text, "plain", "utf-8"))

    # Attach iCal if present
    ical_content = notification.get("ical_content") or ""
    if ical_content:
        ical_part = MIMEBase("text", "calendar", method="REQUEST")
        ical_part.set_payload(ical_content.encode("utf-8"))
        encoders.encode_base64(ical_part)
        ical_part.add_header("Content-Disposition", "attachment", filename="maintenance.ics")
        msg.attach(ical_part)

    return msg, to_addrs


def _send_via_ses(mime_msg, to_addrs, notification_id):
    """Send a MIME message via SES with tracking tags."""
    kwargs = {
        "Source": SES_FROM_ADDRESS,
        "Destinations": to_addrs,
        "RawMessage": {"Data": mime_msg.as_string()},
        "Tags": [
            {"Name": "notification_id", "Value": str(notification_id)},
        ],
    }
    if SES_CONFIGURATION_SET:
        kwargs["ConfigurationSetName"] = SES_CONFIGURATION_SET

    response = ses_client.send_raw_email(**kwargs)
    return response["MessageId"]


def _patch_status(notification_id, status, message):
    """Update notification status in NetBox."""
    url = f"{NETBOX_URL}/api/plugins/notices/prepared-notifications/{notification_id}/"
    payload = {
        "status": status,
        "message": message,
    }
    if status == "sent":
        payload["timestamp"] = datetime.now(timezone.utc).isoformat()

    resp = requests.patch(url, json=payload, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _fetch_ready_notifications():
    """Fetch all notifications in 'ready' status from NetBox."""
    url = f"{NETBOX_URL}/api/plugins/notices/prepared-notifications/"
    params = {"status": "ready", "limit": 100}
    notifications = []

    while url:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        notifications.extend(data.get("results", []))
        url = data.get("next")
        params = None  # next URL includes params

    return notifications


def _fetch_notification(notification_id):
    """Fetch a single notification by ID from NetBox."""
    url = f"{NETBOX_URL}/api/plugins/notices/prepared-notifications/{notification_id}/"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _send_notification(notification):
    """Send a single notification via SES and update its status.

    On success: transitions ready → sent.
    On failure: logs the error and leaves the notification in "ready" status
    so that the next poll (or a manual retry) can re-attempt delivery.
    The state machine does not allow ready → failed directly.
    """
    nid = notification["id"]
    subject = notification.get("subject", "(no subject)")
    logger.info("Processing notification %d: %s", nid, subject)

    try:
        mime_msg, to_addrs = _build_mime(notification)
        message_id = _send_via_ses(mime_msg, to_addrs, nid)
        logger.info("Sent notification %d via SES, MessageId=%s", nid, message_id)
        _patch_status(nid, "sent", f"Sent via SES (MessageId: {message_id})")
        return True
    except Exception:
        logger.exception("Failed to send notification %d — will retry on next poll", nid)
        return False


# ── Webhook helpers ──────────────────────────────────────────


def _verify_signature(body_bytes, signature):
    """Verify the X-Hook-Signature header from NetBox (HMAC-SHA512)."""
    if not WEBHOOK_SECRET:
        logger.warning("WEBHOOK_SECRET not configured, rejecting webhook")
        return False
    expected = hmac.new(
        WEBHOOK_SECRET.encode("utf-8"),
        body_bytes,
        hashlib.sha512,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _is_api_gateway_event(event):
    """Detect if the event is from API Gateway (HTTP API v2 payload format)."""
    return "requestContext" in event and "http" in event.get("requestContext", {})


def _handle_webhook(event):
    """Handle a NetBox Event Rule webhook POST."""
    # Extract signature
    headers_lower = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    signature = headers_lower.get("x-hook-signature", "")

    # Get body
    body = event.get("body", "")
    is_base64 = event.get("isBase64Encoded", False)
    if is_base64:
        import base64

        body_bytes = base64.b64decode(body)
    else:
        body_bytes = body.encode("utf-8") if isinstance(body, str) else body

    # Verify signature
    if not _verify_signature(body_bytes, signature):
        logger.warning("Webhook signature verification failed")
        return {
            "statusCode": 403,
            "body": json.dumps({"error": "Invalid signature"}),
        }

    # Parse payload
    try:
        payload = json.loads(body_bytes)
    except (json.JSONDecodeError, TypeError):
        logger.exception("Failed to parse webhook body")
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Invalid JSON"}),
        }

    # Extract notification ID from webhook data
    data = payload.get("data", {})
    notification_id = data.get("id")
    status = data.get("status", {})
    # status can be a dict {"value": "ready", "label": "Ready"} or a string
    status_value = status.get("value") if isinstance(status, dict) else status

    if not notification_id:
        logger.warning("No notification ID in webhook payload")
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "No notification ID in payload"}),
        }

    if status_value != "ready":
        logger.info("Notification %d status is '%s', not 'ready' — skipping", notification_id, status_value)
        return {
            "statusCode": 200,
            "body": json.dumps({"skipped": True, "reason": f"status is {status_value}"}),
        }

    logger.info("Webhook received for notification %d", notification_id)

    # Fetch the full notification from NetBox (webhook data may not include
    # all fields like recipients, body_html, ical_content, etc.)
    notification = _fetch_notification(notification_id)

    # Double-check it's still ready (race condition guard)
    if notification.get("status", {}).get("value", notification.get("status")) != "ready":
        logger.info("Notification %d is no longer ready, skipping", notification_id)
        return {
            "statusCode": 200,
            "body": json.dumps({"skipped": True, "reason": "no longer ready"}),
        }

    success = _send_notification(notification)
    return {
        "statusCode": 200,
        "body": json.dumps({"sent": 1 if success else 0, "failed": 0 if success else 1}),
    }


# ── Main entry point ────────────────────────────────────────


def lambda_handler(event, context):
    """Main entry point — handles both scheduled polls and webhook triggers."""
    # Webhook mode: API Gateway HTTP API v2 event
    if _is_api_gateway_event(event):
        logger.info("Webhook trigger detected")
        return _handle_webhook(event)

    # Schedule mode: EventBridge scheduled event (or manual invoke)
    logger.info("Polling NetBox for ready notifications")

    notifications = _fetch_ready_notifications()
    logger.info("Found %d ready notification(s)", len(notifications))

    sent_count = 0
    failed_count = 0

    for notification in notifications:
        if _send_notification(notification):
            sent_count += 1
        else:
            failed_count += 1

    logger.info("Complete: %d sent, %d failed", sent_count, failed_count)
    return {"sent": sent_count, "failed": failed_count}
