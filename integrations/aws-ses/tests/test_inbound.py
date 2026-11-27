"""
Tests for the inbound Lambda.

A real BCOP iCalendar notification goes through the real circuit-maintenance-parser;
only the NetBox REST API is replaced, by an in-memory fake that serves the endpoints
and filters the handler uses, the way NetBox 4.x does.
"""

from datetime import UTC, datetime
from email.message import EmailMessage
from itertools import count

import handler
import pytest
import requests

RECEIVED = datetime(2026, 1, 15, 12, 0, 1, tzinfo=UTC)

OBJECT_TYPES = {("notices", "maintenance"): 71, ("circuits", "circuit"): 12}

# What the plugin's serializers accept (notices/choices.py, notices/models/events.py)
MAINTENANCE_STATUSES = {"TENTATIVE", "CONFIRMED", "CANCELLED", "IN-PROCESS", "COMPLETED", "RE-SCHEDULED", "UNKNOWN"}
IMPACTS = {"NO-IMPACT", "REDUCED-REDUNDANCY", "DEGRADED", "OUTAGE"}
REQUIRED_TEXT = {
    "plugins/notices/maintenance/": {"name": 100, "summary": 200},
    "plugins/notices/eventnotification/": {"subject": 100, "email_body": None},
}


def _ics(status="CONFIRMED", impact="OUTAGE", maintenance_id="WO-31415", circuit="CID-100"):
    status_line = [f"X-MAINTNOTE-STATUS:{status}"] if status else []  # the BCOP allows omitting it
    return "\r\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Maint Note//https://github.com/maint-notification//",
            "BEGIN:VEVENT",
            "SUMMARY:Fibre splice on the north span",
            "DTSTART;VALUE=DATE-TIME:20260201T060000Z",
            "DTEND;VALUE=DATE-TIME:20260201T100000Z",
            "DTSTAMP;VALUE=DATE-TIME:20260115T115900Z",
            "UID:42",
            "SEQUENCE:1",
            "X-MAINTNOTE-PROVIDER:examplecarrier",
            "X-MAINTNOTE-ACCOUNT:12345",
            f"X-MAINTNOTE-MAINTENANCE-ID:{maintenance_id}",
            f"X-MAINTNOTE-OBJECT-ID;X-MAINTNOTE-OBJECT-IMPACT={impact}:{circuit}",
            f"X-MAINTNOTE-IMPACT:{impact}",
            *status_line,
            'ORGANIZER;CN="Example NOC":mailto:noc@carrier.example.net',
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ]
    )


def _email(
    sender="NOC <noc@carrier.example.net>",
    subject="Maintenance WO-31415",
    text="Please see the attached maintenance notification.",
    **ics_kwargs,
):
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = "notices@example.com"
    msg["Subject"] = subject
    msg["Date"] = "Thu, 15 Jan 2026 11:59:00 +0000"
    if text is None:  # a bare calendar invite
        msg.set_content(_ics(**ics_kwargs), subtype="calendar")
        return msg.as_bytes()
    msg.set_content(text)
    msg.add_attachment(_ics(**ics_kwargs).encode(), maintype="text", subtype="calendar", filename="maint.ics")
    return msg.as_bytes()


