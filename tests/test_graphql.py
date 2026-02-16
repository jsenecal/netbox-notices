"""Tests for GraphQL API types."""

import pytest


@pytest.mark.django_db
class TestGraphQLTypes:
    def test_maintenance_type_exists(self):
        from notices.graphql.types import MaintenanceType

        assert MaintenanceType is not None

    def test_outage_type_exists(self):
        from notices.graphql.types import OutageType

        assert OutageType is not None

    def test_impact_type_exists(self):
        from notices.graphql.types import ImpactType

        assert ImpactType is not None

    def test_event_notification_type_exists(self):
        from notices.graphql.types import EventNotificationType

        assert EventNotificationType is not None

    def test_notification_template_type_exists(self):
        from notices.graphql.types import NotificationTemplateType

        assert NotificationTemplateType is not None

    def test_prepared_notification_type_exists(self):
        from notices.graphql.types import PreparedNotificationType

        assert PreparedNotificationType is not None

    def test_schema_exports_list(self):
        from notices.graphql.schema import schema

        assert isinstance(schema, list)
        assert len(schema) == 1

    def test_graphql_schema_registered(self):
        from notices import NoticesConfig

        assert hasattr(NoticesConfig, "graphql_schema")
        assert NoticesConfig.graphql_schema == "graphql.schema.schema"
