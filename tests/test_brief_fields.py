"""Tests for brief_fields on API serializers."""


class TestBriefFields:
    def test_maintenance_serializer_has_brief_fields(self):
        from notices.api.serializers.events import MaintenanceSerializer

        assert hasattr(MaintenanceSerializer.Meta, "brief_fields")
        assert "id" in MaintenanceSerializer.Meta.brief_fields
        assert "url" in MaintenanceSerializer.Meta.brief_fields
        assert "display" in MaintenanceSerializer.Meta.brief_fields
        assert "name" in MaintenanceSerializer.Meta.brief_fields

    def test_outage_serializer_has_brief_fields(self):
        from notices.api.serializers.events import OutageSerializer

        assert hasattr(OutageSerializer.Meta, "brief_fields")
        assert "id" in OutageSerializer.Meta.brief_fields

    def test_impact_serializer_has_brief_fields(self):
        from notices.api.serializers.events import ImpactSerializer

        assert hasattr(ImpactSerializer.Meta, "brief_fields")

    def test_event_notification_serializer_has_brief_fields(self):
        from notices.api.serializers.events import EventNotificationSerializer

        assert hasattr(EventNotificationSerializer.Meta, "brief_fields")

    def test_notification_template_serializer_has_brief_fields(self):
        from notices.api.serializers.messaging import NotificationTemplateSerializer

        assert hasattr(NotificationTemplateSerializer.Meta, "brief_fields")
        assert "name" in NotificationTemplateSerializer.Meta.brief_fields
        assert "slug" in NotificationTemplateSerializer.Meta.brief_fields

    def test_prepared_notification_serializer_has_brief_fields(self):
        from notices.api.serializers.messaging import PreparedNotificationSerializer

        assert hasattr(PreparedNotificationSerializer.Meta, "brief_fields")

    def test_sent_notification_serializer_has_brief_fields(self):
        from notices.api.serializers.messaging import SentNotificationSerializer

        assert hasattr(SentNotificationSerializer.Meta, "brief_fields")
