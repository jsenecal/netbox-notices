# tests/test_messaging_models.py
import pytest
from django.contrib.contenttypes.models import ContentType

from notices.choices import (
    BodyFormatChoices,
    MessageEventTypeChoices,
    MessageGranularityChoices,
    PreparedMessageStatusChoices,
)
from notices.models import MessageTemplate, PreparedMessage, TemplateScope


@pytest.mark.django_db
class TestMessageTemplate:
    """Tests for MessageTemplate model."""

    def test_create_minimal_template(self):
        """Test creating a template with minimal required fields."""
        template = MessageTemplate.objects.create(
            name="Test Template",
            slug="test-template",
            event_type=MessageEventTypeChoices.MAINTENANCE,
            subject_template="Test Subject",
            body_template="Test Body",
        )
        assert template.pk is not None
        assert template.name == "Test Template"
        assert template.granularity == MessageGranularityChoices.PER_TENANT
        assert template.body_format == BodyFormatChoices.MARKDOWN

    def test_template_str(self):
        """Test template string representation."""
        template = MessageTemplate.objects.create(
            name="My Template",
            slug="my-template",
            event_type=MessageEventTypeChoices.BOTH,
            subject_template="Subject",
            body_template="Body",
        )
        assert str(template) == "My Template"

    def test_template_inheritance(self):
        """Test template extends relationship."""
        base = MessageTemplate.objects.create(
            name="Base Template",
            slug="base-template",
            event_type=MessageEventTypeChoices.MAINTENANCE,
            subject_template="Base Subject",
            body_template="{% block content %}{% endblock %}",
            is_base_template=True,
        )
        child = MessageTemplate.objects.create(
            name="Child Template",
            slug="child-template",
            event_type=MessageEventTypeChoices.MAINTENANCE,
            subject_template="Child Subject",
            body_template="{% block content %}Child Content{% endblock %}",
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
            name="Scoped Template",
            slug="scoped-template",
            event_type=MessageEventTypeChoices.MAINTENANCE,
            subject_template="Subject",
            body_template="Body",
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
            name="Type Scoped Template",
            slug="type-scoped-template",
            event_type=MessageEventTypeChoices.OUTAGE,
            subject_template="Subject",
            body_template="Body",
        )
        content_type = ContentType.objects.get_for_model(tenant)
        scope = TemplateScope.objects.create(
            template=template,
            content_type=content_type,
            object_id=None,  # All tenants
        )
        assert scope.object_id is None
        assert "all tenants" in str(scope).lower()


@pytest.mark.django_db
class TestPreparedMessage:
    """Tests for PreparedMessage model."""

    def test_create_prepared_message(self):
        """Test creating a prepared message."""
        template = MessageTemplate.objects.create(
            name="Test Template",
            slug="test-template",
            event_type=MessageEventTypeChoices.NONE,
            subject_template="Subject",
            body_template="Body",
        )
        message = PreparedMessage.objects.create(
            template=template,
            subject="Test Subject Line",
            body_text="Test body content",
        )
        assert message.pk is not None
        assert message.status == PreparedMessageStatusChoices.DRAFT
        assert message.approved_by is None

    def test_prepared_message_str_short(self):
        """Test message string representation for short subjects."""
        template = MessageTemplate.objects.create(
            name="Test",
            slug="test",
            event_type=MessageEventTypeChoices.NONE,
            subject_template="S",
            body_template="B",
        )
        message = PreparedMessage.objects.create(
            template=template,
            subject="Short Subject",
            body_text="Body",
        )
        assert str(message) == "Short Subject"

    def test_prepared_message_str_truncated(self):
        """Test message string representation for long subjects."""
        template = MessageTemplate.objects.create(
            name="Test",
            slug="test2",
            event_type=MessageEventTypeChoices.NONE,
            subject_template="S",
            body_template="B",
        )
        long_subject = "A" * 100
        message = PreparedMessage.objects.create(
            template=template,
            subject=long_subject,
            body_text="Body",
        )
        assert str(message) == "A" * 50 + "..."
