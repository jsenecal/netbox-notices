"""Tests for filterset search methods."""

from datetime import timedelta

import pytest
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from notices.filtersets import (
    EventNotificationFilterSet,
    ImpactFilterSet,
    MaintenanceFilterSet,
    NotificationTemplateFilterSet,
    OutageFilterSet,
    PreparedNotificationFilterSet,
)
from notices.models import (
    EventNotification,
    Impact,
    Maintenance,
    NotificationTemplate,
    Outage,
    PreparedNotification,
)


@pytest.mark.django_db
class TestMaintenanceFilterSetSearch:
    """Tests for MaintenanceFilterSet search method."""

    def test_search_by_name(self, provider):
        """Should find maintenance by name."""
        Maintenance.objects.create(
            name="MAINT-UNIQUE-123",
            summary="Test",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=4),
            status="CONFIRMED",
        )
        Maintenance.objects.create(
            name="OTHER",
            summary="Test",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=4),
            status="CONFIRMED",
        )

        filterset = MaintenanceFilterSet({"q": "UNIQUE"}, Maintenance.objects.all())
        assert filterset.qs.count() == 1
        assert filterset.qs.first().name == "MAINT-UNIQUE-123"

    def test_search_by_summary(self, provider):
        """Should find maintenance by summary."""
        Maintenance.objects.create(
            name="Test",
            summary="Router firmware upgrade required",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=4),
            status="CONFIRMED",
        )

        filterset = MaintenanceFilterSet({"q": "firmware"}, Maintenance.objects.all())
        assert filterset.qs.count() == 1

    def test_search_by_internal_ticket(self, provider):
        """Should find maintenance by internal ticket."""
        Maintenance.objects.create(
            name="Test",
            summary="Test",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=4),
            status="CONFIRMED",
            internal_ticket="CHG0012345",
        )

        filterset = MaintenanceFilterSet({"q": "CHG0012345"}, Maintenance.objects.all())
        assert filterset.qs.count() == 1

    def test_search_empty_value(self, provider):
        """Should return all when search is empty."""
        Maintenance.objects.create(
            name="Test",
            summary="Test",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=4),
            status="CONFIRMED",
        )

        filterset = MaintenanceFilterSet({"q": "  "}, Maintenance.objects.all())
        assert filterset.qs.count() == 1

    def test_filter_has_replaces_true(self, provider):
        """Should filter maintenances that have replacements."""
        original = Maintenance.objects.create(
            name="Original",
            summary="Test",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=4),
            status="RE-SCHEDULED",
        )
        Maintenance.objects.create(
            name="Replacement",
            summary="Test",
            provider=provider,
            start=timezone.now() + timedelta(days=1),
            end=timezone.now() + timedelta(days=1, hours=4),
            status="CONFIRMED",
            replaces=original,
        )

        filterset = MaintenanceFilterSet({"has_replaces": True}, Maintenance.objects.all())
        assert filterset.qs.count() == 1
        assert filterset.qs.first().name == "Original"


@pytest.mark.django_db
class TestOutageFilterSetSearch:
    """Tests for OutageFilterSet search method."""

    def test_search_by_name(self, provider):
        """Should find outage by name."""
        Outage.objects.create(
            name="OUT-CRITICAL-001",
            summary="Test",
            provider=provider,
            status="REPORTED",
        )

        filterset = OutageFilterSet({"q": "CRITICAL"}, Outage.objects.all())
        assert filterset.qs.count() == 1

    def test_search_by_summary(self, provider):
        """Should find outage by summary."""
        Outage.objects.create(
            name="Test",
            summary="Fiber cut on main route",
            provider=provider,
            status="REPORTED",
        )

        filterset = OutageFilterSet({"q": "Fiber"}, Outage.objects.all())
        assert filterset.qs.count() == 1

    def test_search_empty_value(self, provider):
        """Should return all when search is empty."""
        Outage.objects.create(
            name="Test",
            summary="Test",
            provider=provider,
            status="REPORTED",
        )

        filterset = OutageFilterSet({"q": ""}, Outage.objects.all())
        assert filterset.qs.count() == 1


