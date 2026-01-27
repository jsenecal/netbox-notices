# notices/validators.py
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from notices.choices import PreparedMessageStatusChoices

# Valid state transitions
VALID_TRANSITIONS = {
    PreparedMessageStatusChoices.DRAFT: [PreparedMessageStatusChoices.READY],
    PreparedMessageStatusChoices.READY: [PreparedMessageStatusChoices.SENT],
    PreparedMessageStatusChoices.SENT: [
        PreparedMessageStatusChoices.DELIVERED,
        PreparedMessageStatusChoices.FAILED,
    ],
    PreparedMessageStatusChoices.DELIVERED: [],
    PreparedMessageStatusChoices.FAILED: [PreparedMessageStatusChoices.READY],
}


class PreparedMessageStateMachine:
    """
    State machine for PreparedMessage status transitions.

    Validates transitions and performs side effects.
    """

    def __init__(self, message, user=None):
        self.message = message
        self.user = user

    def can_transition_to(self, new_status):
        """Check if transition to new_status is valid."""
        current = self.message.status
        return new_status in VALID_TRANSITIONS.get(current, [])

    def get_valid_transitions(self):
        """Return list of valid target statuses."""
        return VALID_TRANSITIONS.get(self.message.status, [])

    @transaction.atomic
    def transition_to(self, new_status, message_text=None, timestamp=None):
        """
        Transition to new status with validation and side effects.

        Args:
            new_status: Target status
            message_text: Optional message for journal entry
            timestamp: Optional timestamp for the transition (for external systems
                      with batch processing or delayed polling). If not provided,
                      defaults to current time.

        Returns:
            The message instance (saved)

        Raises:
            ValidationError: If transition is invalid or timestamp validation fails
        """
        if not self.can_transition_to(new_status):
            raise ValidationError(
                f"Cannot transition from '{self.message.status}' to '{new_status}'. "
                f"Valid transitions: {', '.join(self.get_valid_transitions()) or 'none'}"
            )

        now = timezone.now()
        ts = timestamp or now

        # Validate timestamp is not in the future
        if ts > now:
            raise ValidationError("timestamp cannot be in the future")

        # Validate timestamp ordering between states
        self._validate_timestamp_order(new_status, ts)

        old_status = self.message.status
        self.message.status = new_status

        # Handle side effects
        if new_status == PreparedMessageStatusChoices.READY:
            self._handle_ready_transition()
        elif new_status == PreparedMessageStatusChoices.SENT:
            self._handle_sent_transition(timestamp=ts)
        elif new_status == PreparedMessageStatusChoices.DELIVERED:
            self._handle_delivered_transition(timestamp=ts)

        # Save the message to persist changes
        self.message.save()

        # Create journal entry if message provided
        if message_text:
            self._create_journal_entry(old_status, new_status, message_text)

        return self.message

    def _validate_timestamp_order(self, new_status, timestamp):
        """Validate that timestamps are logically ordered between states."""
        if new_status == PreparedMessageStatusChoices.SENT:
            # sent_at must be >= approved_at
            if self.message.approved_at and timestamp < self.message.approved_at:
                raise ValidationError("sent_at cannot be before approved_at")

        elif new_status == PreparedMessageStatusChoices.DELIVERED:
            # delivered_at must be >= sent_at
            if self.message.sent_at and timestamp < self.message.sent_at:
                raise ValidationError("delivered_at cannot be before sent_at")

    def _handle_ready_transition(self):
        """Handle draft -> ready transition."""
        # Recompute recipients from contacts
        self._snapshot_recipients()

        # Validate recipients not empty
        if not self.message.recipients:
            raise ValidationError("Cannot approve message with no recipients. Add contacts first.")

        # Set approval tracking
        self.message.approved_by = self.user
        self.message.approved_at = timezone.now()

    def _handle_sent_transition(self, timestamp):
        """Handle ready -> sent transition."""
        if not self.message.sent_at:
            self.message.sent_at = timestamp

    def _handle_delivered_transition(self, timestamp):
        """Handle sent -> delivered transition."""
        if not self.message.delivered_at:
            self.message.delivered_at = timestamp

    def _snapshot_recipients(self):
        """Snapshot recipients from contacts M2M."""
        recipients = []
        for contact in self.message.contacts.all():
            if contact.email:
                recipients.append(
                    {
                        "email": contact.email,
                        "name": contact.name,
                        "contact_id": contact.pk,
                    }
                )
        self.message.recipients = recipients

    def _create_journal_entry(self, old_status, new_status, message_text):
        """Create a journal entry for the status change."""
        from extras.models import JournalEntry

        # Determine kind based on new status
        kind_map = {
            PreparedMessageStatusChoices.READY: "info",
            PreparedMessageStatusChoices.SENT: "info",
            PreparedMessageStatusChoices.DELIVERED: "success",
            PreparedMessageStatusChoices.FAILED: "warning",
        }
        kind = kind_map.get(new_status, "info")

        JournalEntry.objects.create(
            assigned_object=self.message,
            created_by=self.user,
            kind=kind,
            comments=f"Status: {old_status} → {new_status}\n\n{message_text}",
        )