class FakeNetBox:
    """
    In-memory stand-in for the NetBox REST endpoints the handler calls.

    Writes are validated the way the plugin's serializers validate them, so a payload
    real NetBox would answer with 400 fails here too.
    """

    def __init__(self):
        self._ids = count(1)
        self.providers = [{"id": 5, "name": "Example Carrier", "slug": "examplecarrier"}]
        self.circuits = [
            {"id": 100, "cid": "CID-100", "provider": 5},
            {"id": 101, "cid": "CID-100", "provider": 6},  # same CID, another provider
        ]
        self.maintenances = []
        self.impacts = []
        self.notifications = []
        self.calls = []

    def __call__(self, method, path, params=None, json=None):
        self.calls.append((method, path))
        if method == "GET":
            return {"results": self._list(path, params or {})}
        if method == "POST":
            return self._create(path, json)
        if method == "PATCH":
            return self._update(path, json)
        raise AssertionError(f"unexpected {method} {path}")

    def _list(self, path, p):
        if path == "core/object-types/":
            pk = OBJECT_TYPES.get((p["app_label"], p["model"]))
            return [{"id": pk}] if pk else []
        if path == "circuits/providers/":
            if "slug" in p:
                return [x for x in self.providers if x["slug"] == p["slug"]]
            return [x for x in self.providers if p["name__ic"].lower() in x["name"].lower()]
        if path == "circuits/circuits/":
            return [
                c
                for c in self.circuits
                if c["cid"].lower() == p["cid__ie"].lower() and c["provider"] == p["provider_id"]
            ]
        if path == "plugins/notices/maintenance/":
            return [m for m in self.maintenances if m["name"] == p["name"] and m["provider"] == p["provider_id"]]
        if path == "plugins/notices/impact/":
            assert p["event_content_type"] == "notices.maintenance"
            assert p["target_content_type"] == "circuits.circuit"
            return [
                i
                for i in self.impacts
                if i["event_object_id"] == p["event_object_id"] and i["target_object_id"] == p["target_object_id"]
            ]
        if path == "plugins/notices/eventnotification/":
            assert p["event_content_type"] == "notices.maintenance"
            return [
                n
                for n in self.notifications
                if (n["event_object_id"], n["subject"], n["email_received"])
                == (p["event_object_id"], p["subject"], p["email_received"])
            ]
        raise AssertionError(f"unexpected GET {path}")

    @staticmethod
    def _validate(path, body, partial=False):
        for field, max_length in REQUIRED_TEXT.get(path, {}).items():
            if field in body or not partial:
                value = (body.get(field) or "").strip()
                if not value or (max_length and len(value) > max_length):
                    raise requests.HTTPError(f"400: {field}={body.get(field)!r}")
        if "status" in body and body["status"] not in MAINTENANCE_STATUSES:
            raise requests.HTTPError(f"400: status={body['status']!r}")
        if "impact" in body and body["impact"] not in IMPACTS:
            raise requests.HTTPError(f"400: impact={body['impact']!r}")

    def _create(self, path, body):
        self._validate(path, body)
        obj = {"id": next(self._ids), **body}
        if path == "plugins/notices/maintenance/":
            self.maintenances.append(obj)
        elif path == "plugins/notices/impact/":
            assert body["event_content_type"] == 71 and body["target_content_type"] == 12
            maintenance = next(m for m in self.maintenances if m["id"] == body["event_object_id"])
            if maintenance["status"] in ("COMPLETED", "CANCELLED"):
                raise requests.HTTPError("400: You cannot alter an impact once the event has completed.")
            self.impacts.append(obj)
        elif path == "plugins/notices/eventnotification/":
            self.notifications.append(obj)
        else:
            raise AssertionError(f"unexpected POST {path}")
        return obj

    def _update(self, path, body):
        kind, pk = path.removeprefix("plugins/notices/").strip("/").split("/")
        self._validate(f"plugins/notices/{kind}/", body, partial=True)
        table = {"maintenance": self.maintenances, "impact": self.impacts}[kind]
        obj = next(o for o in table if o["id"] == int(pk))
        obj.update(body)
        return obj


@pytest.fixture
def netbox(monkeypatch):
    fake = FakeNetBox()
    monkeypatch.setattr(handler, "_api", fake)
    monkeypatch.setattr(handler, "_object_type_ids", {})
    monkeypatch.setenv("PROVIDER_MAP", '{"carrier.example.net": "genericprovider"}')
    return fake


def test_new_notification_creates_maintenance_impact_and_notification(netbox):
    result = handler.process_email(_email(), RECEIVED)

    assert result == {"status": "ok", "maintenance_ids": ["WO-31415"]}
    [maintenance] = netbox.maintenances
    assert maintenance["provider"] == 5
    assert maintenance["status"] == "CONFIRMED"
    assert maintenance["start"] == "2026-02-01T06:00:00Z"
    assert maintenance["end"] == "2026-02-01T10:00:00Z"
    assert maintenance["summary"] == "Fibre splice on the north span"

    [impact] = netbox.impacts
    # The circuit is the one with this CID under the maintenance's provider, not the other provider's
    assert impact["target_object_id"] == 100
    assert impact["event_object_id"] == maintenance["id"]
    assert impact["impact"] == "OUTAGE"

    [notification] = netbox.notifications
    assert notification["event_object_id"] == maintenance["id"]
    assert notification["email_from"] == "noc@carrier.example.net"
    assert notification["email_received"] == "2026-01-15T12:00:01Z"
    assert "attached maintenance notification" in notification["email_body"]