@pytest.mark.django_db
class TestImpactFilterSetSearch:
    """Tests for ImpactFilterSet search method."""

    def test_search_by_impact_level(self, provider, circuit):
        """Should find impact by impact level."""
        maintenance = Maintenance.objects.create(
            name="Test",
            summary="Test",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=4),
            status="CONFIRMED",
        )
        ct = ContentType.objects.get_for_model(circuit)
        maint_ct = ContentType.objects.get_for_model(maintenance)
        Impact.objects.create(
            event_content_type=maint_ct,
            event_object_id=maintenance.pk,
            target_content_type=ct,
            target_object_id=circuit.pk,
            impact="OUTAGE",
        )

        filterset = ImpactFilterSet({"q": "OUTAGE"}, Impact.objects.all())
        assert filterset.qs.count() == 1

    def test_search_empty_value(self, provider, circuit):
        """Should return all when search is empty."""
        maintenance = Maintenance.objects.create(
            name="Test",
            summary="Test",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=4),
            status="CONFIRMED",
        )
        ct = ContentType.objects.get_for_model(circuit)
        maint_ct = ContentType.objects.get_for_model(maintenance)
        Impact.objects.create(
            event_content_type=maint_ct,
            event_object_id=maintenance.pk,
            target_content_type=ct,
            target_object_id=circuit.pk,
            impact="OUTAGE",
        )

        filterset = ImpactFilterSet({"q": "   "}, Impact.objects.all())
        assert filterset.qs.count() == 1


@pytest.mark.django_db
class TestEventNotificationFilterSetSearch:
    """Tests for EventNotificationFilterSet search method."""

    def test_search_by_subject(self, provider):
        """Should find notification by subject."""
        maintenance = Maintenance.objects.create(
            name="Test",
            summary="Test",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=4),
            status="CONFIRMED",
        )
        EventNotification.objects.create(
            event_content_type=ContentType.objects.get_for_model(maintenance),
            event_object_id=maintenance.pk,
            email=b"data",
            email_body="body",
            subject="Urgent: Network Maintenance",
            email_from="noc@example.com",
            email_received=timezone.now(),
        )

        filterset = EventNotificationFilterSet({"q": "Urgent"}, EventNotification.objects.all())
        assert filterset.qs.count() == 1

    def test_search_by_email_body(self, provider):
        """Should find notification by email body."""
        maintenance = Maintenance.objects.create(
            name="Test",
            summary="Test",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=4),
            status="CONFIRMED",
        )
        EventNotification.objects.create(
            event_content_type=ContentType.objects.get_for_model(maintenance),
            event_object_id=maintenance.pk,
            email=b"data",
            email_body="Please be advised of scheduled maintenance",
            subject="Subject",
            email_from="noc@example.com",
            email_received=timezone.now(),
        )

        filterset = EventNotificationFilterSet({"q": "advised"}, EventNotification.objects.all())
        assert filterset.qs.count() == 1

    def test_search_by_email_from(self, provider):
        """Should find notification by sender."""
        maintenance = Maintenance.objects.create(
            name="Test",
            summary="Test",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=4),
            status="CONFIRMED",
        )
        EventNotification.objects.create(
            event_content_type=ContentType.objects.get_for_model(maintenance),
            event_object_id=maintenance.pk,
            email=b"data",
            email_body="body",
            subject="Subject",
            email_from="noc-team@provider.net",
            email_received=timezone.now(),
        )

        filterset = EventNotificationFilterSet({"q": "provider.net"}, EventNotification.objects.all())
        assert filterset.qs.count() == 1

    def test_search_empty_value(self, provider):
        """Should return all when search is empty."""
        maintenance = Maintenance.objects.create(
            name="Test",
            summary="Test",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=4),
            status="CONFIRMED",
        )
        EventNotification.objects.create(
            event_content_type=ContentType.objects.get_for_model(maintenance),
            event_object_id=maintenance.pk,
            email=b"data",
            email_body="body",
            subject="Subject",
            email_from="test@example.com",
            email_received=timezone.now(),
        )

        filterset = EventNotificationFilterSet({"q": ""}, EventNotification.objects.all())
        assert filterset.qs.count() == 1


