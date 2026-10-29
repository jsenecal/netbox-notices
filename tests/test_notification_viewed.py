"""Tests for recording when a prepared notification was first viewed (#62)."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from notices.choices import PreparedNotificationStatusChoices as Status
from notices.filtersets import PreparedNotificationFilterSet
from notices.models import PreparedNotification
from notices.validators import PreparedNotificationStateMachine

User = get_user_model()


def _mark(notification, timestamp=None):
    PreparedNotificationStateMachine(notification).mark_viewed(timestamp=timestamp)
    notification.refresh_from_db()
    return notification


@pytest.mark.django_db
class TestMarkViewed:
    @pytest.mark.parametrize("status", [Status.SENT, Status.DELIVERED])
    def test_sets_viewed_at_without_changing_status(self, make_notification, status):
        n = _mark(make_notification(status))
        assert n.viewed_at is not None
        assert n.status == status

    def test_uses_supplied_timestamp(self, make_notification):
        at = timezone.now() - timedelta(minutes=30)
        assert _mark(make_notification(), at).viewed_at == at

    def test_keeps_earliest_view(self, make_notification):
        n = make_notification()
        first = timezone.now() - timedelta(minutes=30)
        _mark(n, first)
        assert _mark(n, timezone.now() - timedelta(minutes=10)).viewed_at == first
        earlier = timezone.now() - timedelta(minutes=50)
        assert _mark(n, earlier).viewed_at == earlier

    @pytest.mark.parametrize("status", [Status.DRAFT, Status.READY, Status.FAILED])
    def test_refused_before_sending(self, make_notification, status):
        with pytest.raises(ValidationError, match=status):
            _mark(make_notification(status))

    def test_future_timestamp_refused(self, make_notification):
        with pytest.raises(ValidationError, match="future"):
            _mark(make_notification(), timezone.now() + timedelta(minutes=5))

    def test_timestamp_before_sent_refused(self, make_notification):
        n = make_notification()
        with pytest.raises(ValidationError, match="sent_at"):
            _mark(n, n.sent_at - timedelta(seconds=1))


def _url(notification):
    return f"/api/plugins/notices/prepared-notifications/{notification.pk}/viewed/"


@pytest.mark.django_db
class TestViewedAction:
    def test_records_view(self, admin_api, make_notification):
        n = make_notification()
        at = timezone.now() - timedelta(minutes=5)
        response = admin_api.post(_url(n), {"timestamp": at.isoformat()}, format="json")
        assert response.status_code == 200
        n.refresh_from_db()
        assert n.viewed_at == at
        assert response.data["viewed_at"] is not None

    def test_without_body_uses_now(self, admin_api, make_notification):
        n = make_notification()
        assert admin_api.post(_url(n)).status_code == 200
        n.refresh_from_db()
        assert timezone.now() - n.viewed_at < timedelta(minutes=1)

    def test_bad_ordering_is_400_on_timestamp(self, admin_api, make_notification):
        n = make_notification()
        response = admin_api.post(_url(n), {"timestamp": (n.sent_at - timedelta(minutes=1)).isoformat()}, format="json")
        assert response.status_code == 400
        assert "timestamp" in response.data

    def test_unsent_is_400(self, admin_api, make_notification):
        assert admin_api.post(_url(make_notification(Status.DRAFT))).status_code == 400

    def test_view_only_user_is_forbidden(self, make_notification, grant_permission, api_client_for):
        user = User.objects.create_user(username="viewed-reader", password="x")
        grant_permission(user, ["view"], "preparednotification")
        assert api_client_for(user).post(_url(make_notification())).status_code == 403

    def test_object_permission_constraints_apply(self, make_notification, grant_permission, api_client_for):
        allowed, other = make_notification(), make_notification()
        user = User.objects.create_user(username="viewed-scoped", password="x")
        grant_permission(user, ["view", "change"], "preparednotification", constraints={"pk": allowed.pk})
        client = api_client_for(user)
        assert client.post(_url(other)).status_code == 404
        assert client.post(_url(allowed)).status_code == 200


@pytest.mark.django_db
def test_viewed_filter(make_notification):
    seen = make_notification(viewed_at=timezone.now())
    unseen = make_notification()

    def ids(value):
        return set(PreparedNotificationFilterSet({"viewed": value}, PreparedNotification.objects.all()).qs)

    assert ids("true") == {seen}
    assert ids("false") == {unseen}
