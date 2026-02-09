# Outgoing Notifications Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a message composition system that prepares outgoing notifications using Jinja templates, discovers recipients from NetBox contacts, and exposes messages for external delivery systems.

**Architecture:** Content/delivery separation - this plugin handles templates, recipient discovery, message composition, and state tracking. External systems handle actual delivery via pull-based REST API. Templates use Config Context-like scoping with field-level and block-level (Jinja inheritance) merging.

**Tech Stack:** Django ORM, NetBoxModel, Jinja2, python-markdown, PyYAML, GenericForeignKey

**Design Document:** `docs/plans/2026-01-22-outgoing-notifications-design.md`

**GitHub Issues:**
- Main: #2
- Models: #3 | Template Engine: #4 | Recipients: #5 | Matching: #6
- State Machine: #7 | iCal: #8 | API: #9 | UI: #10 | Docs: #11

---

## Phase 1: Data Models (#3)

### Task 1.1: Add Choices for New Models

**Files:**
- Modify: `notices/choices.py`

**Step 1: Add choices classes**

```python
# Add to notices/choices.py

class MessageEventTypeChoices(ChoiceSet):
    """Event type choices for message templates."""
    MAINTENANCE = 'maintenance'
    OUTAGE = 'outage'
    BOTH = 'both'
    NONE = 'none'

    CHOICES = [
        (MAINTENANCE, 'Maintenance'),
        (OUTAGE, 'Outage'),
        (BOTH, 'Both'),
        (NONE, 'None (Standalone)'),
    ]


class MessageGranularityChoices(ChoiceSet):
    """Granularity choices for message generation."""
    PER_EVENT = 'per_event'
    PER_TENANT = 'per_tenant'
    PER_IMPACT = 'per_impact'

    CHOICES = [
        (PER_EVENT, 'Per Event'),
        (PER_TENANT, 'Per Tenant'),
        (PER_IMPACT, 'Per Impact'),
    ]


class BodyFormatChoices(ChoiceSet):
    """Body format choices for templates."""
    MARKDOWN = 'markdown'
    HTML = 'html'
    TEXT = 'text'

    CHOICES = [
        (MARKDOWN, 'Markdown'),
        (HTML, 'HTML'),
        (TEXT, 'Plain Text'),
    ]


class PreparedMessageStatusChoices(ChoiceSet):
    """Status choices for prepared messages."""
    DRAFT = 'draft'
    READY = 'ready'
    SENT = 'sent'
    DELIVERED = 'delivered'
    FAILED = 'failed'

    CHOICES = [
        (DRAFT, 'Draft'),
        (READY, 'Ready'),
        (SENT, 'Sent'),
        (DELIVERED, 'Delivered'),
        (FAILED, 'Failed'),
    ]


class ContactPriorityChoices(ChoiceSet):
    """Contact priority choices (mirrors NetBox's ContactPriorityChoices)."""
    PRIMARY = 'primary'
    SECONDARY = 'secondary'
    TERTIARY = 'tertiary'

    CHOICES = [
        (PRIMARY, 'Primary'),
        (SECONDARY, 'Secondary'),
        (TERTIARY, 'Tertiary'),
    ]
```

**Step 2: Run linting**

Run: `make lint`
Expected: PASS

**Step 3: Commit**

```bash
git add notices/choices.py
git commit -m "feat(models): add choices for message templates and prepared messages

Part of #3"
```

---

### Task 1.2: Create MessageTemplate Model

**Files:**
- Create: `notices/models/messaging.py`
- Modify: `notices/models/__init__.py`

**Step 1: Create the messaging models file**

```python
# notices/models/messaging.py
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.urls import reverse

from netbox.models import NetBoxModel
from tenancy.models import Contact, ContactRole

from notices.choices import (
    BodyFormatChoices,
    ContactPriorityChoices,
    MessageEventTypeChoices,
    MessageGranularityChoices,
    PreparedMessageStatusChoices,
)

__all__ = (
    'MessageTemplate',
    'TemplateScope',
    'PreparedMessage',
)


class MessageTemplate(NetBoxModel):
    """
    A Jinja template for generating outgoing notifications.

    Templates can be scoped to specific objects (tenants, providers, sites, etc.)
    via TemplateScope assignments, similar to Config Contexts.
    """
    name = models.CharField(
        max_length=100,
    )
    slug = models.SlugField(
        unique=True,
    )
    description = models.TextField(
        blank=True,
    )

    # Event type targeting
    event_type = models.CharField(
        max_length=20,
        choices=MessageEventTypeChoices,
        help_text='Which event types this template applies to.',
    )

    # Generation granularity
    granularity = models.CharField(
        max_length=20,
        choices=MessageGranularityChoices,
        default=MessageGranularityChoices.PER_TENANT,
        help_text='How messages are grouped when generated from events.',
    )

    # Content templates
    subject_template = models.TextField(
        help_text='Jinja template for the email subject line.',
    )
    body_template = models.TextField(
        help_text='Jinja template for the message body. Supports {% block %} inheritance.',
    )
    body_format = models.CharField(
        max_length=20,
        choices=BodyFormatChoices,
        default=BodyFormatChoices.MARKDOWN,
        help_text='Format of the body template.',
    )
    css_template = models.TextField(
        blank=True,
        help_text='CSS styles for HTML output.',
    )
    headers_template = models.JSONField(
        default=dict,
        blank=True,
        help_text='Jinja templates for email headers (stored as JSON, accepts YAML input).',
    )

    # iCal (Maintenance only)
    include_ical = models.BooleanField(
        default=False,
        help_text='Whether to generate an iCal attachment (Maintenance only).',
    )
    ical_template = models.TextField(
        blank=True,
        help_text='Jinja template for iCal content (BCOP-compliant).',
    )

    # Recipient discovery
    contact_roles = models.ManyToManyField(
        to=ContactRole,
        blank=True,
        related_name='message_templates',
        help_text='Contact roles to include when discovering recipients.',
    )
    contact_priorities = ArrayField(
        base_field=models.CharField(max_length=20, choices=ContactPriorityChoices),
        default=list,
        blank=True,
        help_text='Contact priorities to include (e.g., primary, secondary).',
    )

    # Template inheritance
    is_base_template = models.BooleanField(
        default=False,
        help_text='Whether this template can be extended by other templates.',
    )
    extends = models.ForeignKey(
        to='self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children',
        help_text='Parent template to extend (for Jinja block inheritance).',
    )

    # Merge weight
    weight = models.IntegerField(
        default=1000,
        help_text='Base weight for template matching (higher = wins conflicts).',
    )

    class Meta:
        ordering = ['name']
        verbose_name = 'Message Template'
        verbose_name_plural = 'Message Templates'

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('plugins:notices:messagetemplate', args=[self.pk])
```