@pytest.mark.django_db
class TestMaintenanceFilterSetHasReplaceFalse:
    """Test the false branch of filter_has_replaces."""

    def test_filter_has_replaces_false(self, provider):
        """Should filter maintenances that have NOT been rescheduled."""
        original = Maintenance.objects.create(
            name="Original",
            summary="Test",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=4),
            status="RE-SCHEDULED",
        )
        Maintenance.objects.create(
            name="Standalone",
            summary="Test",
            provider=provider,
            start=timezone.now(),
            end=timezone.now() + timedelta(hours=4),
            status="CONFIRMED",
        )
        Maintenance.objects.create(
            name="Replacement",
            summary="Test",
            provider=provider,
            start=timezone.now() + timedelta(days=1),
            end=timezone.now() + timedelta(days=1, hours=4),
            status="CONFIRMED",
            replaces=original,
        )

        filterset = MaintenanceFilterSet({"has_replaces": False}, Maintenance.objects.all())
        names = list(filterset.qs.values_list("name", flat=True))
        assert "Standalone" in names
        assert "Replacement" in names
        assert "Original" not in names


@pytest.mark.django_db
class TestNotificationTemplateFilterSetSearch:
    """Tests for NotificationTemplateFilterSet search method."""

    def _create_template(self, name, slug, description=""):
        return NotificationTemplate.objects.create(
            name=name,
            slug=slug,
            description=description,
            event_type="maintenance",
            granularity="per_event",
            subject_template="S",
            body_template="B",
            body_format="text",
            weight=1000,
        )

    def test_search_by_name(self):
        self._create_template("Outage Alert", "outage-alert")
        self._create_template("Maintenance Notice", "maint-notice")

        filterset = NotificationTemplateFilterSet({"q": "Alert"}, NotificationTemplate.objects.all())
        assert filterset.qs.count() == 1
        assert filterset.qs.first().name == "Outage Alert"

    def test_search_by_slug(self):
        self._create_template("Template One", "template-one")

        filterset = NotificationTemplateFilterSet({"q": "template-one"}, NotificationTemplate.objects.all())
        assert filterset.qs.count() == 1

    def test_search_by_description(self):
        self._create_template("T1", "t1", description="Sends alerts to NOC team")

        filterset = NotificationTemplateFilterSet({"q": "NOC team"}, NotificationTemplate.objects.all())
        assert filterset.qs.count() == 1

    def test_search_empty_returns_all(self):
        self._create_template("T1", "t1")
        self._create_template("T2", "t2")

        filterset = NotificationTemplateFilterSet({"q": "  "}, NotificationTemplate.objects.all())
        assert filterset.qs.count() == 2


@pytest.mark.django_db
class TestPreparedNotificationFilterSetSearch:
    """Tests for PreparedNotificationFilterSet search method."""

    def _create_prepared(self, subject, body_text="body"):
        template = NotificationTemplate.objects.create(
            name=f"Tmpl-{subject[:10]}",
            slug=f"tmpl-{subject[:10].lower().replace(' ', '-')}",
            event_type="maintenance",
            granularity="per_event",
            subject_template="S",
            body_template="B",
            body_format="text",
            weight=1000,
        )
        return PreparedNotification.objects.create(
            template=template,
            subject=subject,
            body_text=body_text,
        )

    def test_search_by_subject(self):
        self._create_prepared("Critical Outage Notification")
        self._create_prepared("Routine Maintenance")

        filterset = PreparedNotificationFilterSet({"q": "Critical"}, PreparedNotification.objects.all())
        assert filterset.qs.count() == 1

    def test_search_by_body_text(self):
        self._create_prepared("Subject", body_text="Router firmware update scheduled")

        filterset = PreparedNotificationFilterSet({"q": "firmware"}, PreparedNotification.objects.all())
        assert filterset.qs.count() == 1

    def test_search_empty_returns_all(self):
        self._create_prepared("A")
        self._create_prepared("B")

        filterset = PreparedNotificationFilterSet({"q": " "}, PreparedNotification.objects.all())
        assert filterset.qs.count() == 2
