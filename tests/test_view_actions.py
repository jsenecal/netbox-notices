"""Tests for maintenance view quick actions."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from notices.models import EventNotification, Impact, Maintenance, Outage

User = get_user_model()


@pytest.fixture
def admin_user(db):
    """Create an admin user with all permissions."""
    user = User.objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="adminpass123",
    )
    return user


@pytest.fixture
def admin_client(admin_user):
    """Client logged in as admin."""
    client = Client()
    client.login(username="admin", password="adminpass123")
    return client


@pytest.fixture
def maintenance(provider):
    """Create a test maintenance."""
    return Maintenance.objects.create(
        name="TEST-MAINT-001",
        summary="Test maintenance",
        provider=provider,
        start=timezone.now() + timedelta(days=1),
        end=timezone.now() + timedelta(days=1, hours=4),
        status="CONFIRMED",
    )


@pytest.fixture
def outage(provider):
    """Create a test outage."""
    return Outage.objects.create(
        name="TEST-OUT-001",
        summary="Test outage",
        provider=provider,
        status="REPORTED",
    )


@pytest.mark.django_db
class TestMaintenanceAcknowledgeView:
    """Tests for MaintenanceAcknowledgeView."""

    def test_acknowledge_maintenance(self, admin_client, maintenance):
        """Should mark maintenance as acknowledged."""
        assert maintenance.acknowledged is False

        url = reverse("plugins:notices:maintenance_acknowledge", args=[maintenance.pk])
        response = admin_client.post(url)

        maintenance.refresh_from_db()
        assert maintenance.acknowledged is True
        assert response.status_code == 302

    def test_acknowledge_redirects_to_detail(self, admin_client, maintenance):
        """Should redirect to maintenance detail page."""
        url = reverse("plugins:notices:maintenance_acknowledge", args=[maintenance.pk])
        response = admin_client.post(url)

        assert response.status_code == 302
        assert f"/maintenance/{maintenance.pk}/" in response.url

    def test_acknowledge_with_return_url(self, admin_client, maintenance):
        """Should redirect to return_url if provided."""
        url = reverse("plugins:notices:maintenance_acknowledge", args=[maintenance.pk])
        return_url = "/plugins/notices/maintenance/"
        response = admin_client.post(url, {"return_url": return_url})

        assert response.status_code == 302
        assert response.url == return_url


@pytest.mark.django_db
class TestMaintenanceCancelView:
    """Tests for MaintenanceCancelView."""

    def test_get_shows_confirmation(self, admin_client, maintenance):
        """GET should show confirmation page."""
        url = reverse("plugins:notices:maintenance_cancel", args=[maintenance.pk])
        response = admin_client.get(url)

        assert response.status_code == 200
        assert "object" in response.context
        assert response.context["object"] == maintenance

    def test_cancel_maintenance(self, admin_client, maintenance):
        """POST should cancel maintenance."""
        url = reverse("plugins:notices:maintenance_cancel", args=[maintenance.pk])
        response = admin_client.post(url)

        maintenance.refresh_from_db()
        assert maintenance.status == "CANCELLED"
        assert response.status_code == 302

    def test_cannot_cancel_completed_maintenance(self, admin_client, provider):
        """Should not allow cancelling completed maintenance."""
        completed = Maintenance.objects.create(
            name="COMPLETED",
            summary="Test",
            provider=provider,
            start=timezone.now() - timedelta(days=2),
            end=timezone.now() - timedelta(days=1),
            status="COMPLETED",
        )

        url = reverse("plugins:notices:maintenance_cancel", args=[completed.pk])
        admin_client.post(url)

        completed.refresh_from_db()
        assert completed.status == "COMPLETED"  # Status unchanged

    def test_cannot_cancel_already_cancelled(self, admin_client, provider):
        """Should not allow cancelling already cancelled maintenance."""
        cancelled = Maintenance.objects.create(
            name="CANCELLED",
            summary="Test",
            provider=provider,
            start=timezone.now() + timedelta(days=1),
            end=timezone.now() + timedelta(days=2),
            status="CANCELLED",
        )

        url = reverse("plugins:notices:maintenance_cancel", args=[cancelled.pk])
        admin_client.post(url)

        cancelled.refresh_from_db()
        assert cancelled.status == "CANCELLED"


@pytest.mark.django_db
class TestMaintenanceMarkInProgressView:
    """Tests for MaintenanceMarkInProgressView."""

    def test_mark_in_progress(self, admin_client, maintenance):
        """Should mark maintenance as in-progress."""
        url = reverse(
            "plugins:notices:maintenance_mark_in_progress", args=[maintenance.pk]
        )
        response = admin_client.post(url)

        maintenance.refresh_from_db()
        assert maintenance.status == "IN-PROCESS"
        assert response.status_code == 302

    def test_cannot_mark_completed_as_in_progress(self, admin_client, provider):
        """Should not allow marking completed maintenance as in-progress."""
        completed = Maintenance.objects.create(
            name="COMPLETED",
            summary="Test",
            provider=provider,
            start=timezone.now() - timedelta(days=2),
            end=timezone.now() - timedelta(days=1),
            status="COMPLETED",
        )

        url = reverse(
            "plugins:notices:maintenance_mark_in_progress", args=[completed.pk]
        )
        admin_client.post(url)

        completed.refresh_from_db()
        assert completed.status == "COMPLETED"  # Status unchanged

    def test_cannot_mark_cancelled_as_in_progress(self, admin_client, provider):
        """Should not allow marking cancelled maintenance as in-progress."""
        cancelled = Maintenance.objects.create(
            name="CANCELLED",
            summary="Test",
            provider=provider,
            start=timezone.now() + timedelta(days=1),
            end=timezone.now() + timedelta(days=2),
            status="CANCELLED",
        )

        url = reverse(
            "plugins:notices:maintenance_mark_in_progress", args=[cancelled.pk]
        )
        admin_client.post(url)

        cancelled.refresh_from_db()
        assert cancelled.status == "CANCELLED"


@pytest.mark.django_db
class TestMaintenanceMarkCompletedView:
    """Tests for MaintenanceMarkCompletedView."""

    def test_mark_completed(self, admin_client, maintenance):
        """Should mark maintenance as completed."""
        url = reverse(
            "plugins:notices:maintenance_mark_completed", args=[maintenance.pk]
        )
        response = admin_client.post(url)

        maintenance.refresh_from_db()
        assert maintenance.status == "COMPLETED"
        assert response.status_code == 302

    def test_cannot_mark_cancelled_as_completed(self, admin_client, provider):
        """Should not allow marking cancelled maintenance as completed."""
        cancelled = Maintenance.objects.create(
            name="CANCELLED",
            summary="Test",
            provider=provider,
            start=timezone.now() + timedelta(days=1),
            end=timezone.now() + timedelta(days=2),
            status="CANCELLED",
        )

        url = reverse("plugins:notices:maintenance_mark_completed", args=[cancelled.pk])
        admin_client.post(url)

        cancelled.refresh_from_db()
        assert cancelled.status == "CANCELLED"

    def test_already_completed_shows_info(self, admin_client, provider):
        """Should show info message if already completed."""
        completed = Maintenance.objects.create(
            name="COMPLETED",
            summary="Test",
            provider=provider,
            start=timezone.now() - timedelta(days=2),
            end=timezone.now() - timedelta(days=1),
            status="COMPLETED",
        )

        url = reverse("plugins:notices:maintenance_mark_completed", args=[completed.pk])
        admin_client.post(url)

        completed.refresh_from_db()
        assert completed.status == "COMPLETED"


@pytest.mark.django_db
class TestMaintenanceDetailView:
    """Tests for MaintenanceView (detail view)."""

    def test_detail_view_loads(self, admin_client, maintenance):
        """Should load maintenance detail page."""
        url = reverse("plugins:notices:maintenance", args=[maintenance.pk])
        response = admin_client.get(url)

        assert response.status_code == 200

    def test_detail_view_shows_impacts(self, admin_client, maintenance, circuit):
        """Should show impacts on detail page."""
        ct = ContentType.objects.get_for_model(circuit)
        maint_ct = ContentType.objects.get_for_model(maintenance)
        Impact.objects.create(
            event_content_type=maint_ct,
            event_object_id=maintenance.pk,
            target_content_type=ct,
            target_object_id=circuit.pk,
            impact="OUTAGE",
        )

        url = reverse("plugins:notices:maintenance", args=[maintenance.pk])
        response = admin_client.get(url)

        assert response.status_code == 200
        assert "impacts" in response.context

    def test_detail_view_shows_notifications(self, admin_client, maintenance):
        """Should show notifications on detail page."""
        EventNotification.objects.create(
            event_content_type=ContentType.objects.get_for_model(maintenance),
            event_object_id=maintenance.pk,
            email=b"data",
            email_body="Test body",
            subject="Test Subject",
            email_from="noc@example.com",
            email_received=timezone.now(),
        )

        url = reverse("plugins:notices:maintenance", args=[maintenance.pk])
        response = admin_client.get(url)

        assert response.status_code == 200
        assert "notifications" in response.context


@pytest.mark.django_db
class TestOutageDetailView:
    """Tests for OutageView (detail view)."""

    def test_detail_view_loads(self, admin_client, outage):
        """Should load outage detail page."""
        url = reverse("plugins:notices:outage", args=[outage.pk])
        response = admin_client.get(url)

        assert response.status_code == 200

    def test_detail_view_shows_impacts(self, admin_client, outage, circuit):
        """Should show impacts on detail page."""
        ct = ContentType.objects.get_for_model(circuit)
        outage_ct = ContentType.objects.get_for_model(outage)
        Impact.objects.create(
            event_content_type=outage_ct,
            event_object_id=outage.pk,
            target_content_type=ct,
            target_object_id=circuit.pk,
            impact="OUTAGE",
        )

        url = reverse("plugins:notices:outage", args=[outage.pk])
        response = admin_client.get(url)

        assert response.status_code == 200
        assert "impacts" in response.context


@pytest.mark.django_db
class TestMaintenanceCalendarView:
    """Tests for MaintenanceCalendarView."""

    def test_calendar_view_loads(self, admin_client):
        """Should load calendar page."""
        url = reverse("plugins:notices:maintenance_calendar")
        response = admin_client.get(url)

        assert response.status_code == 200
        assert "title" in response.context
        assert response.context["title"] == "Maintenance Calendar"


@pytest.mark.django_db
class TestMaintenanceRescheduleView:
    """Tests for MaintenanceRescheduleView."""

    def test_reschedule_get_shows_form(self, admin_client, maintenance):
        """GET should show form with pre-filled data."""
        url = reverse("plugins:notices:maintenance_reschedule", args=[maintenance.pk])
        response = admin_client.get(url)

        assert response.status_code == 200
        # Form should have original maintenance data
        assert "form" in response.context

    def test_reschedule_creates_new_maintenance(self, admin_client, maintenance):
        """POST should create new maintenance linked to original."""
        url = reverse("plugins:notices:maintenance_reschedule", args=[maintenance.pk])
        new_start = timezone.now() + timedelta(days=7)
        new_end = new_start + timedelta(hours=4)

        admin_client.post(
            url,
            {
                "name": "RESCHEDULED-001",
                "summary": maintenance.summary,
                "provider": maintenance.provider.pk,
                "start": new_start.strftime("%Y-%m-%d %H:%M:%S"),
                "end": new_end.strftime("%Y-%m-%d %H:%M:%S"),
                "status": "TENTATIVE",
                "replaces": maintenance.pk,
            },
        )

        # Should create new maintenance
        new_maint = Maintenance.objects.filter(name="RESCHEDULED-001").first()
        assert new_maint is not None
        assert new_maint.replaces == maintenance
