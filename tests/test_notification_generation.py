"""Tests for NotificationGenerator."""

import pytest
from django.contrib.contenttypes.models import ContentType

from notices.models import NotificationTemplate, PreparedNotification, TemplateScope
from notices.services.notification_generation import NotificationGenerator


def _kind(slug, **kw):
    defaults = {
        "name": slug,
        "slug": slug,
        "event_type": "maintenance",
        "granularity": "per_tenant",
        "subject_template": "{{ maintenance.name }} for {{ tenant.name if tenant else 'all' }}",
        "body_template": "Body {{ tenant_impacts|length }}",
        "body_format": "text",
    }
    defaults.update(kw)
    return NotificationTemplate.objects.create(**defaults)


def _actions(plan):
    return sorted(item.action for item in plan)


@pytest.mark.django_db
class TestPlan:
    def test_one_draft_per_tenant(self, maintenance_with_two_tenants):
        event, tenant_a, tenant_b = maintenance_with_two_tenants
        _kind("customer")
        plan = NotificationGenerator(event).plan()
        assert _actions(plan) == ["create", "create"]
        assert {item.tenant for item in plan} == {tenant_a, tenant_b}
        assert plan[0].content["subject"].startswith("MAINT-001 for Tenant")
        assert PreparedNotification.objects.count() == 0  # plan has no side effects

    def test_each_kind_generates_independently(self, maintenance_with_two_tenants):
        event, *_ = maintenance_with_two_tenants
        _kind("customer")
        _kind("noc", granularity="per_event")
        assert len(NotificationGenerator(event).plan()) == 3

    def test_tenant_override_replaces_root_for_that_tenant(self, maintenance_with_two_tenants):
        event, tenant_a, _ = maintenance_with_two_tenants
        root = _kind("customer")
        acme = _kind("customer-a", extends=root, subject_template="Special")
        TemplateScope.objects.create(
            template=acme, content_type=ContentType.objects.get_for_model(tenant_a), object_id=tenant_a.pk
        )
        plan = {item.tenant: item for item in NotificationGenerator(event).plan()}
        assert plan[tenant_a].template == acme and plan[tenant_a].content["subject"] == "Special"
        assert plan[tenant_a].root_template == root

    def test_group_without_contacts_is_skipped(self, maintenance_with_two_tenants):
        event, *_ = maintenance_with_two_tenants
        _kind("customer", contact_priorities=["tertiary"])
        assert _actions(NotificationGenerator(event).plan()) == ["skip", "skip"]

    def test_render_error_only_marks_its_own_kind(self, maintenance_with_two_tenants):
        event, *_ = maintenance_with_two_tenants
        _kind("good", granularity="per_event")
        _kind("bad", granularity="per_event", body_template="{% if %}")
        plan = {item.root_template.slug: item for item in NotificationGenerator(event).plan()}
        assert plan["good"].action == "create"
        assert plan["bad"].action == "error" and plan["bad"].error

    def test_long_subject_is_truncated(self, maintenance_with_two_tenants):
        event, *_ = maintenance_with_two_tenants
        _kind("long", granularity="per_event", subject_template="x" * 400)
        [item] = NotificationGenerator(event).plan()
        assert len(item.content["subject"]) == 255