**Step 2: Update models __init__.py**

```python
# Add to notices/models/__init__.py
from .messaging import *
```

**Step 3: Run linting**

Run: `make lint`
Expected: PASS

**Step 4: Commit**

```bash
git add notices/models/messaging.py notices/models/__init__.py
git commit -m "feat(models): add MessageTemplate model

Part of #3"
```

---

### Task 1.3: Create TemplateScope Model

**Files:**
- Modify: `notices/models/messaging.py`

**Step 1: Add TemplateScope model**

```python
# Add to notices/models/messaging.py after MessageTemplate

class TemplateScope(models.Model):
    """
    Links a MessageTemplate to NetBox objects for Config Context-like matching.

    When generating messages, templates with matching scopes are selected
    and merged by weight.
    """
    template = models.ForeignKey(
        to=MessageTemplate,
        on_delete=models.CASCADE,
        related_name='scopes',
    )

    # GenericFK to any NetBox object
    content_type = models.ForeignKey(
        to=ContentType,
        on_delete=models.CASCADE,
        help_text='The type of object this scope matches.',
    )
    object_id = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        help_text='Specific object ID (null = all of this type).',
    )
    object = GenericForeignKey('content_type', 'object_id')

    # Event filtering
    event_type = models.CharField(
        max_length=20,
        choices=MessageEventTypeChoices,
        null=True,
        blank=True,
        help_text='Filter by event type.',
    )
    event_status = models.CharField(
        max_length=50,
        blank=True,
        help_text='Filter by event status (e.g., CONFIRMED, TENTATIVE).',
    )

    # Merge priority
    weight = models.IntegerField(
        default=1000,
        help_text='Weight for this scope (higher = higher priority in merge).',
    )

    class Meta:
        ordering = ['template', '-weight']
        verbose_name = 'Template Scope'
        verbose_name_plural = 'Template Scopes'
        constraints = [
            models.UniqueConstraint(
                fields=['template', 'content_type', 'object_id', 'event_type', 'event_status'],
                name='unique_template_scope',
            ),
        ]

    def __str__(self):
        obj_str = str(self.object) if self.object_id else f'All {self.content_type.model}s'
        return f'{self.template.name} → {obj_str}'
```

**Step 2: Update __all__ export**

```python
# Update __all__ in notices/models/messaging.py
__all__ = (
    'MessageTemplate',
    'TemplateScope',
    'PreparedMessage',
)
```

**Step 3: Run linting**

Run: `make lint`
Expected: PASS

**Step 4: Commit**

```bash
git add notices/models/messaging.py
git commit -m "feat(models): add TemplateScope model

Part of #3"
```

---

### Task 1.4: Create PreparedMessage Model

**Files:**
- Modify: `notices/models/messaging.py`

**Step 1: Add PreparedMessage model**

```python
# Add to notices/models/messaging.py after TemplateScope

User = get_user_model()


class PreparedMessage(NetBoxModel):
    """
    A rendered message ready for delivery.

    Stores a snapshot of rendered content and recipients at generation time.
    Status transitions are validated via state machine.
    """
    # Source template
    template = models.ForeignKey(
        to=MessageTemplate,
        on_delete=models.PROTECT,
        related_name='prepared_messages',
    )

    # Linked event (optional)
    event_content_type = models.ForeignKey(
        to=ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    event_id = models.PositiveBigIntegerField(
        null=True,
        blank=True,
    )
    event = GenericForeignKey('event_content_type', 'event_id')

    # Status
    status = models.CharField(
        max_length=20,
        choices=PreparedMessageStatusChoices,
        default=PreparedMessageStatusChoices.DRAFT,
    )

    # Recipients
    contacts = models.ManyToManyField(
        to=Contact,
        blank=True,
        related_name='prepared_messages',
        help_text='Contacts to receive this message.',
    )
    recipients = models.JSONField(
        default=list,
        help_text='Readonly snapshot of recipients at send time.',
    )

    # Rendered content snapshot
    subject = models.CharField(
        max_length=255,
    )
    body_text = models.TextField()
    body_html = models.TextField(
        blank=True,
    )
    headers = models.JSONField(
        default=dict,
    )
    css = models.TextField(
        blank=True,
    )
    ical_content = models.TextField(
        blank=True,
    )

    # Approval tracking
    approved_by = models.ForeignKey(
        to=User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    # Delivery tracking
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    delivered_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    viewed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ['-created']
        verbose_name = 'Prepared Message'
        verbose_name_plural = 'Prepared Messages'

    def __str__(self):
        return f'{self.subject[:50]}...' if len(self.subject) > 50 else self.subject

    def get_absolute_url(self):
        return reverse('plugins:notices:preparedmessage', args=[self.pk])

    @property
    def event_type_name(self):
        """Return the event type name (maintenance/outage) or None."""
        if self.event_content_type:
            return self.event_content_type.model
        return None
```

**Step 2: Run linting**

Run: `make lint`
Expected: PASS

**Step 3: Commit**

```bash
git add notices/models/messaging.py
git commit -m "feat(models): add PreparedMessage model

Part of #3"
```

---

### Task 1.5: Create and Run Migrations

**Files:**
- Create: `notices/migrations/XXXX_add_messaging_models.py` (auto-generated)

**Step 1: Create migration**

Run: `make makemigrations`
Expected: Migration file created

**Step 2: Review migration**

Run: `ls -la notices/migrations/`
Expected: New migration file visible

**Step 3: Run migration**

Run: `make migrate`
Expected: Migration applied successfully

