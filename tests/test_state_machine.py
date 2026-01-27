# tests/test_state_machine.py
import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from notices.choices import MessageEventTypeChoices, PreparedNotificationStatusChoices
from notices.models import NotificationTemplate, PreparedNotification
from notices.validators import PreparedNotificationStateMachine

User = get_user_model()


@pytest.fixture
def template():
    return NotificationTemplate.objects.create(
        name="Test Template",
        slug="test-template-sm",
        event_type=MessageEventTypeChoices.NONE,
        subject_template="Subject",
        body_template="Body",
    )


@pytest.fixture
def draft_notification(template):
    return PreparedNotification.objects.create(
        template=template,
        subject="Test Subject",
        body_text="Test Body",
        status=PreparedNotificationStatusChoices.DRAFT,
    )


@pytest.fixture
def admin_user():
    return User.objects.create_user(
        username="admin",
        email="admin@example.com",
        password="testpass123",
    )


@pytest.mark.django_db
class TestPreparedNotificationStateMachine:
    """Tests for PreparedNotification state machine."""

    def test_valid_draft_to_ready(self, draft_notification, admin_user, contact):
        """Test valid transition from draft to ready."""
        draft_notification.contacts.add(contact)
        sm = PreparedNotificationStateMachine(draft_notification, user=admin_user)

        result = sm.transition_to(PreparedNotificationStatusChoices.READY)

        assert result.status == PreparedNotificationStatusChoices.READY
        assert result.approved_by == admin_user
        assert result.approved_at is not None
        assert len(result.recipients) == 1

    def test_draft_to_ready_no_recipients_fails(self, draft_notification, admin_user):
        """Test transition fails when no recipients."""
        sm = PreparedNotificationStateMachine(draft_notification, user=admin_user)

        with pytest.raises(ValidationError, match="no recipients"):
            sm.transition_to(PreparedNotificationStatusChoices.READY)

    def test_invalid_draft_to_sent(self, draft_notification):
        """Test invalid direct transition from draft to sent."""
        sm = PreparedNotificationStateMachine(draft_notification)

        with pytest.raises(ValidationError, match="Cannot transition"):
            sm.transition_to(PreparedNotificationStatusChoices.SENT)

    def test_valid_ready_to_sent(self, draft_notification, admin_user, contact):
        """Test valid transition from ready to sent."""
        draft_notification.contacts.add(contact)
        draft_notification.status = PreparedNotificationStatusChoices.READY
        draft_notification.recipients = [{"email": "test@example.com", "name": "Test", "contact_id": 1}]
        draft_notification.save()

        sm = PreparedNotificationStateMachine(draft_notification)
        result = sm.transition_to(PreparedNotificationStatusChoices.SENT)

        assert result.status == PreparedNotificationStatusChoices.SENT
        assert result.sent_at is not None

    def test_valid_sent_to_delivered(self, draft_notification, contact):
        """Test valid transition from sent to delivered."""
        draft_notification.contacts.add(contact)
        draft_notification.status = PreparedNotificationStatusChoices.SENT
        draft_notification.recipients = [{"email": "test@example.com", "name": "Test", "contact_id": 1}]
        draft_notification.save()

        sm = PreparedNotificationStateMachine(draft_notification)
        result = sm.transition_to(PreparedNotificationStatusChoices.DELIVERED)

        assert result.status == PreparedNotificationStatusChoices.DELIVERED
        assert result.delivered_at is not None

    def test_valid_sent_to_failed(self, draft_notification, contact):
        """Test valid transition from sent to failed."""
        draft_notification.contacts.add(contact)
        draft_notification.status = PreparedNotificationStatusChoices.SENT
        draft_notification.recipients = [{"email": "test@example.com", "name": "Test", "contact_id": 1}]
        draft_notification.save()

        sm = PreparedNotificationStateMachine(draft_notification)
        result = sm.transition_to(PreparedNotificationStatusChoices.FAILED)

        assert result.status == PreparedNotificationStatusChoices.FAILED

    def test_valid_failed_to_ready_retry(self, draft_notification, admin_user, contact):
        """Test retry: failed -> ready."""
        draft_notification.contacts.add(contact)
        draft_notification.status = PreparedNotificationStatusChoices.FAILED
        draft_notification.recipients = [{"email": "test@example.com", "name": "Test", "contact_id": 1}]
        draft_notification.save()

        sm = PreparedNotificationStateMachine(draft_notification, user=admin_user)
        result = sm.transition_to(PreparedNotificationStatusChoices.READY)

        assert result.status == PreparedNotificationStatusChoices.READY

    def test_get_valid_transitions(self, draft_notification):
        """Test getting valid transitions for each state."""
        sm = PreparedNotificationStateMachine(draft_notification)

        # Draft can go to ready
        assert sm.get_valid_transitions() == [PreparedNotificationStatusChoices.READY]

        # Delivered has no transitions
        draft_notification.status = PreparedNotificationStatusChoices.DELIVERED
        assert sm.get_valid_transitions() == []

    def test_journal_entry_created(self, draft_notification, admin_user, contact):
        """Test journal entry is created when message provided."""
        from extras.models import JournalEntry

        draft_notification.contacts.add(contact)
        sm = PreparedNotificationStateMachine(draft_notification, user=admin_user)
        sm.transition_to(PreparedNotificationStatusChoices.READY, message_text="Approved for sending")
        draft_notification.save()

        entries = JournalEntry.objects.filter(
            assigned_object_type__model="preparednotification",
            assigned_object_id=draft_notification.pk,
        )
        assert entries.count() == 1
        assert "Approved for sending" in entries.first().comments