@pytest.mark.django_db
class TestRegeneration:
    def _generate(self, event, **kw):
        gen = NotificationGenerator(event, **kw)
        return gen.apply(gen.plan())

    def test_untouched_draft_is_updated_in_place(self, maintenance_with_two_tenants):
        event, *_ = maintenance_with_two_tenants
        kind = _kind("noc", granularity="per_event")
        self._generate(event)
        kind.subject_template = "New subject"
        kind.save()
        result = self._generate(event)
        assert result.counts == {"update": 1}
        assert PreparedNotification.objects.get().subject == "New subject"

    def test_modified_draft_is_kept(self, maintenance_with_two_tenants):
        event, *_ = maintenance_with_two_tenants
        _kind("noc", granularity="per_event")
        self._generate(event)
        n = PreparedNotification.objects.get()
        n.body_text = "hand edit"
        n.save()
        assert self._generate(event).counts == {"keep": 1}
        assert PreparedNotification.objects.get().body_text == "hand edit"

    def test_sent_notification_kept_and_new_draft_created(self, maintenance_with_two_tenants):
        event, *_ = maintenance_with_two_tenants
        _kind("noc", granularity="per_event", include_ical=True, ical_template="SEQ:{{ message_sequence }}")
        self._generate(event)
        PreparedNotification.objects.update(status="sent")
        result = self._generate(event)
        assert result.counts == {"create": 1}
        new = PreparedNotification.objects.get(status="draft")
        assert new.ical_content == "SEQ:2"

    def test_stale_untouched_draft_is_deleted(self, maintenance_with_two_tenants):
        event, tenant_a, _ = maintenance_with_two_tenants
        _kind("customer")
        self._generate(event)
        event.impacts.filter(target_object_id__in=tenant_a.circuits.values("pk")).delete()
        assert self._generate(event).counts == {"update": 1, "delete": 1}

    def test_unselected_kind_drafts_survive(self, maintenance_with_two_tenants):
        event, *_ = maintenance_with_two_tenants
        a = _kind("a", granularity="per_event")
        _kind("b", granularity="per_event")
        self._generate(event)
        self._generate(event, templates=[a])
        assert PreparedNotification.objects.count() == 2

    def test_apply_sets_group_and_baseline(self, maintenance_with_two_tenants):
        event, tenant_a, _ = maintenance_with_two_tenants
        _kind("customer")
        self._generate(event)
        n = PreparedNotification.objects.get(tenant=tenant_a)
        assert n.event == event and not n.is_modified and n.rendered_hash
        assert list(n.contacts.values_list("email", flat=True)) == ["c1@example.com"]

    def test_hand_created_draft_is_untouched_and_does_not_suppress_creation(self, maintenance_with_two_tenants):
        event, *_ = maintenance_with_two_tenants
        kind = _kind("noc", granularity="per_event")
        manual = PreparedNotification.objects.create(
            template=kind, event=event, subject="mine", body_text="mine", status="draft"
        )
        result = self._generate(event)
        assert result.counts == {"create": 1}
        manual.refresh_from_db()
        assert manual.subject == "mine" and manual.body_text == "mine"
        assert PreparedNotification.objects.count() == 2

    def test_hand_created_tenant_draft_is_not_deleted_as_stale(self, maintenance_with_two_tenants):
        event, tenant_a, _ = maintenance_with_two_tenants
        kind = _kind("customer")
        manual = PreparedNotification.objects.create(
            template=kind, event=event, tenant=tenant_a, subject="mine", body_text="mine", status="draft"
        )
        event.impacts.all().delete()
        result = self._generate(event)
        assert "delete" not in result.counts
        assert PreparedNotification.objects.filter(pk=manual.pk).exists()


@pytest.mark.django_db
class TestReset:
    def test_reset_discards_edits(self, maintenance_with_two_tenants):
        event, *_ = maintenance_with_two_tenants
        _kind("noc", granularity="per_event")
        gen = NotificationGenerator(event)
        gen.apply(gen.plan())
        n = PreparedNotification.objects.get()
        original = n.body_text
        n.body_text = "edited"
        n.save()
        n = NotificationGenerator(event).reset(n)
        assert n.body_text == original and not n.is_modified

    def test_reset_rejects_non_draft(self, maintenance_with_two_tenants):
        event, *_ = maintenance_with_two_tenants
        _kind("noc", granularity="per_event")
        gen = NotificationGenerator(event)
        gen.apply(gen.plan())
        n = PreparedNotification.objects.get()
        n.status = "ready"
        with pytest.raises(ValueError):
            NotificationGenerator(event).reset(n)