**Step 4: Commit**

```bash
git add notices/migrations/
git commit -m "feat(models): add messaging models migration

Part of #3"
```

---

### Task 1.6: Write Model Tests

**Files:**
- Create: `tests/test_messaging_models.py`

**Step 1: Write model tests**

```python
# tests/test_messaging_models.py
import pytest
from django.contrib.contenttypes.models import ContentType

from notices.models import MessageTemplate, TemplateScope, PreparedMessage
from notices.choices import (
    MessageEventTypeChoices,
    MessageGranularityChoices,
    BodyFormatChoices,
    PreparedMessageStatusChoices,
)


@pytest.mark.django_db
class TestMessageTemplate:
    """Tests for MessageTemplate model."""

    def test_create_minimal_template(self):
        """Test creating a template with minimal required fields."""
        template = MessageTemplate.objects.create(
            name='Test Template',
            slug='test-template',
            event_type=MessageEventTypeChoices.MAINTENANCE,
            subject_template='Test Subject',
            body_template='Test Body',
        )
        assert template.pk is not None
        assert template.name == 'Test Template'
        assert template.granularity == MessageGranularityChoices.PER_TENANT
        assert template.body_format == BodyFormatChoices.MARKDOWN

    def test_template_str(self):
        """Test template string representation."""
        template = MessageTemplate.objects.create(
            name='My Template',
            slug='my-template',
            event_type=MessageEventTypeChoices.BOTH,
            subject_template='Subject',
            body_template='Body',
        )
        assert str(template) == 'My Template'

    def test_template_inheritance(self):
        """Test template extends relationship."""
        base = MessageTemplate.objects.create(
            name='Base Template',
            slug='base-template',
            event_type=MessageEventTypeChoices.MAINTENANCE,
            subject_template='Base Subject',
            body_template='{% block content %}{% endblock %}',
            is_base_template=True,
        )
        child = MessageTemplate.objects.create(
            name='Child Template',
            slug='child-template',
            event_type=MessageEventTypeChoices.MAINTENANCE,
            subject_template='Child Subject',
            body_template='{% block content %}Child Content{% endblock %}',
            extends=base,
        )
        assert child.extends == base
        assert base.children.first() == child


@pytest.mark.django_db
class TestTemplateScope:
    """Tests for TemplateScope model."""

    def test_create_scope_with_object(self, tenant):
        """Test creating a scope for a specific object."""
        template = MessageTemplate.objects.create(
            name='Scoped Template',
            slug='scoped-template',
            event_type=MessageEventTypeChoices.MAINTENANCE,
            subject_template='Subject',
            body_template='Body',
        )
        content_type = ContentType.objects.get_for_model(tenant)
        scope = TemplateScope.objects.create(
            template=template,
            content_type=content_type,
            object_id=tenant.pk,
            weight=2000,
        )
        assert scope.object == tenant
        assert scope.weight == 2000

    def test_create_scope_for_all_of_type(self, tenant):
        """Test creating a scope for all objects of a type."""
        template = MessageTemplate.objects.create(
            name='Type Scoped Template',
            slug='type-scoped-template',
            event_type=MessageEventTypeChoices.OUTAGE,
            subject_template='Subject',
            body_template='Body',
        )
        content_type = ContentType.objects.get_for_model(tenant)
        scope = TemplateScope.objects.create(
            template=template,
            content_type=content_type,
            object_id=None,  # All tenants
        )
        assert scope.object_id is None
        assert 'All tenant' in str(scope).lower()


@pytest.mark.django_db
class TestPreparedMessage:
    """Tests for PreparedMessage model."""

    def test_create_prepared_message(self):
        """Test creating a prepared message."""
        template = MessageTemplate.objects.create(
            name='Test Template',
            slug='test-template',
            event_type=MessageEventTypeChoices.NONE,
            subject_template='Subject',
            body_template='Body',
        )
        message = PreparedMessage.objects.create(
            template=template,
            subject='Test Subject Line',
            body_text='Test body content',
        )
        assert message.pk is not None
        assert message.status == PreparedMessageStatusChoices.DRAFT
        assert message.approved_by is None

    def test_prepared_message_str_short(self):
        """Test message string representation for short subjects."""
        template = MessageTemplate.objects.create(
            name='Test',
            slug='test',
            event_type=MessageEventTypeChoices.NONE,
            subject_template='S',
            body_template='B',
        )
        message = PreparedMessage.objects.create(
            template=template,
            subject='Short Subject',
            body_text='Body',
        )
        assert str(message) == 'Short Subject'

    def test_prepared_message_str_truncated(self):
        """Test message string representation for long subjects."""
        template = MessageTemplate.objects.create(
            name='Test',
            slug='test2',
            event_type=MessageEventTypeChoices.NONE,
            subject_template='S',
            body_template='B',
        )
        long_subject = 'A' * 100
        message = PreparedMessage.objects.create(
            template=template,
            subject=long_subject,
            body_text='Body',
        )
        assert str(message) == 'A' * 50 + '...'
```

**Step 2: Create test fixture for tenant**

```python
# Add to tests/conftest.py
import pytest
from tenancy.models import Tenant


@pytest.fixture
def tenant():
    """Create a test tenant."""
    return Tenant.objects.create(
        name='Test Tenant',
        slug='test-tenant',
    )
```

**Step 3: Run tests**

Run: `make test`
Expected: All tests pass

**Step 4: Commit**

```bash
git add tests/test_messaging_models.py tests/conftest.py
git commit -m "test(models): add messaging model tests

Part of #3
Closes #3"
```

---

## Phase 2: State Machine (#7)

### Task 2.1: Create State Machine Validator

**Files:**
- Create: `notices/validators.py`

**Step 1: Write the state machine validator**

