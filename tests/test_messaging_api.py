"""Tests for MessageTemplate and PreparedMessage API endpoints."""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from notices.choices import PreparedMessageStatusChoices
from notices.models import MessageTemplate, PreparedMessage

User = get_user_model()


@pytest.fixture
def superuser():
    """Create superuser for API testing."""
    return User.objects.create_superuser(
        username="apiuser",
        email="api@example.com",
        password="apipass123",
    )


@pytest.fixture
def api_client(superuser):
    """Create authenticated API client."""
    client = APIClient()
    client.force_authenticate(user=superuser)
    return client


@pytest.fixture
def message_template():
    """Create a test message template."""
    return MessageTemplate.objects.create(
        name="Test Template",
        slug="test-template",
        event_type="maintenance",
        granularity="per_event",
        subject_template="Test Subject: {{ maintenance.name }}",
        body_template="Test body for {{ maintenance.name }}",
        body_format="text",
        weight=1000,
    )


@pytest.fixture
def prepared_message(message_template, contact):
    """Create a test prepared message."""
    msg = PreparedMessage.objects.create(
        template=message_template,
        status=PreparedMessageStatusChoices.DRAFT,
        subject="Test Subject",
        body_text="Test body content",
    )
    msg.contacts.add(contact)
    return msg


@pytest.mark.django_db
class TestMessageTemplateAPI:
    """Test MessageTemplate API endpoints."""

    def test_list_templates(self, api_client, message_template):
        """Test listing message templates."""
        response = api_client.get("/api/plugins/notices/message-templates/")
        assert response.status_code == 200
        assert len(response.data["results"]) >= 1

    def test_get_template(self, api_client, message_template):
        """Test retrieving a single template."""
        response = api_client.get(f"/api/plugins/notices/message-templates/{message_template.pk}/")
        assert response.status_code == 200
        assert response.data["name"] == "Test Template"
        assert response.data["slug"] == "test-template"

    def test_create_template(self, api_client):
        """Test creating a message template."""
        data = {
            "name": "New Template",
            "slug": "new-template",
            "event_type": "outage",
            "granularity": "per_tenant",
            "subject_template": "Outage: {{ outage.name }}",
            "body_template": "Outage details...",
            "body_format": "markdown",
            "weight": 500,
        }
        response = api_client.post("/api/plugins/notices/message-templates/", data, format="json")
        assert response.status_code == 201
        assert response.data["name"] == "New Template"
        assert MessageTemplate.objects.filter(slug="new-template").exists()

    def test_update_template(self, api_client, message_template):
        """Test updating a message template."""
        data = {"name": "Updated Template"}
        response = api_client.patch(
            f"/api/plugins/notices/message-templates/{message_template.pk}/",
            data,
            format="json",
        )
        assert response.status_code == 200
        message_template.refresh_from_db()
        assert message_template.name == "Updated Template"

    def test_delete_template(self, api_client, message_template):
        """Test deleting a message template."""
        pk = message_template.pk
        response = api_client.delete(f"/api/plugins/notices/message-templates/{pk}/")
        assert response.status_code == 204
        assert not MessageTemplate.objects.filter(pk=pk).exists()


