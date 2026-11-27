"""
Inbound Lambda — Parse incoming provider maintenance emails and create events in NetBox.

Triggered by SES receipt rule: SES stores the raw email in S3, then invokes
this Lambda. The handler fetches the email from S3, parses it with the
circuit-maintenance-parser library, and creates/updates Maintenance events
in NetBox via the REST API.

For each maintenance the parser extracts:
  1. The NetBox Provider is resolved (slug first, then a unique name match).
  2. The Maintenance is found by (name, provider) and updated, or created.
  3. Each parsed circuit is matched by CID within that provider and its
     Impact is created or updated, unless the event is COMPLETED or
     CANCELLED, whose impacts the plugin refuses to change.
  4. The email is stored as an EventNotification, once: a retried invocation
     finds the notification it already stored and does not add another.

NetBox errors raise, so Lambda's asynchronous retry gets another attempt;
every step above is safe to repeat. An email that cannot be attributed to a
provider, or yields no maintenance, is logged and skipped.
"""

import email as email_lib
import json
import logging
import os
from datetime import UTC, datetime
from email import policy
from email.utils import parseaddr

import boto3
import requests
from circuit_maintenance_parser import NotificationData, init_provider
from circuit_maintenance_parser.errors import ProviderError

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

# Field lengths enforced by the plugin's models
MAX_SUMMARY = 200
MAX_SUBJECT = 100

# Maintenance statuses whose impacts the plugin no longer allows to change
TERMINAL_STATUSES = {"COMPLETED", "CANCELLED"}

MAINTENANCE_TYPE = "notices.maintenance"
CIRCUIT_TYPE = "circuits.circuit"

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

_session = requests.Session()
_session.headers.update(HEADERS)
_object_type_ids = {}


def _api(method, path, **kwargs):
    """Call the NetBox REST API and return the decoded JSON body."""
    resp = _session.request(method, f"{NETBOX_URL}/api/{path}", timeout=30, **kwargs)
    resp.raise_for_status()
    return resp.json()


def _results(path, **params):
    return _api("GET", path, params=params).get("results", [])


def _object_type_id(dotted):
    """Return the ObjectType (ContentType) PK for ``app_label.model``, cached per container."""
    if dotted not in _object_type_ids:
        app_label, model = dotted.split(".")
        results = _results("core/object-types/", app_label=app_label, model=model)
        if not results:
            raise ValueError(f"Object type not found: {dotted}")
        _object_type_ids[dotted] = results[0]["id"]
    return _object_type_ids[dotted]


def _get_provider_map():
    """Load provider map from env var or use defaults."""
    env_map = os.environ.get("PROVIDER_MAP", "")
    if env_map:
        try:
            return json.loads(env_map)
        except json.JSONDecodeError:
            logger.warning("Invalid PROVIDER_MAP JSON, using defaults")
    return DEFAULT_PROVIDER_MAP


def _identify_provider(from_header, provider_map):
    """Return the parser name for the sender's domain, or for one of its parent domains."""
    domain = parseaddr(from_header)[1].rpartition("@")[2].lower()
    for map_domain, provider_name in provider_map.items():
        map_domain = map_domain.lower()
        if domain == map_domain or domain.endswith(f".{map_domain}"):
            return provider_name
    return None


def _parse_email(raw_email, provider_name):
    """Parse the raw email with circuit-maintenance-parser; return a list of maintenance dicts."""
    logger.info("Parsing email with provider: %s", provider_name)

    parser = init_provider(provider_name)
    if parser is None:
        logger.error("Unknown circuit-maintenance-parser provider: %s", provider_name)
        return []

    data = NotificationData.init_from_email_bytes(raw_email)
    if data is None:
        logger.error("circuit-maintenance-parser could not read the email")
        return []

    try:
        maintenances = parser.get_maintenances(data)
    except ProviderError:
        logger.exception("Parser %s could not process the email", provider_name)
        return []

    return [json.loads(m.to_json()) for m in maintenances]