def test_follow_up_updates_the_same_maintenance(netbox):
    handler.process_email(_email(), RECEIVED)
    later = RECEIVED.replace(hour=13)
    handler.process_email(_email(subject="Update: WO-31415", impact="DEGRADED"), later)

    assert len(netbox.maintenances) == 1
    [impact] = netbox.impacts
    assert impact["impact"] == "DEGRADED"
    assert len(netbox.notifications) == 2


def test_redelivery_does_not_duplicate_anything(netbox):
    handler.process_email(_email(), RECEIVED)
    handler.process_email(_email(), RECEIVED)

    assert len(netbox.maintenances) == 1
    assert len(netbox.impacts) == 1
    assert len(netbox.notifications) == 1


def test_same_maintenance_id_from_another_provider_is_a_different_event(netbox):
    netbox.maintenances.append({"id": 900, "name": "WO-31415", "provider": 6, "status": "CONFIRMED"})

    handler.process_email(_email(), RECEIVED)

    assert [m["provider"] for m in netbox.maintenances] == [6, 5]
    assert netbox.maintenances[0]["status"] == "CONFIRMED"


def test_cancellation_updates_status_without_touching_impacts(netbox):
    handler.process_email(_email(), RECEIVED)
    result = handler.process_email(_email(subject="Cancelled: WO-31415", status="CANCELLED"), RECEIVED.replace(hour=14))

    assert result["status"] == "ok"
    assert netbox.maintenances[0]["status"] == "CANCELLED"
    impact_writes = [c for c in netbox.calls if c[0] != "GET" and c[1].startswith("plugins/notices/impact/")]
    assert len(impact_writes) == 1  # the create from the first notice, nothing after the cancellation
    assert len(netbox.notifications) == 2


def test_new_cancelled_maintenance_is_recorded_without_impacts(netbox):
    result = handler.process_email(_email(status="CANCELLED"), RECEIVED)

    assert result["status"] == "ok"
    assert netbox.maintenances[0]["status"] == "CANCELLED"
    assert netbox.impacts == []
    assert len(netbox.notifications) == 1


def test_notice_without_a_status_keeps_the_existing_one(netbox):
    handler.process_email(_email(), RECEIVED)
    handler.process_email(_email(subject="Reminder: WO-31415", status=None), RECEIVED.replace(hour=13))

    assert netbox.maintenances[0]["status"] == "CONFIRMED"
    assert len(netbox.notifications) == 2


def test_first_notice_without_a_status_creates_an_unknown_maintenance(netbox):
    result = handler.process_email(_email(status=None), RECEIVED)

    assert result["status"] == "ok"
    assert netbox.maintenances[0]["status"] == "UNKNOWN"


def test_calendar_only_email_stores_the_invite_as_the_body(netbox):
    result = handler.process_email(_email(text=None), RECEIVED)

    assert result["status"] == "ok"
    assert "X-MAINTNOTE-MAINTENANCE-ID:WO-31415" in netbox.notifications[0]["email_body"]


def test_blank_subject_is_stored_as_a_placeholder(netbox):
    # A missing Subject header is not covered: circuit-maintenance-parser cannot read such an email
    handler.process_email(_email(subject="  "), RECEIVED)

    assert netbox.notifications[0]["subject"] == "(no subject)"


def test_non_utf8_email_is_parsed(netbox):
    latin1 = _email(text="Travaux planifiés.").replace(
        b"Content-Transfer-Encoding: 7bit", b"Content-Transfer-Encoding: 8bit"
    )
    latin1 = latin1.replace("Travaux planifiés.".encode(), "Travaux planifiés.".encode("latin-1"), 1)
    latin1 = latin1.replace(b'charset="utf-8"', b'charset="iso-8859-1"', 1)

    result = handler.process_email(latin1, RECEIVED)

    assert result["status"] == "ok"
    assert netbox.notifications[0]["email_body"] == "Travaux planifiés."


