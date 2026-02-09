"""
Inbound Lambda — Parse incoming provider maintenance emails and create events in NetBox.

Triggered by SES receipt rule: SES stores the raw email in S3, then invokes
this Lambda. The handler fetches the email from S3, parses it with the
circuit-maintenance-parser library, and creates/updates Maintenance events
in NetBox via the REST API.

This is a modernized version of the original parsers/aws-sns-lambda/ with:
  - Environment variables instead of hardcoded config
  - requests library instead of pynetbox (consistent with other Lambdas)
  - Updated API paths for current plugin model names
  - Configurable provider map via PROVIDER_MAP env var (JSON)
  - Structured logging
  - Proper error handling
"""

import email as email_lib
import json
import logging
import os
from datetime import datetime, timezone
from email import policy

import boto3
import requests
from circuit_maintenance_parser import NotificationData, init_provider

logger = logging.getLogger()
logger.setLevel(logging.INFO)

NETBOX_URL = os.environ["NETBOX_URL"].rstrip("/")
NETBOX_API_TOKEN = os.environ["NETBOX_API_TOKEN"]
S3_BUCKET_NAME = os.environ["S3_BUCKET_NAME"]

HEADERS = {
    "Authorization": f"Token {NETBOX_API_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# Default provider domain → parser name mapping
DEFAULT_PROVIDER_MAP = {
    "zayo.com": "zayo",
    "colt.net": "colt",
    "verizonbusiness.com": "verizon",
    "cogentco.com": "cogent",
    "aquacomms.com": "aquacomms",
    "arelion.com": "arelion",
    "amazon.com": "aws",
    "bso.co": "bso",
    "equinix.com": "equinix",
    "lumen.com": "lumen",
    "momentumtelecom.com": "momentum",
    "superonline.net": "seaborn",
    "tisparkle.com": "sparkle",
    "telstra.com": "telstra",
}


def _get_provider_map():
    """Load provider map from env var or use defaults."""
    env_map = os.environ.get("PROVIDER_MAP", "")
    if env_map:
        try:
            return json.loads(env_map)
        except json.JSONDecodeError:
            logger.warning("Invalid PROVIDER_MAP JSON, using defaults")
    return DEFAULT_PROVIDER_MAP


def _identify_provider(from_email, provider_map):
    """Determine the circuit-maintenance-parser provider from the email address."""
    from_email = from_email.lower()
    for domain, provider_name in provider_map.items():
        if domain.lower() in from_email:
            return provider_name
    return None


def _parse_email(mail, provider_name):
    """Parse the inbound email using circuit-maintenance-parser."""
    logger.info("Parsing email with provider: %s", provider_name)

    generic_provider = init_provider(provider_name)
    data_to_process = NotificationData.init_from_emailmessage(mail)
    maintenances = generic_provider.get_maintenances(data_to_process)

    if maintenances:
        return maintenances[0].to_json()

    logger.warning("No maintenances extracted from email")
    return None


def _format_timestamp(unix_ts):
    """Convert a Unix timestamp string to ISO 8601 format."""
    return datetime.fromtimestamp(int(unix_ts), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _get_content_type_id(app_label, model):
    """Look up a Django ContentType PK via the NetBox API."""
    url = f"{NETBOX_URL}/api/extras/content-types/"
    resp = requests.get(
        url,
        params={"app_label": app_label, "model": model},
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])
    if results:
        return results[0]["id"]
    raise ValueError(f"ContentType not found: {app_label}.{model}")


def _get_or_create_maintenance(maintenance):
    """Create or update a Maintenance event in NetBox."""
    name = maintenance["maintenance_id"]

    # Check if maintenance exists
    url = f"{NETBOX_URL}/api/plugins/notices/maintenance/"
    resp = requests.get(url, params={"name": name}, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    results = resp.json().get("results", [])

    start_time = _format_timestamp(maintenance["start"])
    end_time = _format_timestamp(maintenance["end"])

    if results:
        # Update existing maintenance
        existing = results[0]
        logger.info("Updating existing maintenance: %s (id=%d)", name, existing["id"])
        patch_url = f"{NETBOX_URL}/api/plugins/notices/maintenance/{existing['id']}/"
        resp = requests.patch(
            patch_url,
            json={"status": maintenance["status"], "start": start_time, "end": end_time},
            headers=HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    # Find provider in NetBox
    provider_url = f"{NETBOX_URL}/api/circuits/providers/"
    resp = requests.get(
        provider_url,
        params={"name__ic": maintenance["provider"]},
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    providers = resp.json().get("results", [])

    if not providers:
        logger.error("Provider not found in NetBox: %s", maintenance["provider"])
        return None

    provider_id = providers[0]["id"]
    logger.info("Creating new maintenance: %s", name)

    resp = requests.post(
        url,
        json={
            "name": name,
            "summary": maintenance.get("summary", ""),
            "status": maintenance["status"],
            "provider": provider_id,
            "start": start_time,
            "end": end_time,
        },
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _process_impacts(maintenance_data, nb_maintenance):
    """Create or update impact records for the maintenance event."""
    maintenance_id = nb_maintenance["id"]

    # Look up ContentType PKs for the GenericForeignKey fields
    maintenance_ct_id = _get_content_type_id("notices", "maintenance")
    circuit_ct_id = _get_content_type_id("circuits", "circuit")

    for circuit_data in maintenance_data.get("circuits", []):
        circuit_id_str = circuit_data["circuit_id"]

        # Find circuit in NetBox
        resp = requests.get(
            f"{NETBOX_URL}/api/circuits/circuits/",
            params={"cid__ic": circuit_id_str},
            headers=HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
        circuits = resp.json().get("results", [])

        if not circuits:
            logger.warning("Circuit not found in NetBox: %s", circuit_id_str)
            continue

        nb_circuit_id = circuits[0]["id"]
        logger.info("Processing impact for circuit %s (id=%d)", circuit_id_str, nb_circuit_id)

        # Check if impact already exists (filter by GenericFK fields)
        impact_url = f"{NETBOX_URL}/api/plugins/notices/impact/"
        resp = requests.get(
            impact_url,
            params={
                "event_content_type_id": maintenance_ct_id,
                "event_object_id": maintenance_id,
                "target_content_type_id": circuit_ct_id,
                "target_object_id": nb_circuit_id,
            },
            headers=HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
        impacts = resp.json().get("results", [])

        if impacts:
            existing_impact = impacts[0]
            if existing_impact.get("impact") != circuit_data["impact"]:
                logger.info("Updating impact for circuit %s to %s", circuit_id_str, circuit_data["impact"])
                requests.patch(
                    f"{impact_url}{existing_impact['id']}/",
                    json={"impact": circuit_data["impact"]},
                    headers=HEADERS,
                    timeout=30,
                ).raise_for_status()
            else:
                logger.info("Impact unchanged for circuit %s: %s", circuit_id_str, circuit_data["impact"])
        else:
            logger.info("Creating impact for circuit %s: %s", circuit_id_str, circuit_data["impact"])
            requests.post(
                impact_url,
                json={
                    "event_content_type": maintenance_ct_id,
                    "event_object_id": maintenance_id,
                    "target_content_type": circuit_ct_id,
                    "target_object_id": nb_circuit_id,
                    "impact": circuit_data["impact"],
                },
                headers=HEADERS,
                timeout=30,
            ).raise_for_status()


def _store_notification(maintenance_data, nb_maintenance, mail):
    """Store the raw email notification in NetBox."""
    logger.info("Storing email notification")

    # Look up ContentType PK for the GenericForeignKey
    maintenance_ct_id = _get_content_type_id("notices", "maintenance")

    # Extract email body
    body = mail.get_body()
    body_text = str(body) if body else ""

    # Parse the from address
    from_addr = email_lib.utils.parseaddr(mail["from"])[1]

    received_time = _format_timestamp(maintenance_data["stamp"])

    url = f"{NETBOX_URL}/api/plugins/notices/eventnotification/"
    resp = requests.post(
        url,
        json={
            "event_content_type": maintenance_ct_id,
            "event_object_id": nb_maintenance["id"],
            "email_body": body_text,
            "subject": mail.get("subject", ""),
            "email_from": from_addr,
            "email_received": received_time,
        },
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()


def lambda_handler(event, context):
    """Main entry point — triggered by SES receipt rule."""
    ses_record = event["Records"][0]["ses"]
    message_id = ses_record["mail"]["messageId"]
    logger.info("Processing inbound email: %s", message_id)

    s3_client = boto3.client("s3")
    provider_map = _get_provider_map()

    # Fetch email from S3
    try:
        s3_obj = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=message_id)
        raw_email = s3_obj["Body"].read().decode("utf-8")
    except Exception:
        logger.exception("Failed to fetch email from S3: %s/%s", S3_BUCKET_NAME, message_id)
        return {"status": "error", "reason": "s3_fetch_failed"}

    # Parse the email
    try:
        mail = email_lib.message_from_string(raw_email, policy=policy.default)
    except Exception:
        logger.exception("Failed to parse email content")
        return {"status": "error", "reason": "email_parse_failed"}

    from_addr = mail.get("from", "")
    provider_name = _identify_provider(from_addr, provider_map)

    if not provider_name:
        logger.warning("No matching provider for sender: %s", from_addr)
        return {"status": "skipped", "reason": "unknown_provider"}

    # Parse maintenance data from email
    maintenance_json = _parse_email(mail, provider_name)
    if not maintenance_json:
        return {"status": "skipped", "reason": "no_maintenance_data"}

    maintenance_data = json.loads(maintenance_json)

    # Create/update maintenance event in NetBox
    nb_maintenance = _get_or_create_maintenance(maintenance_data)
    if not nb_maintenance:
        return {"status": "error", "reason": "provider_not_found"}

    # Process circuit impacts
    _process_impacts(maintenance_data, nb_maintenance)

    # Store the notification
    _store_notification(maintenance_data, nb_maintenance, mail)

    logger.info("Maintenance parsing complete: %s", maintenance_data.get("maintenance_id", ""))
    return {"status": "ok", "maintenance_id": maintenance_data.get("maintenance_id", "")}
