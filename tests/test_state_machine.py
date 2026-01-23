# tests/test_state_machine.py
import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from notices.choices import MessageEventTypeChoices, PreparedMessageStatusChoices
from notices.models import MessageTemplate, PreparedMessage
from notices.validators import PreparedMessageStateMachine

User = get_user_model()


@pytest.fixture
def template():
    return MessageTemplate.objects.create(
        name="Test Template",
        slug="test-template-sm",
        event_type=MessageEventTypeChoices.NONE,
        subject_template="Subject",
        body_template="Body",
    )


@pytest.fixture
def draft_message(template):
    return PreparedMessage.objects.create(
        template=template,
        subject="Test Subject",
        body_text="Test Body",
        status=PreparedMessageStatusChoices.DRAFT,
    )


@pytest.fixture
def admin_user():
    return User.objects.create_user(
        username="admin",
        email="admin@example.com",
        password="testpass123",
    )


@pytest.mark.django_db
class TestPreparedMessageStateMachine:
    """Tests for PreparedMessage state machine."""

    def test_valid_draft_to_ready(self, draft_message, admin_user, contact):
        """Test valid transition from draft to ready."""
        draft_message.contacts.add(contact)
        sm = PreparedMessageStateMachine(draft_message, user=admin_user)

        result = sm.transition_to(PreparedMessageStatusChoices.READY)

        assert result.status == PreparedMessageStatusChoices.READY
        assert result.approved_by == admin_user
        assert result.approved_at is not None
        assert len(result.recipients) == 1

    def test_draft_to_ready_no_recipients_fails(self, draft_message, admin_user):
        """Test transition fails when no recipients."""
        sm = PreparedMessageStateMachine(draft_message, user=admin_user)

        with pytest.raises(ValidationError, match="no recipients"):
            sm.transition_to(PreparedMessageStatusChoices.READY)

    def test_invalid_draft_to_sent(self, draft_message):
        """Test invalid direct transition from draft to sent."""
        sm = PreparedMessageStateMachine(draft_message)

        with pytest.raises(ValidationError, match="Cannot transition"):
            sm.transition_to(PreparedMessageStatusChoices.SENT)

    def test_valid_ready_to_sent(self, draft_message, admin_user, contact):
        """Test valid transition from ready to sent."""
        draft_message.contacts.add(contact)
        draft_message.status = PreparedMessageStatusChoices.READY
        draft_message.recipients = [{"email": "test@example.com", "name": "Test", "contact_id": 1}]
        draft_message.save()

        sm = PreparedMessageStateMachine(draft_message)
        result = sm.transition_to(PreparedMessageStatusChoices.SENT)

        assert result.status == PreparedMessageStatusChoices.SENT
        assert result.sent_at is not None

    def test_valid_sent_to_delivered(self, draft_message, contact):
        """Test valid transition from sent to delivered."""
        draft_message.contacts.add(contact)
        draft_message.status = PreparedMessageStatusChoices.SENT
        draft_message.recipients = [{"email": "test@example.com", "name": "Test", "contact_id": 1}]
        draft_message.save()

        sm = PreparedMessageStateMachine(draft_message)
        result = sm.transition_to(PreparedMessageStatusChoices.DELIVERED)

        assert result.status == PreparedMessageStatusChoices.DELIVERED
        assert result.delivered_at is not None

    def test_valid_sent_to_failed(self, draft_message, contact):
        """Test valid transition from sent to failed."""
        draft_message.contacts.add(contact)
        draft_message.status = PreparedMessageStatusChoices.SENT
        draft_message.recipients = [{"email": "test@example.com", "name": "Test", "contact_id": 1}]
        draft_message.save()

        sm = PreparedMessageStateMachine(draft_message)
        result = sm.transition_to(PreparedMessageStatusChoices.FAILED)

        assert result.status == PreparedMessageStatusChoices.FAILED

    def test_valid_failed_to_ready_retry(self, draft_message, admin_user, contact):
        """Test retry: failed -> ready."""
        draft_message.contacts.add(contact)
        draft_message.status = PreparedMessageStatusChoices.FAILED
        draft_message.recipients = [{"email": "test@example.com", "name": "Test", "contact_id": 1}]
        draft_message.save()

        sm = PreparedMessageStateMachine(draft_message, user=admin_user)
        result = sm.transition_to(PreparedMessageStatusChoices.READY)

        assert result.status == PreparedMessageStatusChoices.READY

    def test_get_valid_transitions(self, draft_message):
        """Test getting valid transitions for each state."""
        sm = PreparedMessageStateMachine(draft_message)

        # Draft can go to ready
        assert sm.get_valid_transitions() == [PreparedMessageStatusChoices.READY]

        # Delivered has no transitions
        draft_message.status = PreparedMessageStatusChoices.DELIVERED
        assert sm.get_valid_transitions() == []

    def test_journal_entry_created(self, draft_message, admin_user, contact):
        """Test journal entry is created when message provided."""
        from extras.models import JournalEntry

        draft_message.contacts.add(contact)
        sm = PreparedMessageStateMachine(draft_message, user=admin_user)
        sm.transition_to(PreparedMessageStatusChoices.READY, message_text="Approved for sending")
        draft_message.save()

        entries = JournalEntry.objects.filter(
            assigned_object_type__model="preparedmessage",
            assigned_object_id=draft_message.pk,
        )
        assert entries.count() == 1
        assert "Approved for sending" in entries.first().comments