def test_long_maintenance_id_is_truncated_consistently(netbox):
    long_id = "WO-" + "9" * 120
    handler.process_email(_email(maintenance_id=long_id), RECEIVED)
    handler.process_email(_email(maintenance_id=long_id, subject="Update"), RECEIVED.replace(hour=13))

    [maintenance] = netbox.maintenances
    assert maintenance["name"] == long_id[:100]


def test_unknown_circuit_is_skipped(netbox):
    result = handler.process_email(_email(circuit="NOT-IN-NETBOX"), RECEIVED)

    assert result["status"] == "ok"
    assert netbox.impacts == []
    assert len(netbox.notifications) == 1


def test_long_subject_is_truncated_to_the_model_limit(netbox):
    handler.process_email(_email(subject="x" * 150), RECEIVED)

    assert netbox.notifications[0]["subject"] == "x" * 100


def test_unknown_sender_is_skipped(netbox):
    result = handler.process_email(_email(sender="someone@unrelated.example.org"), RECEIVED)

    assert result == {"status": "skipped", "reason": "unknown_provider"}
    assert netbox.calls == []


def test_provider_missing_from_netbox_is_an_error(netbox):
    netbox.providers = []

    result = handler.process_email(_email(), RECEIVED)

    assert result == {"status": "error", "reason": "provider_not_found"}
    assert netbox.maintenances == []


def test_ambiguous_provider_name_is_refused(netbox):
    netbox.providers = [
        {"id": 5, "name": "Examplecarrier East", "slug": "east"},
        {"id": 6, "name": "Examplecarrier West", "slug": "west"},
    ]

    result = handler.process_email(_email(), RECEIVED)

    assert result == {"status": "error", "reason": "provider_not_found"}


def test_unparseable_email_is_skipped(netbox):
    msg = EmailMessage()
    msg["From"] = "noc@carrier.example.net"
    msg["Subject"] = "Hello"
    msg["Date"] = "Thu, 15 Jan 2026 11:59:00 +0000"
    msg.set_content("No maintenance in here.")

    result = handler.process_email(msg.as_bytes(), RECEIVED)

    assert result == {"status": "skipped", "reason": "no_maintenance_data"}


@pytest.mark.parametrize(
    ("sender", "expected"),
    [
        ("NOC <noc@zayo.com>", "zayo"),
        ("noc@mail.zayo.com", "zayo"),
        ("NOC@ZAYO.COM", "zayo"),
        ("noc@bso.com", None),  # "bso.co" must not match a different domain it prefixes
        ("noc@notzayo.com", None),
        ("noc@zayo.com.attacker.example", None),
    ],
)
def test_identify_provider_matches_domain_or_subdomain(sender, expected):
    assert handler._identify_provider(sender, handler.DEFAULT_PROVIDER_MAP) == expected


def test_identify_provider_prefers_the_most_specific_domain():
    provider_map = {"example.net": "genericprovider", "carrier.example.net": "zayo"}

    assert handler._identify_provider("noc@mail.carrier.example.net", provider_map) == "zayo"
    assert handler._identify_provider("noc@other.example.net", provider_map) == "genericprovider"


def test_lambda_handler_reads_the_email_from_s3(monkeypatch, netbox):
    class Body:
        def read(self):
            return _email()

    class S3:
        def get_object(self, Bucket, Key):  # noqa: N803 - boto3's parameter names
            assert (Bucket, Key) == ("inbound-test", "abc123")
            return {"Body": Body()}

    monkeypatch.setattr(handler.boto3, "client", lambda service: S3())
    event = {"Records": [{"ses": {"mail": {"messageId": "abc123", "timestamp": "2026-01-15T12:00:01.000Z"}}}]}

    assert handler.lambda_handler(event, None)["status"] == "ok"
    assert netbox.notifications[0]["email_received"] == "2026-01-15T12:00:01Z"


def test_lambda_handler_raises_on_s3_errors_so_lambda_retries(monkeypatch, netbox):
    class S3:
        def get_object(self, Bucket, Key):  # noqa: N803 - boto3's parameter names
            raise ConnectionError("S3 unavailable")

    monkeypatch.setattr(handler.boto3, "client", lambda service: S3())
    event = {"Records": [{"ses": {"mail": {"messageId": "abc123", "timestamp": "2026-01-15T12:00:01.000Z"}}}]}

    with pytest.raises(ConnectionError):
        handler.lambda_handler(event, None)