```python
# notices/validators.py
from django.core.exceptions import ValidationError
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

    def transition_to(self, new_status, message_text=None):
        """
        Transition to new status with validation and side effects.

        Args:
            new_status: Target status
            message_text: Optional message for journal entry

        Returns:
            The message instance

        Raises:
            ValidationError: If transition is invalid
        """
        if not self.can_transition_to(new_status):
            raise ValidationError(
                f"Cannot transition from '{self.message.status}' to '{new_status}'. "
                f"Valid transitions: {', '.join(self.get_valid_transitions()) or 'none'}"
            )

        old_status = self.message.status
        self.message.status = new_status

        # Handle side effects
        if new_status == PreparedMessageStatusChoices.READY:
            self._handle_ready_transition()
        elif new_status == PreparedMessageStatusChoices.SENT:
            self._handle_sent_transition()
        elif new_status == PreparedMessageStatusChoices.DELIVERED:
            self._handle_delivered_transition()

        # Create journal entry if message provided
        if message_text:
            self._create_journal_entry(old_status, new_status, message_text)

        return self.message

    def _handle_ready_transition(self):
        """Handle draft -> ready transition."""
        # Recompute recipients from contacts
        self._snapshot_recipients()

        # Validate recipients not empty
        if not self.message.recipients:
            raise ValidationError(
                "Cannot approve message with no recipients. Add contacts first."
            )

        # Set approval tracking
        self.message.approved_by = self.user
        self.message.approved_at = timezone.now()

    def _handle_sent_transition(self):
        """Handle ready -> sent transition."""
        if not self.message.sent_at:
            self.message.sent_at = timezone.now()

    def _handle_delivered_transition(self):
        """Handle sent -> delivered transition."""
        if not self.message.delivered_at:
            self.message.delivered_at = timezone.now()

    def _snapshot_recipients(self):
        """Snapshot recipients from contacts M2M."""
        recipients = []
        for contact in self.message.contacts.all():
            if contact.email:
                recipients.append({
                    'email': contact.email,
                    'name': contact.name,
                    'contact_id': contact.pk,
                })
        self.message.recipients = recipients

    def _create_journal_entry(self, old_status, new_status, message_text):
        """Create a journal entry for the status change."""
        from extras.models import JournalEntry

        # Determine kind based on new status
        kind_map = {
            PreparedMessageStatusChoices.READY: 'info',
            PreparedMessageStatusChoices.SENT: 'info',
            PreparedMessageStatusChoices.DELIVERED: 'success',
            PreparedMessageStatusChoices.FAILED: 'warning',
        }
        kind = kind_map.get(new_status, 'info')

        JournalEntry.objects.create(
            assigned_object=self.message,
            created_by=self.user,
            kind=kind,
            comments=f"Status: {old_status} → {new_status}\n\n{message_text}",
        )
```

**Step 2: Run linting**

Run: `make lint`
Expected: PASS

**Step 3: Commit**

```bash
git add notices/validators.py
git commit -m "feat(validators): add PreparedMessage state machine

Part of #7"
```

---

### Task 2.2: Write State Machine Tests

**Files:**
- Create: `tests/test_state_machine.py`

**Step 1: Write state machine tests**

```python
# tests/test_state_machine.py
import pytest
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from notices.models import MessageTemplate, PreparedMessage
from notices.choices import MessageEventTypeChoices, PreparedMessageStatusChoices
from notices.validators import PreparedMessageStateMachine

User = get_user_model()


@pytest.fixture
def template():
    return MessageTemplate.objects.create(
        name='Test Template',
        slug='test-template-sm',
        event_type=MessageEventTypeChoices.NONE,
        subject_template='Subject',
        body_template='Body',
    )


@pytest.fixture
def draft_message(template):
    return PreparedMessage.objects.create(
        template=template,
        subject='Test Subject',
        body_text='Test Body',
        status=PreparedMessageStatusChoices.DRAFT,
    )


@pytest.fixture
def admin_user():
    return User.objects.create_user(
        username='admin',
        email='admin@example.com',
        password='testpass123',
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
        draft_message.recipients = [{'email': 'test@example.com', 'name': 'Test', 'contact_id': 1}]
        draft_message.save()

        sm = PreparedMessageStateMachine(draft_message)
        result = sm.transition_to(PreparedMessageStatusChoices.SENT)

        assert result.status == PreparedMessageStatusChoices.SENT
        assert result.sent_at is not None

    def test_valid_sent_to_delivered(self, draft_message, contact):
        """Test valid transition from sent to delivered."""
        draft_message.contacts.add(contact)
        draft_message.status = PreparedMessageStatusChoices.SENT
        draft_message.recipients = [{'email': 'test@example.com', 'name': 'Test', 'contact_id': 1}]
        draft_message.save()

        sm = PreparedMessageStateMachine(draft_message)
        result = sm.transition_to(PreparedMessageStatusChoices.DELIVERED)

        assert result.status == PreparedMessageStatusChoices.DELIVERED
        assert result.delivered_at is not None

    def test_valid_sent_to_failed(self, draft_message, contact):
        """Test valid transition from sent to failed."""
        draft_message.contacts.add(contact)
        draft_message.status = PreparedMessageStatusChoices.SENT
        draft_message.recipients = [{'email': 'test@example.com', 'name': 'Test', 'contact_id': 1}]
        draft_message.save()

        sm = PreparedMessageStateMachine(draft_message)
        result = sm.transition_to(PreparedMessageStatusChoices.FAILED)

        assert result.status == PreparedMessageStatusChoices.FAILED

    def test_valid_failed_to_ready_retry(self, draft_message, admin_user, contact):
        """Test retry: failed -> ready."""
        draft_message.contacts.add(contact)
        draft_message.status = PreparedMessageStatusChoices.FAILED
        draft_message.recipients = [{'email': 'test@example.com', 'name': 'Test', 'contact_id': 1}]
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
            assigned_object_type__model='preparedmessage',
            assigned_object_id=draft_message.pk,
        )
        assert entries.count() == 1
        assert "Approved for sending" in entries.first().comments
```

**Step 2: Add contact fixture to conftest.py**

```python
# Add to tests/conftest.py
from tenancy.models import Contact


@pytest.fixture
def contact():
    """Create a test contact with email."""
    return Contact.objects.create(
        name='Test Contact',
        email='test@example.com',
    )
```

**Step 3: Run tests**

Run: `make test`
Expected: All tests pass

**Step 4: Commit**

```bash
git add tests/test_state_machine.py tests/conftest.py
git commit -m "test(validators): add state machine tests

Part of #7
Closes #7"
```

