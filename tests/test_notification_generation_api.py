"""Tests for the notification generation and reset API actions."""

import pytest
from core.models import ObjectType
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from users.constants import TOKEN_PREFIX
from users.models import ObjectPermission, Token

from notices.models import NotificationTemplate, PreparedNotification

User = get_user_model()


@pytest.fixture
def kind():
    return NotificationTemplate.objects.create(
        name="NOC",
        slug="noc",
        event_type="maintenance",
        granularity="per_event",
        subject_template="S",
        body_template="B",
        body_format="text",
    )


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def admin_api():
    return _client(User.objects.create_superuser(username="api-admin", password="x", email="x@example.com"))


def _url(event):
    return f"/api/plugins/notices/maintenance/{event.pk}/generate-notifications/"


def _grant(user, name, actions, *models):
    perm = ObjectPermission.objects.create(name=name, actions=actions)
    perm.object_types.add(*[ObjectType.objects.get(app_label="notices", model=m) for m in models])
    perm.users.add(user)


@pytest.mark.django_db
class TestGenerateAction:
    def test_dry_run_returns_plan_without_writing(self, admin_api, maintenance_with_two_tenants, kind):
        event, *_ = maintenance_with_two_tenants
        response = admin_api.post(_url(event), {"dry_run": True}, format="json")
        assert response.status_code == 200
        assert [i["action"] for i in response.data["items"]] == ["create"]
        assert PreparedNotification.objects.count() == 0

    def test_apply_returns_saved_ids(self, admin_api, maintenance_with_two_tenants, kind):
        event, *_ = maintenance_with_two_tenants
        response = admin_api.post(_url(event), {}, format="json")
        assert response.data["counts"] == {"create": 1}
        assert response.data["items"][0]["notification"] == PreparedNotification.objects.get().pk

    def test_duplicate_template_ids_generate_once(self, admin_api, maintenance_with_two_tenants, kind):
        event, *_ = maintenance_with_two_tenants
        response = admin_api.post(_url(event), {"templates": [kind.pk, kind.pk]}, format="json")
        assert response.data["counts"] == {"create": 1}
        assert PreparedNotification.objects.count() == 1

    def test_rejects_template_that_is_not_a_kind_for_event(self, admin_api, maintenance_with_two_tenants, kind):
        event, *_ = maintenance_with_two_tenants
        outage_kind = NotificationTemplate.objects.create(
            name="O", slug="o", event_type="outage", subject_template="S", body_template="B"
        )
        response = admin_api.post(_url(event), {"templates": [outage_kind.pk]}, format="json")
        assert response.status_code == 400

    def test_needs_notification_permissions_not_event_add(self, maintenance_with_two_tenants, kind):
        event, *_ = maintenance_with_two_tenants
        user = User.objects.create_user(username="gen", password="x")
        _grant(user, "gen", ["view", "add", "change", "delete"], "preparednotification")
        _grant(user, "view-maint", ["view"], "maintenance")
        assert _client(user).post(_url(event), {"dry_run": True}, format="json").status_code == 200

    def test_without_notification_permissions_is_forbidden(self, maintenance_with_two_tenants, kind):
        event, *_ = maintenance_with_two_tenants
        user = User.objects.create_user(username="viewer", password="x")
        _grant(user, "view-maint2", ["view"], "maintenance")
        assert _client(user).post(_url(event), {"dry_run": True}, format="json").status_code == 403

    @pytest.mark.parametrize(("write_enabled", "status"), [(False, 403), (True, 200)])
    def test_token_write_ability_is_enforced(self, maintenance_with_two_tenants, kind, write_enabled, status):
        event, *_ = maintenance_with_two_tenants
        user = User.objects.create_superuser(username="tok", password="x", email="tok@example.com")
        token = Token.objects.create(user=user, write_enabled=write_enabled)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {TOKEN_PREFIX}{token.key}.{token.token}")
        assert client.post(_url(event), {"dry_run": True}, format="json").status_code == status


@pytest.mark.django_db
class TestResetAction:
    def test_reset_returns_unmodified_notification(self, admin_api, maintenance_with_two_tenants, kind):
        event, *_ = maintenance_with_two_tenants
        admin_api.post(_url(event), {}, format="json")
        n = PreparedNotification.objects.get()
        n.body_text = "edited"
        n.save()
        response = admin_api.post(f"/api/plugins/notices/prepared-notifications/{n.pk}/reset/")
        assert response.status_code == 200
        assert response.data["modified"] is False and response.data["body_text"] == "B"

    def test_reset_non_draft_is_400(self, admin_api, maintenance_with_two_tenants, kind):
        event, *_ = maintenance_with_two_tenants
        admin_api.post(_url(event), {}, format="json")
        PreparedNotification.objects.update(status="sent")
        n = PreparedNotification.objects.get()
        assert admin_api.post(f"/api/plugins/notices/prepared-notifications/{n.pk}/reset/").status_code == 400