def _format_timestamp(unix_ts):
    """Convert a Unix timestamp to ISO 8601 (UTC)."""
    return datetime.fromtimestamp(int(unix_ts), tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _find_provider(parsed_name):
    """Resolve the parser's provider name to a NetBox Provider: exact slug, else a unique name match."""
    providers = _results("circuits/providers/", slug=parsed_name.lower())
    if not providers:
        providers = _results("circuits/providers/", name__ic=parsed_name)
    if len(providers) == 1:
        return providers[0]
    if providers:
        logger.error(
            "Provider %r matches %d NetBox providers (%s); give the intended one the slug %r",
            parsed_name,
            len(providers),
            ", ".join(p["name"] for p in providers),
            parsed_name.lower(),
        )
    else:
        logger.error("Provider not found in NetBox: %s", parsed_name)
    return None


def _upsert_maintenance(maintenance, provider_id):
    """Create the Maintenance, or update the one this provider already has under that name."""
    name = maintenance["maintenance_id"]
    fields = {
        "status": maintenance["status"],
        "start": _format_timestamp(maintenance["start"]),
        "end": _format_timestamp(maintenance["end"]),
    }

    existing = _results("plugins/notices/maintenance/", name=name, provider_id=provider_id)
    if existing:
        logger.info("Updating existing maintenance: %s (id=%d)", name, existing[0]["id"])
        return _api("PATCH", f"plugins/notices/maintenance/{existing[0]['id']}/", json=fields)

    logger.info("Creating new maintenance: %s", name)
    return _api(
        "POST",
        "plugins/notices/maintenance/",
        json={
            "name": name,
            "summary": (maintenance.get("summary") or name)[:MAX_SUMMARY],
            "provider": provider_id,
            **fields,
        },
    )


def _upsert_impacts(maintenance, nb_maintenance, provider_id):
    """Create or update an Impact for every parsed circuit found under this provider."""
    if nb_maintenance["status"] in TERMINAL_STATUSES:
        logger.info(
            "Maintenance %s is %s; leaving its impacts unchanged", nb_maintenance["name"], nb_maintenance["status"]
        )
        return

    for circuit in maintenance.get("circuits", []):
        cid = circuit["circuit_id"]
        circuits = _results("circuits/circuits/", cid__ie=cid, provider_id=provider_id)
        if not circuits:
            logger.warning("Circuit not found in NetBox: %s", cid)
            continue
        circuit_pk = circuits[0]["id"]

        impacts = _results(
            "plugins/notices/impact/",
            event_content_type=MAINTENANCE_TYPE,
            event_object_id=nb_maintenance["id"],
            target_content_type=CIRCUIT_TYPE,
            target_object_id=circuit_pk,
        )

        if not impacts:
            logger.info("Creating impact for circuit %s: %s", cid, circuit["impact"])
            _api(
                "POST",
                "plugins/notices/impact/",
                json={
                    "event_content_type": _object_type_id(MAINTENANCE_TYPE),
                    "event_object_id": nb_maintenance["id"],
                    "target_content_type": _object_type_id(CIRCUIT_TYPE),
                    "target_object_id": circuit_pk,
                    "impact": circuit["impact"],
                },
            )
        elif impacts[0].get("impact") != circuit["impact"]:
            logger.info("Updating impact for circuit %s to %s", cid, circuit["impact"])
            _api("PATCH", f"plugins/notices/impact/{impacts[0]['id']}/", json={"impact": circuit["impact"]})
        else:
            logger.info("Impact unchanged for circuit %s: %s", cid, circuit["impact"])


def _store_notification(mail, nb_maintenance, received):
    """Attach the email to the Maintenance as an EventNotification, unless it already is."""
    subject = (mail.get("subject") or "")[:MAX_SUBJECT]
    received_at = received.strftime("%Y-%m-%dT%H:%M:%SZ")

    if _results(
        "plugins/notices/eventnotification/",
        event_content_type=MAINTENANCE_TYPE,
        event_object_id=nb_maintenance["id"],
        subject=subject,
        email_received=received_at,
    ):
        logger.info("Notification already stored for maintenance %s", nb_maintenance["name"])
        return

    body = mail.get_body(preferencelist=("plain", "html"))
    _api(
        "POST",
        "plugins/notices/eventnotification/",
        json={
            "event_content_type": _object_type_id(MAINTENANCE_TYPE),
            "event_object_id": nb_maintenance["id"],
            "email_body": body.get_content() if body else "",
            "subject": subject,
            "email_from": parseaddr(mail.get("from", ""))[1],
            "email_received": received_at,
        },
    )


def process_email(raw_email, received):
    """Parse one raw email and record what it describes in NetBox. Returns a result dict."""
    mail = email_lib.message_from_bytes(raw_email, policy=policy.default)

    from_header = mail.get("from", "")
    provider_name = _identify_provider(from_header, _get_provider_map())
    if not provider_name:
        logger.warning("No matching provider for sender: %s", from_header)
        return {"status": "skipped", "reason": "unknown_provider"}

    maintenances = _parse_email(raw_email, provider_name)
    if not maintenances:
        logger.warning("No maintenances extracted from email")
        return {"status": "skipped", "reason": "no_maintenance_data"}

    recorded = []
    for maintenance in maintenances:
        provider = _find_provider(maintenance["provider"])
        if provider is None:
            continue

        nb_maintenance = _upsert_maintenance(maintenance, provider["id"])
        _upsert_impacts(maintenance, nb_maintenance, provider["id"])
        _store_notification(mail, nb_maintenance, received)
        recorded.append(maintenance["maintenance_id"])

    if not recorded:
        return {"status": "error", "reason": "provider_not_found"}

    logger.info("Maintenance parsing complete: %s", ", ".join(recorded))
    return {"status": "ok", "maintenance_ids": recorded}


def lambda_handler(event, context):
    """Main entry point — triggered by SES receipt rule."""
    mail_meta = event["Records"][0]["ses"]["mail"]
    message_id = mail_meta["messageId"]
    logger.info("Processing inbound email: %s", message_id)

    try:
        s3_obj = boto3.client("s3").get_object(Bucket=S3_BUCKET_NAME, Key=message_id)
        raw_email = s3_obj["Body"].read()
    except Exception:
        logger.exception("Failed to fetch email from S3: %s/%s", S3_BUCKET_NAME, message_id)
        return {"status": "error", "reason": "s3_fetch_failed"}

    received = datetime.fromisoformat(mail_meta["timestamp"].replace("Z", "+00:00"))
    return process_email(raw_email, received)