---

## Phase 3: Template Engine (#4)

### Task 3.1: Create Template Rendering Service

**Files:**
- Create: `notices/services/__init__.py`
- Create: `notices/services/template_renderer.py`

**Step 1: Create services directory**

```python
# notices/services/__init__.py
from .template_renderer import *
```

**Step 2: Create template renderer**

```python
# notices/services/template_renderer.py
import markdown
from django.conf import settings
from django.utils import timezone
from jinja2 import Environment, BaseLoader, TemplateSyntaxError, UndefinedError

__all__ = ('TemplateRenderer', 'TemplateRenderError')


class TemplateRenderError(Exception):
    """Raised when template rendering fails."""
    pass


class StringLoader(BaseLoader):
    """Jinja loader that loads templates from strings."""

    def __init__(self, templates=None):
        self.templates = templates or {}

    def get_source(self, environment, template):
        if template in self.templates:
            source = self.templates[template]
            return source, template, lambda: True
        raise TemplateSyntaxError(f"Template '{template}' not found", lineno=1)


def ical_datetime(dt):
    """Format datetime as iCal datetime string."""
    if dt is None:
        return ''
    # Convert to UTC and format as YYYYMMDDTHHMMSSZ
    if timezone.is_aware(dt):
        dt = dt.astimezone(timezone.utc)
    return dt.strftime('%Y%m%dT%H%M%SZ')


def render_markdown(text):
    """Render markdown text to HTML."""
    if not text:
        return ''
    return markdown.markdown(
        text,
        extensions=['tables', 'fenced_code', 'nl2br'],
    )


class TemplateRenderer:
    """
    Renders Jinja templates with message context.

    Provides custom filters for iCal datetime formatting and Markdown rendering.
    """

    def __init__(self, templates=None):
        """
        Initialize renderer.

        Args:
            templates: Optional dict of template_name -> template_string for inheritance
        """
        loader = StringLoader(templates) if templates else None
        self.env = Environment(
            loader=loader,
            autoescape=False,
        )
        # Register custom filters
        self.env.filters['ical_datetime'] = ical_datetime
        self.env.filters['markdown'] = render_markdown

    def render(self, template_string, context):
        """
        Render a template string with context.

        Args:
            template_string: Jinja template string
            context: Dict of template variables

        Returns:
            Rendered string

        Raises:
            TemplateRenderError: If rendering fails
        """
        try:
            template = self.env.from_string(template_string)
            return template.render(**context)
        except (TemplateSyntaxError, UndefinedError) as e:
            raise TemplateRenderError(f"Template rendering failed: {e}")

    def validate(self, template_string):
        """
        Validate template syntax without rendering.

        Args:
            template_string: Jinja template string

        Returns:
            True if valid

        Raises:
            TemplateRenderError: If syntax is invalid
        """
        try:
            self.env.parse(template_string)
            return True
        except TemplateSyntaxError as e:
            raise TemplateRenderError(f"Invalid template syntax: {e}")

    def render_with_inheritance(self, child_template, base_name='base'):
        """
        Render a template that extends a base template.

        Args:
            child_template: Child template string (should have {% extends "base" %})
            base_name: Name of the base template in self.templates

        Returns:
            Rendered string
        """
        try:
            template = self.env.from_string(child_template)
            return template.render()
        except (TemplateSyntaxError, UndefinedError) as e:
            raise TemplateRenderError(f"Template inheritance rendering failed: {e}")

    @classmethod
    def build_context(cls, message_template, event=None, tenant=None, impacts=None, **extra):
        """
        Build the full template context for rendering.

        Args:
            message_template: The MessageTemplate being rendered
            event: Optional Maintenance or Outage event
            tenant: Optional target tenant
            impacts: Optional list of Impact records
            **extra: Additional context variables

        Returns:
            Dict of context variables
        """
        context = {
            'now': timezone.now(),
            'netbox_url': getattr(settings, 'BASE_URL', ''),
            'tenant': tenant,
            'impacts': impacts or [],
        }

        if event:
            # Determine event type and add appropriate variables
            event_type = event.__class__.__name__.lower()
            context[event_type] = event

            if event_type == 'maintenance':
                context['maintenance'] = event
            elif event_type == 'outage':
                context['outage'] = event

            # Filter impacts for this tenant if specified
            if tenant and impacts:
                context['tenant_impacts'] = [
                    i for i in impacts
                    if hasattr(i.target, 'tenant') and i.target.tenant == tenant
                ]
            else:
                context['tenant_impacts'] = impacts or []

            # Calculate highest impact
            if impacts:
                impact_order = ['OUTAGE', 'DEGRADED', 'REDUCED-REDUNDANCY', 'NO-IMPACT']
                highest = 'NO-IMPACT'
                for impact in impacts:
                    if impact_order.index(impact.impact) < impact_order.index(highest):
                        highest = impact.impact
                context['highest_impact'] = highest

        context.update(extra)
        return context
```

**Step 3: Run linting**

Run: `make lint`
Expected: PASS

**Step 4: Commit**

```bash
git add notices/services/
git commit -m "feat(services): add template rendering service

Part of #4"
```

---

### Task 3.2: Write Template Renderer Tests

**Files:**
- Create: `tests/test_template_renderer.py`

**Step 1: Write template renderer tests**

