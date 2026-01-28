"""Tests for NotificationTemplate and PreparedNotification API endpoints."""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from notices.choices import PreparedNotificationStatusChoices
from notices.models import NotificationTemplate, PreparedNotification

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
def notification_template():
    """Create a test notification template."""
    return NotificationTemplate.objects.create(
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
def prepared_notification(notification_template, contact):
    """Create a test prepared notification."""
    notification = PreparedNotification.objects.create(
        template=notification_template,
        status=PreparedNotificationStatusChoices.DRAFT,
        subject="Test Subject",
        body_text="Test body content",
    )
    notification.contacts.add(contact)
    return notification


@pytest.mark.django_db
class TestNotificationTemplateAPI:
    """Test NotificationTemplate API endpoints."""

    def test_list_templates(self, api_client, notification_template):
        """Test listing notification templates."""
        response = api_client.get("/api/plugins/notices/notification-templates/")
        assert response.status_code == 200
        assert len(response.data["results"]) >= 1

    def test_get_template(self, api_client, notification_template):
        """Test retrieving a single template."""
        response = api_client.get(f"/api/plugins/notices/notification-templates/{notification_template.pk}/")
        assert response.status_code == 200
        assert response.data["name"] == "Test Template"
        assert response.data["slug"] == "test-template"

    def test_create_template(self, api_client):
        """Test creating a notification template."""
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
        response = api_client.post("/api/plugins/notices/notification-templates/", data, format="json")
        assert response.status_code == 201
        assert response.data["name"] == "New Template"
        assert NotificationTemplate.objects.filter(slug="new-template").exists()

    def test_update_template(self, api_client, notification_template):
        """Test updating a notification template."""
        data = {"name": "Updated Template"}
        response = api_client.patch(
            f"/api/plugins/notices/notification-templates/{notification_template.pk}/",
            data,
            format="json",
        )
        assert response.status_code == 200
        notification_template.refresh_from_db()
        assert notification_template.name == "Updated Template"

    def test_delete_template(self, api_client, notification_template):
        """Test deleting a notification template."""
        pk = notification_template.pk
        response = api_client.delete(f"/api/plugins/notices/notification-templates/{pk}/")
        assert response.status_code == 204
        assert not NotificationTemplate.objects.filter(pk=pk).exists()


@pytest.mark.django_db
class TestPreparedNotificationAPI:
    """Test PreparedNotification API endpoints."""

    def test_list_notifications(self, api_client, prepared_notification):
        """Test listing prepared notifications."""
        response = api_client.get("/api/plugins/notices/prepared-notifications/")
        assert response.status_code == 200
        assert len(response.data["results"]) >= 1

    def test_filter_by_status(self, api_client, prepared_notification):
        """Test filtering prepared notifications by status."""
        response = api_client.get("/api/plugins/notices/prepared-notifications/?status=draft")
        assert response.status_code == 200
        for notification in response.data["results"]:
            assert notification["status"] == "draft"

    def test_get_notification(self, api_client, prepared_notification):
        """Test retrieving a single prepared notification."""
        response = api_client.get(f"/api/plugins/notices/prepared-notifications/{prepared_notification.pk}/")
        assert response.status_code == 200
        assert response.data["subject"] == "Test Subject"
        assert response.data["status"] == "draft"

    def test_create_notification(self, api_client, notification_template, contact):
        """Test creating a prepared notification."""
        data = {
            "template_id": notification_template.pk,
            "subject": "New Notification Subject",
            "body_text": "New notification body",
            "contact_ids": [contact.pk],
        }
        response = api_client.post("/api/plugins/notices/prepared-notifications/", data, format="json")
        assert response.status_code == 201
        assert response.data["subject"] == "New Notification Subject"
        assert response.data["status"] == "draft"

    def test_update_notification_status_to_ready(self, api_client, prepared_notification, superuser):
        """Test transitioning notification status from draft to ready."""
        response = api_client.patch(
            f"/api/plugins/notices/prepared-notifications/{prepared_notification.pk}/",
            {"status": "ready", "message": "Approved for delivery"},
            format="json",
        )
        assert response.status_code == 200
        prepared_notification.refresh_from_db()
        assert prepared_notification.status == PreparedNotificationStatusChoices.READY
        assert prepared_notification.approved_by == superuser
        assert prepared_notification.approved_at is not None

    def test_invalid_status_transition(self, api_client, prepared_notification):
        """Test that invalid status transitions are rejected."""
        # Try to go directly from draft to sent (invalid)
        response = api_client.patch(
            f"/api/plugins/notices/prepared-notifications/{prepared_notification.pk}/",
            {"status": "sent"},
            format="json",
        )
        assert response.status_code == 400
        assert "status" in response.data

    def test_status_transition_with_timestamp(self, api_client, prepared_notification, superuser):
        """Test status transition with custom timestamp."""
        # First transition to ready
        api_client.patch(
            f"/api/plugins/notices/prepared-notifications/{prepared_notification.pk}/",
            {"status": "ready"},
            format="json",
        )

        # Then transition to sent with a custom timestamp
        custom_time = timezone.now().isoformat()
        response = api_client.patch(
            f"/api/plugins/notices/prepared-notifications/{prepared_notification.pk}/",
            {"status": "sent", "timestamp": custom_time, "message": "Sent via batch"},
            format="json",
        )
        assert response.status_code == 200
        prepared_notification.refresh_from_db()
        assert prepared_notification.status == PreparedNotificationStatusChoices.SENT
        assert prepared_notification.sent_at is not None

    def test_future_timestamp_rejected(self, api_client, prepared_notification):
        """Test that future timestamps are rejected."""
        # First transition to ready
        api_client.patch(
            f"/api/plugins/notices/prepared-notifications/{prepared_notification.pk}/",
            {"status": "ready"},
            format="json",
        )

        # Try to use a future timestamp
        from datetime import timedelta

        future_time = (timezone.now() + timedelta(hours=1)).isoformat()
        response = api_client.patch(
            f"/api/plugins/notices/prepared-notifications/{prepared_notification.pk}/",
            {"status": "sent", "timestamp": future_time},
            format="json",
        )
        assert response.status_code == 400

    def test_journal_entry_created(self, api_client, prepared_notification):
        """Test that journal entry is created when message is provided."""
        from extras.models import JournalEntry

        initial_count = JournalEntry.objects.filter(
            assigned_object_id=prepared_notification.pk,
        ).count()

        api_client.patch(
            f"/api/plugins/notices/prepared-notifications/{prepared_notification.pk}/",
            {"status": "ready", "message": "Test journal entry"},
            format="json",
        )

        new_count = JournalEntry.objects.filter(
            assigned_object_id=prepared_notification.pk,
        ).count()
        assert new_count == initial_count + 1

    def test_delete_notification(self, api_client, prepared_notification):
        """Test deleting a prepared notification."""
        pk = prepared_notification.pk
        response = api_client.delete(f"/api/plugins/notices/prepared-notifications/{pk}/")
        assert response.status_code == 204
        assert not PreparedNotification.objects.filter(pk=pk).exists()

    def test_recipients_readonly(self, api_client, prepared_notification):
        """Test that recipients field is read-only."""
        response = api_client.patch(
            f"/api/plugins/notices/prepared-notifications/{prepared_notification.pk}/",
            {"recipients": [{"email": "hacker@evil.com", "name": "Hacker"}]},
            format="json",
        )
        # Should succeed but recipients should not be modified
        assert response.status_code == 200
        prepared_notification.refresh_from_db()
        # Recipients are only populated during ready transition, not directly settable
        assert prepared_notification.recipients == []


@pytest.mark.django_db
class TestPreparedNotificationFullWorkflow:
    """Test complete PreparedNotification workflow through API."""

    def test_full_delivery_workflow(self, api_client, prepared_notification):
        """Test the full workflow: draft -> ready -> sent -> delivered."""
        pk = prepared_notification.pk
        url = f"/api/plugins/notices/prepared-notifications/{pk}/"

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
        prepared_notification.refresh_from_db()
        assert prepared_notification.status == PreparedNotificationStatusChoices.DELIVERED
        assert prepared_notification.sent_at is not None
        assert prepared_notification.delivered_at is not None

    def test_failure_and_retry_workflow(self, api_client, prepared_notification):
        """Test failure and retry workflow: draft -> ready -> sent -> failed -> ready."""
        pk = prepared_notification.pk
        url = f"/api/plugins/notices/prepared-notifications/{pk}/"

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
