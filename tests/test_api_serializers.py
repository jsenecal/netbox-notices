"""Tests for API serializer methods (get_* and validation) in events.py and messaging.py."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from rest_framework.test import APIClient

from notices.models import (
    EventNotification,
    Impact,
    Maintenance,
    NotificationTemplate,
    Outage,
)

User = get_user_model()


@pytest.fixture
def superuser():
    return User.objects.create_superuser(username="serializer-user", email="s@example.com", password="pass")


@pytest.fixture
def api_client(superuser):
    client = APIClient()
    client.force_authenticate(user=superuser)
    return client


@pytest.mark.django_db
class TestImpactSerializerGetEvent:
    """Test ImpactSerializer.get_event for maintenance and outage paths."""

    def test_impact_with_maintenance_event(self, api_client, provider, circuit):
        now = timezone.now()
        maint = Maintenance.objects.create(
            name="M1", summary="Test", provider=provider, start=now, end=now + timedelta(hours=2), status="CONFIRMED"
        )
        maint_ct = ContentType.objects.get_for_model(Maintenance)
        circuit_ct = ContentType.objects.get_for_model(circuit)
        impact = Impact.objects.create(
            event_content_type=maint_ct,
            event_object_id=maint.pk,
            target_content_type=circuit_ct,
            target_object_id=circuit.pk,
            impact="OUTAGE",
        )

        response = api_client.get(f"/api/plugins/notices/impact/{impact.pk}/")
        assert response.status_code == 200
        # get_event should return nested maintenance
        assert response.data["event"]["id"] == maint.pk
        assert response.data["event"]["name"] == "M1"

    def test_impact_with_outage_event(self, api_client, provider, circuit):
        outage = Outage.objects.create(name="O1", summary="Test", provider=provider, status="REPORTED")
        outage_ct = ContentType.objects.get_for_model(Outage)
        circuit_ct = ContentType.objects.get_for_model(circuit)
        impact = Impact.objects.create(
            event_content_type=outage_ct,
            event_object_id=outage.pk,
            target_content_type=circuit_ct,
            target_object_id=circuit.pk,
            impact="DEGRADED",
        )

        response = api_client.get(f"/api/plugins/notices/impact/{impact.pk}/")
        assert response.status_code == 200
        assert response.data["event"]["id"] == outage.pk
        assert response.data["event"]["name"] == "O1"


@pytest.mark.django_db
class TestImpactSerializerGetTarget:
    """Test ImpactSerializer.get_target for circuit and non-circuit paths."""

    def test_target_circuit(self, api_client, provider, circuit):
        now = timezone.now()
        maint = Maintenance.objects.create(
            name="M1", summary="Test", provider=provider, start=now, end=now + timedelta(hours=2), status="CONFIRMED"
        )
        maint_ct = ContentType.objects.get_for_model(Maintenance)
        circuit_ct = ContentType.objects.get_for_model(circuit)
        impact = Impact.objects.create(
            event_content_type=maint_ct,
            event_object_id=maint.pk,
            target_content_type=circuit_ct,
            target_object_id=circuit.pk,
            impact="OUTAGE",
        )

        response = api_client.get(f"/api/plugins/notices/impact/{impact.pk}/")
        assert response.status_code == 200
        # CircuitSerializer used for circuits — has 'cid' field
        assert "cid" in response.data["target"]

    def test_target_non_circuit(self, api_client, provider, device):
        """Non-circuit targets should return basic representation."""
        now = timezone.now()
        maint = Maintenance.objects.create(
            name="M1", summary="Test", provider=provider, start=now, end=now + timedelta(hours=2), status="CONFIRMED"
        )
        maint_ct = ContentType.objects.get_for_model(Maintenance)
        device_ct = ContentType.objects.get_for_model(device)
        impact = Impact.objects.create(
            event_content_type=maint_ct,
            event_object_id=maint.pk,
            target_content_type=device_ct,
            target_object_id=device.pk,
            impact="DEGRADED",
        )

        response = api_client.get(f"/api/plugins/notices/impact/{impact.pk}/")
        assert response.status_code == 200
        # Non-circuit fallback returns basic dict with id, name, type
        target = response.data["target"]
        assert target["id"] == device.pk
        assert "type" in target


@pytest.mark.django_db
class TestNestedImpactSerializer:
    """Test NestedImpactSerializer get_event_type/get_event_object/get_target_type/get_target_object."""

    def test_nested_impact_fields(self, provider, circuit):
        from notices.api.serializers.events import NestedImpactSerializer

        now = timezone.now()
        maint = Maintenance.objects.create(
            name="M1", summary="Test", provider=provider, start=now, end=now + timedelta(hours=2), status="CONFIRMED"
        )
        maint_ct = ContentType.objects.get_for_model(Maintenance)
        circuit_ct = ContentType.objects.get_for_model(circuit)
        impact = Impact.objects.create(
            event_content_type=maint_ct,
            event_object_id=maint.pk,
            target_content_type=circuit_ct,
            target_object_id=circuit.pk,
            impact="OUTAGE",
        )

        serializer = NestedImpactSerializer()
        assert serializer.get_event_type(impact) == "notices.maintenance"
        assert serializer.get_event_object(impact) == {"id": maint.pk, "name": str(maint)}
        assert serializer.get_target_type(impact) == "circuits.circuit"
        assert serializer.get_target_object(impact) == {"id": circuit.pk, "name": str(circuit)}

    def test_nested_impact_null_event(self, provider, circuit):
        """Test get_event_type/get_event_object when event is deleted."""
        from notices.api.serializers.events import NestedImpactSerializer

        now = timezone.now()
        Maintenance.objects.create(
            name="M1", summary="Test", provider=provider, start=now, end=now + timedelta(hours=2), status="CONFIRMED"
        )
        maint_ct = ContentType.objects.get_for_model(Maintenance)
        circuit_ct = ContentType.objects.get_for_model(circuit)
        impact = Impact.objects.create(
            event_content_type=maint_ct,
            event_object_id=999999,  # non-existent
            target_content_type=circuit_ct,
            target_object_id=circuit.pk,
            impact="OUTAGE",
        )

        serializer = NestedImpactSerializer()
        # event_content_type exists but event object doesn't -> get_event_object returns None
        assert serializer.get_event_type(impact) == "notices.maintenance"
        assert serializer.get_event_object(impact) is None


@pytest.mark.django_db
class TestNestedEventNotificationSerializer:
    """Test NestedEventNotificationSerializer get_event_type/get_event_object."""

    def test_nested_notification_fields(self, provider):
        from notices.api.serializers.events import NestedEventNotificationSerializer

        now = timezone.now()
        maint = Maintenance.objects.create(
            name="M1", summary="Test", provider=provider, start=now, end=now + timedelta(hours=2), status="CONFIRMED"
        )
        maint_ct = ContentType.objects.get_for_model(Maintenance)
        notif = EventNotification.objects.create(
            event_content_type=maint_ct,
            event_object_id=maint.pk,
            email=b"raw",
            email_body="body",
            subject="Test Subject",
            email_from="noc@example.com",
            email_received=now,
        )

        serializer = NestedEventNotificationSerializer()
        assert serializer.get_event_type(notif) == "notices.maintenance"
        assert serializer.get_event_object(notif) == {"id": maint.pk, "name": str(maint)}

    def test_nested_notification_null_event(self, provider):
        from notices.api.serializers.events import NestedEventNotificationSerializer

        maint_ct = ContentType.objects.get_for_model(Maintenance)
        notif = EventNotification.objects.create(
            event_content_type=maint_ct,
            event_object_id=999999,
            email=b"raw",
            email_body="body",
            subject="Test",
            email_from="noc@example.com",
            email_received=timezone.now(),
        )

        serializer = NestedEventNotificationSerializer()
        assert serializer.get_event_type(notif) == "notices.maintenance"
        assert serializer.get_event_object(notif) is None


@pytest.mark.django_db
class TestEventNotificationSerializerGetEvent:
    """Test EventNotificationSerializer.get_event for maintenance and outage paths."""

    def test_notification_with_maintenance(self, api_client, provider):
        now = timezone.now()
        maint = Maintenance.objects.create(
            name="M1", summary="Test", provider=provider, start=now, end=now + timedelta(hours=2), status="CONFIRMED"
        )
        maint_ct = ContentType.objects.get_for_model(Maintenance)
        notif = EventNotification.objects.create(
            event_content_type=maint_ct,
            event_object_id=maint.pk,
            email=b"raw",
            email_body="body",
            subject="Test",
            email_from="noc@example.com",
            email_received=now,
        )

        response = api_client.get(f"/api/plugins/notices/eventnotification/{notif.pk}/")
        assert response.status_code == 200
        assert response.data["event"]["id"] == maint.pk

    def test_notification_with_outage(self, api_client, provider):
        outage = Outage.objects.create(name="O1", summary="Test", provider=provider, status="REPORTED")
        outage_ct = ContentType.objects.get_for_model(Outage)
        notif = EventNotification.objects.create(
            event_content_type=outage_ct,
            event_object_id=outage.pk,
            email=b"raw",
            email_body="body",
            subject="Test",
            email_from="noc@example.com",
            email_received=timezone.now(),
        )

        response = api_client.get(f"/api/plugins/notices/eventnotification/{notif.pk}/")
        assert response.status_code == 200
        assert response.data["event"]["id"] == outage.pk


@pytest.mark.django_db
class TestNotificationTemplateSerializerValidation:
    """Test NotificationTemplateSerializer.validate_headers_template."""

    def test_valid_yaml_headers(self, api_client):
        data = {
            "name": "YAML Test",
            "slug": "yaml-test",
            "event_type": "maintenance",
            "granularity": "per_event",
            "subject_template": "Subject",
            "body_template": "Body",
            "body_format": "text",
            "weight": 1000,
            "headers_template": "X-Custom: value\nX-Other: test",
        }
        response = api_client.post("/api/plugins/notices/notification-templates/", data, format="json")
        assert response.status_code == 201

    def test_invalid_yaml_headers(self, api_client):
        data = {
            "name": "Bad YAML",
            "slug": "bad-yaml",
            "event_type": "maintenance",
            "granularity": "per_event",
            "subject_template": "Subject",
            "body_template": "Body",
            "body_format": "text",
            "weight": 1000,
            "headers_template": ":::invalid: yaml: [unclosed",
        }
        response = api_client.post("/api/plugins/notices/notification-templates/", data, format="json")
        assert response.status_code == 400
        assert "headers_template" in response.data


@pytest.mark.django_db
class TestTemplateScopeSerializerGetObjectRepr:
    """Test TemplateScopeSerializer.get_object_repr."""

    def test_scope_with_object(self, api_client, provider):
        template = NotificationTemplate.objects.create(
            name="T1",
            slug="t1",
            event_type="maintenance",
            granularity="per_event",
            subject_template="S",
            body_template="B",
            body_format="text",
            weight=1000,
        )
        provider_ct = ContentType.objects.get_for_model(provider)
        # Create scope via API is not directly supported, so use model
        from notices.models import TemplateScope

        TemplateScope.objects.create(
            template=template,
            content_type=provider_ct,
            object_id=provider.pk,
            weight=1000,
        )

        response = api_client.get(f"/api/plugins/notices/notification-templates/{template.pk}/")
        assert response.status_code == 200
        scopes = response.data["scopes"]
        assert len(scopes) == 1
        assert scopes[0]["object_repr"] == str(provider)

    def test_scope_without_object(self, api_client):
        template = NotificationTemplate.objects.create(
            name="T2",
            slug="t2",
            event_type="maintenance",
            granularity="per_event",
            subject_template="S",
            body_template="B",
            body_format="text",
            weight=1000,
        )
        from notices.models import TemplateScope

        provider_ct = ContentType.objects.get(app_label="circuits", model="provider")
        TemplateScope.objects.create(
            template=template,
            content_type=provider_ct,
            object_id=None,
            weight=1000,
        )

        response = api_client.get(f"/api/plugins/notices/notification-templates/{template.pk}/")
        assert response.status_code == 200
        scopes = response.data["scopes"]
        assert len(scopes) == 1
        assert "All" in scopes[0]["object_repr"]