```python
# tests/test_template_renderer.py
import pytest
from datetime import datetime
from django.utils import timezone

from notices.services.template_renderer import (
    TemplateRenderer,
    TemplateRenderError,
    ical_datetime,
    render_markdown,
)


class TestIcalDatetime:
    """Tests for ical_datetime filter."""

    def test_formats_utc_datetime(self):
        """Test formatting a UTC datetime."""
        dt = datetime(2026, 1, 22, 14, 30, 0, tzinfo=timezone.utc)
        result = ical_datetime(dt)
        assert result == '20260122T143000Z'

    def test_converts_timezone(self):
        """Test converting non-UTC timezone to UTC."""
        # Create a datetime in a different timezone
        from zoneinfo import ZoneInfo
        dt = datetime(2026, 1, 22, 9, 30, 0, tzinfo=ZoneInfo('US/Eastern'))
        result = ical_datetime(dt)
        # 9:30 EST = 14:30 UTC
        assert result == '20260122T143000Z'

    def test_handles_none(self):
        """Test handling None input."""
        result = ical_datetime(None)
        assert result == ''


class TestRenderMarkdown:
    """Tests for render_markdown filter."""

    def test_renders_basic_markdown(self):
        """Test rendering basic markdown."""
        result = render_markdown('**bold** and *italic*')
        assert '<strong>bold</strong>' in result
        assert '<em>italic</em>' in result

    def test_renders_tables(self):
        """Test rendering markdown tables."""
        md = """
| Header |
|--------|
| Cell   |
"""
        result = render_markdown(md)
        assert '<table>' in result

    def test_handles_empty(self):
        """Test handling empty input."""
        result = render_markdown('')
        assert result == ''

        result = render_markdown(None)
        assert result == ''


class TestTemplateRenderer:
    """Tests for TemplateRenderer class."""

    def test_render_simple_template(self):
        """Test rendering a simple template."""
        renderer = TemplateRenderer()
        result = renderer.render('Hello {{ name }}!', {'name': 'World'})
        assert result == 'Hello World!'

    def test_render_with_filter(self):
        """Test rendering with custom filters."""
        renderer = TemplateRenderer()
        dt = datetime(2026, 1, 22, 14, 30, 0, tzinfo=timezone.utc)
        result = renderer.render('{{ dt|ical_datetime }}', {'dt': dt})
        assert result == '20260122T143000Z'

    def test_render_markdown_filter(self):
        """Test rendering with markdown filter."""
        renderer = TemplateRenderer()
        result = renderer.render('{{ text|markdown }}', {'text': '**bold**'})
        assert '<strong>bold</strong>' in result

    def test_render_invalid_syntax_raises(self):
        """Test that invalid syntax raises error."""
        renderer = TemplateRenderer()
        with pytest.raises(TemplateRenderError, match="rendering failed"):
            renderer.render('{{ invalid syntax }}', {})

    def test_validate_valid_template(self):
        """Test validating a valid template."""
        renderer = TemplateRenderer()
        assert renderer.validate('Hello {{ name }}!') is True

    def test_validate_invalid_template(self):
        """Test validating an invalid template."""
        renderer = TemplateRenderer()
        with pytest.raises(TemplateRenderError, match="Invalid template syntax"):
            renderer.validate('{% if unclosed')

    def test_render_with_blocks(self):
        """Test rendering with Jinja blocks."""
        templates = {
            'base': '{% block content %}default{% endblock %}',
        }
        renderer = TemplateRenderer(templates)

        child = '{% extends "base" %}{% block content %}custom{% endblock %}'
        result = renderer.render_with_inheritance(child)
        assert result == 'custom'

    def test_build_context_minimal(self):
        """Test building minimal context."""
        from notices.models import MessageTemplate
        from notices.choices import MessageEventTypeChoices

        template = MessageTemplate(
            name='Test',
            slug='test',
            event_type=MessageEventTypeChoices.NONE,
            subject_template='S',
            body_template='B',
        )

        context = TemplateRenderer.build_context(template)

        assert 'now' in context
        assert 'netbox_url' in context
        assert context['tenant'] is None
        assert context['impacts'] == []


@pytest.mark.django_db
class TestTemplateRendererWithEvent:
    """Tests for TemplateRenderer with event context."""

    def test_build_context_with_maintenance(self, maintenance):
        """Test building context with maintenance event."""
        from notices.models import MessageTemplate
        from notices.choices import MessageEventTypeChoices

        template = MessageTemplate(
            name='Test',
            slug='test',
            event_type=MessageEventTypeChoices.MAINTENANCE,
            subject_template='S',
            body_template='B',
        )

        context = TemplateRenderer.build_context(template, event=maintenance)

        assert 'maintenance' in context
        assert context['maintenance'] == maintenance
```

**Step 2: Add maintenance fixture to conftest.py**

```python
# Add to tests/conftest.py
from django.utils import timezone
from circuits.models import Provider
from notices.models import Maintenance


@pytest.fixture
def provider():
    """Create a test provider."""
    return Provider.objects.create(
        name='Test Provider',
        slug='test-provider',
    )


@pytest.fixture
def maintenance(provider):
    """Create a test maintenance event."""
    now = timezone.now()
    return Maintenance.objects.create(
        name='MAINT-001',
        provider=provider,
        status='CONFIRMED',
        start=now,
        end=now + timezone.timedelta(hours=4),
    )
```

**Step 3: Run tests**

Run: `make test`
Expected: All tests pass

**Step 4: Commit**

```bash
git add tests/test_template_renderer.py tests/conftest.py
git commit -m "test(services): add template renderer tests

Part of #4
Closes #4"
```

---

## Phase 4: REST API (#9)

### Task 4.1: Create Serializers

**Files:**
- Create: `notices/api/serializers/messaging.py`
- Modify: `notices/api/serializers/__init__.py`

**Step 1: Create messaging serializers**

