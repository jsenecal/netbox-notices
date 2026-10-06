# tests/test_messaging_models.py
import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError

from notices.choices import (
    BodyFormatChoices,
    MessageEventTypeChoices,
    MessageGranularityChoices,
    PreparedNotificationStatusChoices,
)
from notices.models import NotificationTemplate, PreparedNotification, TemplateScope


@pytest.mark.django_db
class TestNotificationTemplate:
    """Tests for NotificationTemplate model."""

    def test_create_minimal_template(self):
        """Test creating a template with minimal required fields."""
        template = NotificationTemplate.objects.create(
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
        template = NotificationTemplate.objects.create(
            name="My Template",
            slug="my-template",
            event_type=MessageEventTypeChoices.BOTH,
            subject_template="Subject",
            body_template="Body",
        )
        assert str(template) == "My Template"

    def test_template_inheritance(self):
        """Test template extends relationship."""
        base = NotificationTemplate.objects.create(
            name="Base Template",
            slug="base-template",
            event_type=MessageEventTypeChoices.MAINTENANCE,
            subject_template="Base Subject",
            body_template="{% block content %}{% endblock %}",
            is_base_template=True,
        )
        child = NotificationTemplate.objects.create(
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
        template = NotificationTemplate.objects.create(
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
        template = NotificationTemplate.objects.create(
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
class TestPreparedNotification:
    """Tests for PreparedNotification model."""

    def test_create_prepared_notification(self):
        """Test creating a prepared notification."""
        template = NotificationTemplate.objects.create(
            name="Test Template",
            slug="test-template",
            event_type=MessageEventTypeChoices.NONE,
            subject_template="Subject",
            body_template="Body",
        )
        notification = PreparedNotification.objects.create(
            template=template,
            subject="Test Subject Line",
            body_text="Test body content",
        )
        assert notification.pk is not None
        assert notification.status == PreparedNotificationStatusChoices.DRAFT
        assert notification.approved_by is None

    def test_prepared_notification_str_short(self):
        """Test notification string representation for short subjects."""
        template = NotificationTemplate.objects.create(
            name="Test",
            slug="test",
            event_type=MessageEventTypeChoices.NONE,
            subject_template="S",
            body_template="B",
        )
        notification = PreparedNotification.objects.create(
            template=template,
            subject="Short Subject",
            body_text="Body",
        )
        assert str(notification) == "Short Subject"

    def test_prepared_notification_str_truncated(self):
        """Test notification string representation for long subjects."""
        template = NotificationTemplate.objects.create(
            name="Test",
            slug="test2",
            event_type=MessageEventTypeChoices.NONE,
            subject_template="S",
            body_template="B",
        )
        long_subject = "A" * 100
        notification = PreparedNotification.objects.create(
            template=template,
            subject=long_subject,
            body_text="Body",
        )
        assert str(notification) == "A" * 50 + "..."


@pytest.mark.django_db
class TestNotificationTemplateClean:
    def _tpl(self, slug, **kw):
        return NotificationTemplate.objects.create(
            name=slug, slug=slug, event_type="maintenance", subject_template="s", body_template="b", **kw
        )

    def test_self_extends_rejected(self):
        t = self._tpl("a")
        t.extends = t
        with pytest.raises(ValidationError, match="cycle"):
            t.clean()

    def test_two_template_cycle_rejected(self):
        a = self._tpl("a")
        b = self._tpl("b", extends=a)
        a.extends = b
        with pytest.raises(ValidationError, match="cycle"):
            a.clean()

    def test_override_granularity_must_match_parent(self):
        parent = self._tpl("p", granularity="per_tenant")
        child = NotificationTemplate(
            name="c",
            slug="c",
            event_type="maintenance",
            subject_template="s",
            body_template="b",
            extends=parent,
            granularity="per_event",
        )
        with pytest.raises(ValidationError, match="granularity"):
            child.clean()

    def test_child_of_base_template_may_use_any_granularity(self):
        base = self._tpl("base", is_base_template=True, granularity="per_tenant")
        child = NotificationTemplate(
            name="c",
            slug="c",
            event_type="maintenance",
            subject_template="s",
            body_template="b",
            extends=base,
            granularity="per_event",
        )
        child.clean()

    def test_root_kind_walks_overrides_only(self):
        base = self._tpl("base", is_base_template=True)
        root = self._tpl("root", extends=base)
        mid = self._tpl("mid", extends=root)
        leaf = self._tpl("leaf", extends=mid)
        assert leaf.root_kind == root
        assert root.root_kind == root
        assert leaf.is_override and not root.is_override


@pytest.mark.django_db
class TestPreparedNotificationModified:
    def _make(self, notification_template, **kw):
        defaults = {"template": notification_template, "subject": "S", "body_text": "B", **kw}
        return PreparedNotification.objects.create(**defaults)

    def test_hand_created_is_never_modified(self, notification_template):
        n = self._make(notification_template)
        assert not n.is_modified
        assert not PreparedNotification.objects.modified().filter(pk=n.pk).exists()

    def test_edit_after_render_is_modified(self, notification_template):
        n = self._make(notification_template)
        n.mark_rendered()
        assert not n.is_modified
        n.body_text = "edited"
        n.save()
        assert n.is_modified
        assert PreparedNotification.objects.modified().filter(pk=n.pk).exists()

    def test_header_key_order_is_not_a_modification(self, notification_template):
        n = self._make(notification_template, headers={"a": "1", "b": "2"})
        n.mark_rendered()
        n.headers = {"b": "2", "a": "1"}
        n.save()
        assert not n.is_modified

    def test_objectchange_relates_to_event(self, notification_template, maintenance):
        n = self._make(notification_template, event=maintenance)
        assert n.to_objectchange("update").related_object == maintenance
