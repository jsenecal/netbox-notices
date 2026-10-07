"""Tests for the notification generation, approve and reset views."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from notices.filtersets import PreparedNotificationFilterSet
from notices.models import PreparedNotification
from notices.services.notification_generation import NotificationGenerator

User = get_user_model()


@pytest.fixture
def kind(make_template):
    return make_template("noc", name="NOC", subject_template="S {{ maintenance.name }}")


@pytest.fixture
def admin_client(client):
    user = User.objects.create_superuser(username="admin2", password="x", email="a@example.com")
    client.force_login(user)
    return client


@pytest.mark.django_db
class TestGenerateView:
    def test_requires_notification_permissions(self, client, maintenance_with_two_tenants):
        event, *_ = maintenance_with_two_tenants
        user = User.objects.create_user(username="viewer", password="x")
        client.force_login(user)
        url = reverse("plugins:notices:maintenance_generate_notifications", args=[event.pk])
        assert client.post(url).status_code == 403

    def test_preview_writes_nothing(self, admin_client, maintenance_with_two_tenants, kind):
        event, *_ = maintenance_with_two_tenants
        url = reverse("plugins:notices:maintenance_generate_notifications", args=[event.pk])
        response = admin_client.get(url, {"templates": [kind.pk]})
        assert [i.action for i in response.context["plan"]] == ["create"]
        assert PreparedNotification.objects.count() == 0

    def test_post_applies_selected_kinds(self, admin_client, maintenance_with_two_tenants, kind, make_template):
        event, *_ = maintenance_with_two_tenants
        make_template("other", name="Other", subject_template="O")
        url = reverse("plugins:notices:maintenance_generate_notifications", args=[event.pk])
        admin_client.post(url, {"templates": [kind.pk, kind.pk]})
        assert list(PreparedNotification.objects.values_list("template__slug", flat=True)) == ["noc"]


@pytest.mark.django_db
class TestApproveAndReset:
    def _generated(self, event):
        NotificationGenerator(event).generate()
        return PreparedNotification.objects.get()

    def test_approve_goes_through_state_machine(self, admin_client, maintenance_with_two_tenants, kind):
        event, *_ = maintenance_with_two_tenants
        n = self._generated(event)
        admin_client.post(reverse("plugins:notices:preparednotification_approve", args=[n.pk]))
        n.refresh_from_db()
        assert n.status == "ready" and n.approved_by is not None and n.recipients

    def test_approve_respects_post_change_permission_constraints(
        self, client, maintenance_with_two_tenants, kind, grant_permission
    ):
        """A drafter whose change permission only covers drafts cannot approve."""
        event, *_ = maintenance_with_two_tenants
        n = self._generated(event)
        user = User.objects.create_user(username="drafter", password="x")
        grant_permission(user, ["view", "change"], "preparednotification", constraints={"status": "draft"})
        client.force_login(user)
        client.post(reverse("plugins:notices:preparednotification_approve", args=[n.pk]))
        n.refresh_from_db()
        assert n.status == "draft" and n.approved_by is None

    def test_reset_restores_template_content(self, admin_client, maintenance_with_two_tenants, kind):
        event, *_ = maintenance_with_two_tenants
        n = self._generated(event)
        n.body_text = "edited"
        n.save()
        admin_client.post(reverse("plugins:notices:preparednotification_reset", args=[n.pk]))
        n.refresh_from_db()
        assert n.body_text == "B" and not n.is_modified

    def test_return_url_must_be_local(self, admin_client, maintenance_with_two_tenants, kind):
        event, *_ = maintenance_with_two_tenants
        n = self._generated(event)
        url = reverse("plugins:notices:preparednotification_approve", args=[n.pk])
        response = admin_client.post(url, {"return_url": "https://evil.example.com/"})
        assert response.url == n.get_absolute_url()


@pytest.mark.django_db
class TestFilterSet:
    def test_modified_filter(self, maintenance_with_two_tenants, kind):
        event, *_ = maintenance_with_two_tenants
        NotificationGenerator(event).generate()
        n = PreparedNotification.objects.get()
        qs = PreparedNotification.objects.all()
        assert PreparedNotificationFilterSet({"modified": True}, qs).qs.count() == 0
        n.subject = "edited"
        n.save()
        assert list(PreparedNotificationFilterSet({"modified": True}, qs).qs) == [n]
        assert list(PreparedNotificationFilterSet({"event_type": "maintenance", "event_id": event.pk}, qs).qs) == [n]