```python
# notices/api/serializers/messaging.py
import yaml
from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType

from netbox.api.serializers import NetBoxModelSerializer, WritableNestedSerializer
from tenancy.api.serializers import NestedContactSerializer, NestedContactRoleSerializer

from notices.models import MessageTemplate, TemplateScope, PreparedMessage
from notices.choices import PreparedMessageStatusChoices
from notices.validators import PreparedMessageStateMachine

__all__ = (
    'MessageTemplateSerializer',
    'NestedMessageTemplateSerializer',
    'TemplateScopeSerializer',
    'PreparedMessageSerializer',
)


class TemplateScopeSerializer(serializers.ModelSerializer):
    """Serializer for TemplateScope."""

    content_type = serializers.SlugRelatedField(
        queryset=ContentType.objects.all(),
        slug_field='model',
    )
    object_repr = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = TemplateScope
        fields = [
            'id', 'content_type', 'object_id', 'object_repr',
            'event_type', 'event_status', 'weight',
        ]

    def get_object_repr(self, obj):
        """Return string representation of the scoped object."""
        if obj.object:
            return str(obj.object)
        return f'All {obj.content_type.model}s'


class MessageTemplateSerializer(NetBoxModelSerializer):
    """Serializer for MessageTemplate."""

    url = serializers.HyperlinkedIdentityField(
        view_name='plugins-api:notices-api:messagetemplate-detail',
    )
    scopes = TemplateScopeSerializer(many=True, required=False)
    contact_roles = NestedContactRoleSerializer(many=True, required=False)
    extends = serializers.PrimaryKeyRelatedField(
        queryset=MessageTemplate.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = MessageTemplate
        fields = [
            'id', 'url', 'display', 'name', 'slug', 'description',
            'event_type', 'granularity',
            'subject_template', 'body_template', 'body_format',
            'css_template', 'headers_template',
            'include_ical', 'ical_template',
            'contact_roles', 'contact_priorities',
            'is_base_template', 'extends', 'weight',
            'scopes',
            'tags', 'custom_fields', 'created', 'last_updated',
        ]

    def validate_headers_template(self, value):
        """Accept YAML input and convert to dict."""
        if isinstance(value, str):
            try:
                return yaml.safe_load(value) or {}
            except yaml.YAMLError as e:
                raise serializers.ValidationError(f"Invalid YAML: {e}")
        return value

    def create(self, validated_data):
        scopes_data = validated_data.pop('scopes', [])
        contact_roles = validated_data.pop('contact_roles', [])

        instance = super().create(validated_data)

        # Create scopes
        for scope_data in scopes_data:
            TemplateScope.objects.create(template=instance, **scope_data)

        # Set contact roles
        if contact_roles:
            instance.contact_roles.set(contact_roles)

        return instance

    def update(self, instance, validated_data):
        scopes_data = validated_data.pop('scopes', None)
        contact_roles = validated_data.pop('contact_roles', None)

        instance = super().update(instance, validated_data)

        # Update scopes if provided
        if scopes_data is not None:
            instance.scopes.all().delete()
            for scope_data in scopes_data:
                TemplateScope.objects.create(template=instance, **scope_data)

        # Update contact roles if provided
        if contact_roles is not None:
            instance.contact_roles.set(contact_roles)

        return instance


class NestedMessageTemplateSerializer(WritableNestedSerializer):
    """Nested serializer for MessageTemplate."""

    url = serializers.HyperlinkedIdentityField(
        view_name='plugins-api:notices-api:messagetemplate-detail',
    )

    class Meta:
        model = MessageTemplate
        fields = ['id', 'url', 'display', 'name', 'slug']


class PreparedMessageSerializer(NetBoxModelSerializer):
    """Serializer for PreparedMessage."""

    url = serializers.HyperlinkedIdentityField(
        view_name='plugins-api:notices-api:preparedmessage-detail',
    )
    template = NestedMessageTemplateSerializer(read_only=True)
    template_id = serializers.PrimaryKeyRelatedField(
        queryset=MessageTemplate.objects.all(),
        source='template',
        write_only=True,
    )
    contacts = NestedContactSerializer(many=True, read_only=True)
    contact_ids = serializers.PrimaryKeyRelatedField(
        queryset='tenancy.Contact',
        many=True,
        source='contacts',
        write_only=True,
        required=False,
    )
    recipients = serializers.JSONField(read_only=True)

    # Status change message (for journal entry)
    message = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = PreparedMessage
        fields = [
            'id', 'url', 'display',
            'template', 'template_id',
            'event_content_type', 'event_id',
            'status', 'message',
            'contacts', 'contact_ids', 'recipients',
            'subject', 'body_text', 'body_html', 'headers', 'css', 'ical_content',
            'approved_by', 'approved_at',
            'sent_at', 'delivered_at', 'viewed_at',
            'tags', 'custom_fields', 'created', 'last_updated',
        ]
        read_only_fields = [
            'recipients', 'approved_by', 'approved_at',
        ]

    def validate(self, data):
        """Validate status transitions using state machine."""
        if self.instance and 'status' in data:
            new_status = data['status']
            if new_status != self.instance.status:
                sm = PreparedMessageStateMachine(self.instance)
                if not sm.can_transition_to(new_status):
                    valid = sm.get_valid_transitions()
                    raise serializers.ValidationError({
                        'status': f"Cannot transition from '{self.instance.status}' to '{new_status}'. "
                                  f"Valid: {', '.join(valid) or 'none'}"
                    })
        return data

    def update(self, instance, validated_data):
        message_text = validated_data.pop('message', None)
        new_status = validated_data.get('status')

        # Handle status transition with state machine
        if new_status and new_status != instance.status:
            request = self.context.get('request')
            user = request.user if request else None

            sm = PreparedMessageStateMachine(instance, user=user)
            sm.transition_to(new_status, message_text=message_text)

            # Remove status from validated_data since state machine handled it
            validated_data.pop('status', None)

        return super().update(instance, validated_data)
```

**Step 2: Update serializers __init__.py**

```python
# Add to notices/api/serializers/__init__.py
from .messaging import *
```

**Step 3: Run linting**

Run: `make lint`
Expected: PASS

**Step 4: Commit**

```bash
git add notices/api/serializers/
git commit -m "feat(api): add messaging serializers

Part of #9"
```

---

### Task 4.2: Create API Views

**Files:**
- Create: `notices/api/views/messaging.py`
- Modify: `notices/api/views/__init__.py`

**Step 1: Create messaging views**

```python
# notices/api/views/messaging.py
from netbox.api.viewsets import NetBoxModelViewSet

from notices.models import MessageTemplate, PreparedMessage
from notices.api.serializers import MessageTemplateSerializer, PreparedMessageSerializer
from notices.filtersets import MessageTemplateFilterSet, PreparedMessageFilterSet

__all__ = (
    'MessageTemplateViewSet',
    'PreparedMessageViewSet',
)


class MessageTemplateViewSet(NetBoxModelViewSet):
    """API viewset for MessageTemplate."""

    queryset = MessageTemplate.objects.prefetch_related(
        'scopes',
        'contact_roles',
        'tags',
    )
    serializer_class = MessageTemplateSerializer
    filterset_class = MessageTemplateFilterSet


class PreparedMessageViewSet(NetBoxModelViewSet):
    """API viewset for PreparedMessage."""

    queryset = PreparedMessage.objects.prefetch_related(
        'template',
        'contacts',
        'tags',
    ).select_related(
        'approved_by',
    )
    serializer_class = PreparedMessageSerializer
    filterset_class = PreparedMessageFilterSet
```

