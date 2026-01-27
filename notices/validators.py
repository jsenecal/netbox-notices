# notices/validators.py
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from notices.choices import PreparedNotificationStatusChoices

# Valid state transitions
VALID_TRANSITIONS = {
    PreparedNotificationStatusChoices.DRAFT: [PreparedNotificationStatusChoices.READY],
    PreparedNotificationStatusChoices.READY: [PreparedNotificationStatusChoices.SENT],
    PreparedNotificationStatusChoices.SENT: [
        PreparedNotificationStatusChoices.DELIVERED,
        PreparedNotificationStatusChoices.FAILED,
    ],
    PreparedNotificationStatusChoices.DELIVERED: [],
    PreparedNotificationStatusChoices.FAILED: [PreparedNotificationStatusChoices.READY],
}


class PreparedNotificationStateMachine:
    """
    State machine for PreparedNotification status transitions.

    Validates transitions and performs side effects.
    """

    def __init__(self, notification, user=None):
        self.notification = notification
        self.user = user

    def can_transition_to(self, new_status):
        """Check if transition to new_status is valid."""
        current = self.notification.status
        return new_status in VALID_TRANSITIONS.get(current, [])

    def get_valid_transitions(self):
        """Return list of valid target statuses."""
        return VALID_TRANSITIONS.get(self.notification.status, [])

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
            The notification instance (saved)

        Raises:
            ValidationError: If transition is invalid or timestamp validation fails
        """
        if not self.can_transition_to(new_status):
            raise ValidationError(
                f"Cannot transition from '{self.notification.status}' to '{new_status}'. "
                f"Valid transitions: {', '.join(self.get_valid_transitions()) or 'none'}"
            )

        now = timezone.now()
        ts = timestamp or now

        # Validate timestamp is not in the future
        if ts > now:
            raise ValidationError("timestamp cannot be in the future")

        # Validate timestamp ordering between states
        self._validate_timestamp_order(new_status, ts)

        old_status = self.notification.status
        self.notification.status = new_status

        # Handle side effects
        if new_status == PreparedNotificationStatusChoices.READY:
            self._handle_ready_transition()
        elif new_status == PreparedNotificationStatusChoices.SENT:
            self._handle_sent_transition(timestamp=ts)
        elif new_status == PreparedNotificationStatusChoices.DELIVERED:
            self._handle_delivered_transition(timestamp=ts)

        # Save the notification to persist changes
        self.notification.save()

        # Create journal entry if message provided
        if message_text:
            self._create_journal_entry(old_status, new_status, message_text)

        return self.notification

    def _validate_timestamp_order(self, new_status, timestamp):
        """Validate that timestamps are logically ordered between states."""
        if new_status == PreparedNotificationStatusChoices.SENT:
            # sent_at must be >= approved_at
            if self.notification.approved_at and timestamp < self.notification.approved_at:
                raise ValidationError("sent_at cannot be before approved_at")

        elif new_status == PreparedNotificationStatusChoices.DELIVERED:
            # delivered_at must be >= sent_at
            if self.notification.sent_at and timestamp < self.notification.sent_at:
                raise ValidationError("delivered_at cannot be before sent_at")

    def _handle_ready_transition(self):
        """Handle draft -> ready transition."""
        # Recompute recipients from contacts
        self._snapshot_recipients()

        # Validate recipients not empty
        if not self.notification.recipients:
            raise ValidationError("Cannot approve notification with no recipients. Add contacts first.")

        # Set approval tracking
        self.notification.approved_by = self.user
        self.notification.approved_at = timezone.now()

    def _handle_sent_transition(self, timestamp):
        """Handle ready -> sent transition."""
        if not self.notification.sent_at:
            self.notification.sent_at = timestamp

    def _handle_delivered_transition(self, timestamp):
        """Handle sent -> delivered transition."""
        if not self.notification.delivered_at:
            self.notification.delivered_at = timestamp

    def _snapshot_recipients(self):
        """Snapshot recipients from contacts M2M."""
        recipients = []
        for contact in self.notification.contacts.all():
            if contact.email:
                recipients.append(
                    {
                        "email": contact.email,
                        "name": contact.name,
                        "contact_id": contact.pk,
                    }
                )
        self.notification.recipients = recipients

    def _create_journal_entry(self, old_status, new_status, message_text):
        """Create a journal entry for the status change."""
        from extras.models import JournalEntry

        # Determine kind based on new status
        kind_map = {
            PreparedNotificationStatusChoices.READY: "info",
            PreparedNotificationStatusChoices.SENT: "info",
            PreparedNotificationStatusChoices.DELIVERED: "success",
            PreparedNotificationStatusChoices.FAILED: "warning",
        }
        kind = kind_map.get(new_status, "info")

        JournalEntry.objects.create(
            assigned_object=self.notification,
            created_by=self.user,
            kind=kind,
            comments=f"Status: {old_status} → {new_status}\n\n{message_text}",
        )
