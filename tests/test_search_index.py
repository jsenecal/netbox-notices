"""Tests for SearchIndex registration."""

import pytest


@pytest.mark.django_db
class TestSearchIndexes:
    """Test that search indexes are properly registered with NetBox."""

    def test_maintenance_index_registered(self):
        from netbox.registry import registry

        assert "notices.maintenance" in registry["search"]

    def test_outage_index_registered(self):
        from netbox.registry import registry

        assert "notices.outage" in registry["search"]

    def test_event_notification_index_registered(self):
        from netbox.registry import registry

        assert "notices.eventnotification" in registry["search"]

    def test_notification_template_index_registered(self):
        from netbox.registry import registry

        assert "notices.notificationtemplate" in registry["search"]

    def test_prepared_notification_index_registered(self):
        from netbox.registry import registry

        assert "notices.preparednotification" in registry["search"]

    def test_maintenance_index_fields(self):
        from notices.search import MaintenanceIndex

        field_names = [f[0] for f in MaintenanceIndex.fields]
        assert "name" in field_names
        assert "summary" in field_names
        assert "internal_ticket" in field_names
        assert "comments" in field_names

    def test_outage_index_fields(self):
        from notices.search import OutageIndex

        field_names = [f[0] for f in OutageIndex.fields]
        assert "name" in field_names
        assert "summary" in field_names
        assert "internal_ticket" in field_names
        assert "comments" in field_names

    def test_event_notification_index_fields(self):
        from notices.search import EventNotificationIndex

        field_names = [f[0] for f in EventNotificationIndex.fields]
        assert "subject" in field_names
        assert "email_from" in field_names

    def test_notification_template_index_fields(self):
        from notices.search import NotificationTemplateIndex

        field_names = [f[0] for f in NotificationTemplateIndex.fields]
        assert "name" in field_names
        assert "slug" in field_names
        assert "description" in field_names

    def test_prepared_notification_index_fields(self):
        from notices.search import PreparedNotificationIndex

        field_names = [f[0] for f in PreparedNotificationIndex.fields]
        assert "subject" in field_names
        assert "body_text" in field_names

    def test_maintenance_index_model(self):
        from notices.models import Maintenance
        from notices.search import MaintenanceIndex

        assert MaintenanceIndex.model is Maintenance

    def test_outage_index_model(self):
        from notices.models import Outage
        from notices.search import OutageIndex

        assert OutageIndex.model is Outage

    def test_event_notification_index_model(self):
        from notices.models import EventNotification
        from notices.search import EventNotificationIndex

        assert EventNotificationIndex.model is EventNotification

    def test_notification_template_index_model(self):
        from notices.models import NotificationTemplate
        from notices.search import NotificationTemplateIndex

        assert NotificationTemplateIndex.model is NotificationTemplate

    def test_prepared_notification_index_model(self):
        from notices.models import PreparedNotification
        from notices.search import PreparedNotificationIndex

        assert PreparedNotificationIndex.model is PreparedNotification

    def test_maintenance_display_attrs(self):
        from notices.search import MaintenanceIndex

        assert "provider" in MaintenanceIndex.display_attrs
        assert "status" in MaintenanceIndex.display_attrs
        assert "summary" in MaintenanceIndex.display_attrs

    def test_outage_display_attrs(self):
        from notices.search import OutageIndex

        assert "provider" in OutageIndex.display_attrs
        assert "status" in OutageIndex.display_attrs
        assert "summary" in OutageIndex.display_attrs