**Step 2: Update views __init__.py**

```python
# Add to notices/api/views/__init__.py
from .messaging import *
```

**Step 3: Run linting**

Run: `make lint`
Expected: PASS

**Step 4: Commit**

```bash
git add notices/api/views/
git commit -m "feat(api): add messaging viewsets

Part of #9"
```

---

### Task 4.3: Create Filtersets

**Files:**
- Modify: `notices/filtersets.py`

**Step 1: Add filtersets for messaging models**

```python
# Add to notices/filtersets.py
import django_filters
from django.db.models import Q

from netbox.filtersets import NetBoxModelFilterSet

from notices.models import MessageTemplate, PreparedMessage
from notices.choices import (
    MessageEventTypeChoices,
    MessageGranularityChoices,
    PreparedMessageStatusChoices,
)


class MessageTemplateFilterSet(NetBoxModelFilterSet):
    """Filterset for MessageTemplate."""

    event_type = django_filters.MultipleChoiceFilter(
        choices=MessageEventTypeChoices,
    )
    granularity = django_filters.MultipleChoiceFilter(
        choices=MessageGranularityChoices,
    )
    is_base_template = django_filters.BooleanFilter()
    q = django_filters.CharFilter(
        method='search',
        label='Search',
    )

    class Meta:
        model = MessageTemplate
        fields = ['id', 'name', 'slug', 'event_type', 'granularity', 'is_base_template']

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value) |
            Q(slug__icontains=value) |
            Q(description__icontains=value)
        )


class PreparedMessageFilterSet(NetBoxModelFilterSet):
    """Filterset for PreparedMessage."""

    status = django_filters.MultipleChoiceFilter(
        choices=PreparedMessageStatusChoices,
    )
    template_id = django_filters.ModelMultipleChoiceFilter(
        queryset=MessageTemplate.objects.all(),
        field_name='template',
    )
    q = django_filters.CharFilter(
        method='search',
        label='Search',
    )

    class Meta:
        model = PreparedMessage
        fields = ['id', 'status', 'template_id']

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(subject__icontains=value) |
            Q(body_text__icontains=value)
        )
```

**Step 2: Run linting**

Run: `make lint`
Expected: PASS

**Step 3: Commit**

```bash
git add notices/filtersets.py
git commit -m "feat(api): add messaging filtersets

Part of #9"
```

---

### Task 4.4: Register API URLs

**Files:**
- Modify: `notices/api/urls.py`

**Step 1: Add URL routes**

```python
# Update notices/api/urls.py
from netbox.api.routers import NetBoxRouter

from notices.api.views import (
    # ... existing views ...
    MessageTemplateViewSet,
    PreparedMessageViewSet,
)

router = NetBoxRouter()
# ... existing routes ...
router.register('message-templates', MessageTemplateViewSet)
router.register('prepared-messages', PreparedMessageViewSet)

urlpatterns = router.urls
```

**Step 2: Run linting**

Run: `make lint`
Expected: PASS

**Step 3: Commit**

```bash
git add notices/api/urls.py
git commit -m "feat(api): register messaging API routes

Part of #9
Closes #9"
```

---

## Phase 5: Remaining Implementation

The remaining tasks follow the same pattern. Here's a summary of what needs to be implemented:

### Phase 5.1: Recipient Discovery (#5)
- Create `notices/services/recipient_discovery.py`
- Implement tenant resolution from impacts
- Query ContactAssignments by role/priority
- Write tests in `tests/test_recipient_discovery.py`

### Phase 5.2: Template Matching (#6)
- Create `notices/services/template_matching.py`
- Implement scope matching algorithm
- Implement field-level merge
- Implement block-level (Jinja) inheritance
- Write tests in `tests/test_template_matching.py`

### Phase 5.3: iCal Generation (#8)
- Create `notices/services/ical_generator.py`
- Generate BCOP-compliant iCal from templates
- Add validation for required BCOP fields
- Write tests in `tests/test_ical_generator.py`

### Phase 5.4: Admin UI (#10)
- Create views in `notices/views/messaging.py`
- Create forms in `notices/forms/messaging.py`
- Create tables in `notices/tables/messaging.py`
- Create templates in `notices/templates/notices/`
- Update navigation in `notices/navigation.py`
- Write view tests

### Phase 5.5: Documentation (#11)
- Create `docs/outgoing-notifications.md`
- Document template creation
- Document recipient discovery
- Document iCal examples
- Document API integration

---

## Execution Checklist

- [ ] Phase 1: Data Models (#3)
  - [ ] Task 1.1: Add Choices
  - [ ] Task 1.2: Create MessageTemplate Model
  - [ ] Task 1.3: Create TemplateScope Model
  - [ ] Task 1.4: Create PreparedMessage Model
  - [ ] Task 1.5: Create and Run Migrations
  - [ ] Task 1.6: Write Model Tests

- [ ] Phase 2: State Machine (#7)
  - [ ] Task 2.1: Create State Machine Validator
  - [ ] Task 2.2: Write State Machine Tests

- [ ] Phase 3: Template Engine (#4)
  - [ ] Task 3.1: Create Template Rendering Service
  - [ ] Task 3.2: Write Template Renderer Tests

- [ ] Phase 4: REST API (#9)
  - [ ] Task 4.1: Create Serializers
  - [ ] Task 4.2: Create API Views
  - [ ] Task 4.3: Create Filtersets
  - [ ] Task 4.4: Register API URLs

- [ ] Phase 5: Remaining Implementation
  - [ ] Phase 5.1: Recipient Discovery (#5)
  - [ ] Phase 5.2: Template Matching (#6)
  - [ ] Phase 5.3: iCal Generation (#8)
  - [ ] Phase 5.4: Admin UI (#10)
  - [ ] Phase 5.5: Documentation (#11)
