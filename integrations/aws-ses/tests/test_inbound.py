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


def _ics(status="CONFIRMED", impact="OUTAGE", maintenance_id="WO-31415", circuit="CID-100"):
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
            f"X-MAINTNOTE-STATUS:{status}",
            'ORGANIZER;CN="Example NOC":mailto:noc@carrier.example.net',
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ]
    )


def _email(sender="NOC <noc@carrier.example.net>", subject="Maintenance WO-31415", **ics_kwargs):
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = "notices@example.com"
    msg["Subject"] = subject
    msg["Date"] = "Thu, 15 Jan 2026 11:59:00 +0000"
    msg.set_content("Please see the attached maintenance notification.")
    msg.add_attachment(_ics(**ics_kwargs).encode(), maintype="text", subtype="calendar", filename="maint.ics")
    return msg.as_bytes()


class FakeNetBox:
    """In-memory stand-in for the NetBox REST endpoints the handler calls."""

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

    def _create(self, path, body):
        obj = {"id": next(self._ids), **body}
        if path == "plugins/notices/maintenance/":
            assert len(body["summary"]) <= 200
            self.maintenances.append(obj)
        elif path == "plugins/notices/impact/":
            assert body["event_content_type"] == 71 and body["target_content_type"] == 12
            maintenance = next(m for m in self.maintenances if m["id"] == body["event_object_id"])
            if maintenance["status"] in ("COMPLETED", "CANCELLED"):
                raise requests.HTTPError("400: You cannot alter an impact once the event has completed.")
            self.impacts.append(obj)
        elif path == "plugins/notices/eventnotification/":
            assert len(body["subject"]) <= 100
            self.notifications.append(obj)
        else:
            raise AssertionError(f"unexpected POST {path}")
        return obj

    def _update(self, path, body):
        kind, pk = path.removeprefix("plugins/notices/").strip("/").split("/")
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