@pytest.mark.django_db
class TestPreparedMessageAPI:
    """Test PreparedMessage API endpoints."""

    def test_list_messages(self, api_client, prepared_message):
        """Test listing prepared messages."""
        response = api_client.get("/api/plugins/notices/prepared-messages/")
        assert response.status_code == 200
        assert len(response.data["results"]) >= 1

    def test_filter_by_status(self, api_client, prepared_message):
        """Test filtering prepared messages by status."""
        response = api_client.get("/api/plugins/notices/prepared-messages/?status=draft")
        assert response.status_code == 200
        for msg in response.data["results"]:
            assert msg["status"] == "draft"

    def test_get_message(self, api_client, prepared_message):
        """Test retrieving a single prepared message."""
        response = api_client.get(f"/api/plugins/notices/prepared-messages/{prepared_message.pk}/")
        assert response.status_code == 200
        assert response.data["subject"] == "Test Subject"
        assert response.data["status"] == "draft"

    def test_create_message(self, api_client, message_template, contact):
        """Test creating a prepared message."""
        data = {
            "template_id": message_template.pk,
            "subject": "New Message Subject",
            "body_text": "New message body",
            "contact_ids": [contact.pk],
        }
        response = api_client.post("/api/plugins/notices/prepared-messages/", data, format="json")
        assert response.status_code == 201
        assert response.data["subject"] == "New Message Subject"
        assert response.data["status"] == "draft"

    def test_update_message_status_to_ready(self, api_client, prepared_message, superuser):
        """Test transitioning message status from draft to ready."""
        response = api_client.patch(
            f"/api/plugins/notices/prepared-messages/{prepared_message.pk}/",
            {"status": "ready", "message": "Approved for delivery"},
            format="json",
        )
        assert response.status_code == 200
        prepared_message.refresh_from_db()
        assert prepared_message.status == PreparedMessageStatusChoices.READY
        assert prepared_message.approved_by == superuser
        assert prepared_message.approved_at is not None

    def test_invalid_status_transition(self, api_client, prepared_message):
        """Test that invalid status transitions are rejected."""
        # Try to go directly from draft to sent (invalid)
        response = api_client.patch(
            f"/api/plugins/notices/prepared-messages/{prepared_message.pk}/",
            {"status": "sent"},
            format="json",
        )
        assert response.status_code == 400
        assert "status" in response.data

    def test_status_transition_with_timestamp(self, api_client, prepared_message, superuser):
        """Test status transition with custom timestamp."""
        # First transition to ready
        api_client.patch(
            f"/api/plugins/notices/prepared-messages/{prepared_message.pk}/",
            {"status": "ready"},
            format="json",
        )

        # Then transition to sent with a custom timestamp
        custom_time = timezone.now().isoformat()
        response = api_client.patch(
            f"/api/plugins/notices/prepared-messages/{prepared_message.pk}/",
            {"status": "sent", "timestamp": custom_time, "message": "Sent via batch"},
            format="json",
        )
        assert response.status_code == 200
        prepared_message.refresh_from_db()
        assert prepared_message.status == PreparedMessageStatusChoices.SENT
        assert prepared_message.sent_at is not None

    def test_future_timestamp_rejected(self, api_client, prepared_message):
        """Test that future timestamps are rejected."""
        # First transition to ready
        api_client.patch(
            f"/api/plugins/notices/prepared-messages/{prepared_message.pk}/",
            {"status": "ready"},
            format="json",
        )

        # Try to use a future timestamp
        from datetime import timedelta

        future_time = (timezone.now() + timedelta(hours=1)).isoformat()
        response = api_client.patch(
            f"/api/plugins/notices/prepared-messages/{prepared_message.pk}/",
            {"status": "sent", "timestamp": future_time},
            format="json",
        )
        assert response.status_code == 400

    def test_journal_entry_created(self, api_client, prepared_message):
        """Test that journal entry is created when message is provided."""
        from extras.models import JournalEntry

        initial_count = JournalEntry.objects.filter(
            assigned_object_id=prepared_message.pk,
        ).count()

        api_client.patch(
            f"/api/plugins/notices/prepared-messages/{prepared_message.pk}/",
            {"status": "ready", "message": "Test journal entry"},
            format="json",
        )

        new_count = JournalEntry.objects.filter(
            assigned_object_id=prepared_message.pk,
        ).count()
        assert new_count == initial_count + 1

    def test_delete_message(self, api_client, prepared_message):
        """Test deleting a prepared message."""
        pk = prepared_message.pk
        response = api_client.delete(f"/api/plugins/notices/prepared-messages/{pk}/")
        assert response.status_code == 204
        assert not PreparedMessage.objects.filter(pk=pk).exists()

    def test_recipients_readonly(self, api_client, prepared_message):
        """Test that recipients field is read-only."""
        response = api_client.patch(
            f"/api/plugins/notices/prepared-messages/{prepared_message.pk}/",
            {"recipients": [{"email": "hacker@evil.com", "name": "Hacker"}]},
            format="json",
        )
        # Should succeed but recipients should not be modified
        assert response.status_code == 200
        prepared_message.refresh_from_db()
        # Recipients are only populated during ready transition, not directly settable
        assert prepared_message.recipients == []


@pytest.mark.django_db
class TestPreparedMessageFullWorkflow:
    """Test complete PreparedMessage workflow through API."""

    def test_full_delivery_workflow(self, api_client, prepared_message):
        """Test the full workflow: draft -> ready -> sent -> delivered."""
        pk = prepared_message.pk
        url = f"/api/plugins/notices/prepared-messages/{pk}/"

        # Draft -> Ready
        response = api_client.patch(url, {"status": "ready", "message": "Approved"}, format="json")
        assert response.status_code == 200
        assert response.data["status"] == "ready"

        # Ready -> Sent
        response = api_client.patch(url, {"status": "sent", "message": "Sent via SMTP"}, format="json")
        assert response.status_code == 200
        assert response.data["status"] == "sent"

        # Sent -> Delivered
        response = api_client.patch(url, {"status": "delivered", "message": "Delivery confirmed"}, format="json")
        assert response.status_code == 200
        assert response.data["status"] == "delivered"

        # Verify final state
        prepared_message.refresh_from_db()
        assert prepared_message.status == PreparedMessageStatusChoices.DELIVERED
        assert prepared_message.sent_at is not None
        assert prepared_message.delivered_at is not None

    def test_failure_and_retry_workflow(self, api_client, prepared_message):
        """Test failure and retry workflow: draft -> ready -> sent -> failed -> ready."""
        pk = prepared_message.pk
        url = f"/api/plugins/notices/prepared-messages/{pk}/"

        # Draft -> Ready -> Sent
        api_client.patch(url, {"status": "ready"}, format="json")
        api_client.patch(url, {"status": "sent"}, format="json")

        # Sent -> Failed
        response = api_client.patch(url, {"status": "failed", "message": "SMTP error"}, format="json")
        assert response.status_code == 200
        assert response.data["status"] == "failed"

        # Failed -> Ready (retry)
        response = api_client.patch(url, {"status": "ready", "message": "Retrying delivery"}, format="json")
        assert response.status_code == 200
        assert response.data["status"] == "ready"
