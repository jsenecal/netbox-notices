from circuits.api.serializers import CircuitSerializer, ProviderSerializer
from django.contrib.contenttypes.models import ContentType
from netbox.api.serializers import NetBoxModelSerializer, WritableNestedSerializer
from rest_framework import serializers

from ..models import (
    EventNotification,
    Impact,
    Maintenance,
    Outage,
)


class NestedMaintenanceSerializer(WritableNestedSerializer):
    """Nested serializer for Maintenance model"""

    url = serializers.HyperlinkedIdentityField(
        view_name="plugins-api:notices-api:maintenance-detail"
    )

    provider = ProviderSerializer(nested=True)

    class Meta:
        model = Maintenance
        fields = (
            "id",
            "url",
            "name",
            "status",
            "provider",
            "start",
            "end",
            "original_timezone",
            "acknowledged",
            "created",
            "last_updated",
        )


class NestedOutageSerializer(WritableNestedSerializer):
    """Nested serializer for Outage model"""

    url = serializers.HyperlinkedIdentityField(
        view_name="plugins-api:notices-api:outage-detail"
    )

    provider = ProviderSerializer(nested=True)

    class Meta:
        model = Outage
        fields = (
            "id",
            "url",
            "name",
            "status",
            "provider",
            "start",
            "end",
            "estimated_time_to_repair",
            "original_timezone",
            "acknowledged",
            "created",
            "last_updated",
        )


class NestedImpactSerializer(WritableNestedSerializer):
    """Nested serializer for Impact model"""

    url = serializers.HyperlinkedIdentityField(
        view_name="plugins-api:notices-api:impact-detail"
    )

    # Read-only representation of the event
    event_type = serializers.SerializerMethodField(read_only=True)
    event_object = serializers.SerializerMethodField(read_only=True)

    # Read-only representation of the target
    target_type = serializers.SerializerMethodField(read_only=True)
    target_object = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Impact
        fields = (
            "id",
            "url",
            "event_type",
            "event_object",
            "target_type",
            "target_object",
            "impact",
            "created",
            "last_updated",
        )

    def get_event_type(self, obj):
        """Return event content type as app_label.model"""
        if obj.event_content_type:
            return f"{obj.event_content_type.app_label}.{obj.event_content_type.model}"
        return None

    def get_event_object(self, obj):
        """Return basic representation of the event object"""
        if obj.event:
            return {"id": obj.event_object_id, "name": str(obj.event)}
        return None

    def get_target_type(self, obj):
        """Return target content type as app_label.model"""
        if obj.target_content_type:
            return (
                f"{obj.target_content_type.app_label}.{obj.target_content_type.model}"
            )
        return None

    def get_target_object(self, obj):
        """Return basic representation of the target object"""
        if obj.target:
            return {"id": obj.target_object_id, "name": str(obj.target)}
        return None


class NestedEventNotificationSerializer(WritableNestedSerializer):
    """Nested serializer for EventNotification model"""

    url = serializers.HyperlinkedIdentityField(
        view_name="plugins-api:notices-api:eventnotification-detail"
    )

    # Read-only representation of the event
    event_type = serializers.SerializerMethodField(read_only=True)
    event_object = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = EventNotification
        fields = (
            "id",
            "url",
            "event_type",
            "event_object",
            "subject",
            "email_from",
            "email_received",
            "created",
            "last_updated",
        )

    def get_event_type(self, obj):
        """Return event content type as app_label.model"""
        if obj.event_content_type:
            return f"{obj.event_content_type.app_label}.{obj.event_content_type.model}"
        return None

    def get_event_object(self, obj):
        """Return basic representation of the event object"""
        if obj.event:
            return {"id": obj.event_object_id, "name": str(obj.event)}
        return None


class MaintenanceSerializer(NetBoxModelSerializer):
    """Full serializer for Maintenance model"""

    url = serializers.HyperlinkedIdentityField(
        view_name="plugins-api:notices-api:maintenance-detail"
    )

    provider = ProviderSerializer(nested=True)
    replaces = serializers.PrimaryKeyRelatedField(
        queryset=Maintenance.objects.all(), required=False, allow_null=True
    )
    impacts = NestedImpactSerializer(
        required=False, many=True, read_only=True, source="impact_set"
    )
    notifications = NestedEventNotificationSerializer(
        required=False, many=True, read_only=True, source="eventnotification_set"
    )
    status_color = serializers.CharField(source="get_status_color", read_only=True)
    impact_count = serializers.SerializerMethodField(read_only=True)

    def get_impact_count(self, obj):
        """Return count of impacts for this maintenance event"""
        return obj.impacts.count()

    class Meta:
        model = Maintenance
        fields = (
            "id",
            "url",
            "display",
            "name",
            "summary",
            "status",
            "status_color",
            "provider",
            "start",
            "end",
            "original_timezone",
            "internal_ticket",
            "acknowledged",
            "replaces",
            "impacts",
            "impact_count",
            "notifications",
            "impact",
            "comments",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )


class OutageSerializer(NetBoxModelSerializer):
    """Full serializer for Outage model"""

    url = serializers.HyperlinkedIdentityField(
        view_name="plugins-api:notices-api:outage-detail"
    )

    provider = ProviderSerializer(nested=True)
    impacts = NestedImpactSerializer(
        required=False, many=True, read_only=True, source="impact_set"
    )
    notifications = NestedEventNotificationSerializer(
        required=False, many=True, read_only=True, source="eventnotification_set"
    )

    class Meta:
        model = Outage
        fields = (
            "id",
            "url",
            "display",
            "name",
            "summary",
            "status",
            "provider",
            "start",
            "reported_at",
            "end",
            "estimated_time_to_repair",
            "original_timezone",
            "internal_ticket",
            "acknowledged",
            "impacts",
            "notifications",
            "impact",
            "comments",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )


class ImpactSerializer(NetBoxModelSerializer):
    """
    Full serializer for Impact model.
    Handles GenericForeignKey relationships for both event and target.
    """

    url = serializers.HyperlinkedIdentityField(
        view_name="plugins-api:notices-api:impact-detail"
    )

    # Write fields for GenericForeignKey - event
    event_content_type = serializers.PrimaryKeyRelatedField(
        queryset=ContentType.objects.filter(
            app_label="notices", model__in=["maintenance", "outage"]
        ),
        help_text="Content type of the event (Maintenance or Outage)",
    )
    event_object_id = serializers.IntegerField(help_text="ID of the event object")

    # Write fields for GenericForeignKey - target
    target_content_type = serializers.PrimaryKeyRelatedField(
        queryset=ContentType.objects.all(),
        help_text="Content type of the target object",
    )
    target_object_id = serializers.IntegerField(help_text="ID of the target object")

    # Read-only nested representations
    event = serializers.SerializerMethodField(read_only=True)
    target = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Impact
        fields = (
            "id",
            "url",
            "display",
            "event_content_type",
            "event_object_id",
            "event",
            "target_content_type",
            "target_object_id",
            "target",
            "impact",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )

    def get_event(self, obj):
        """
        Return nested representation of the event object.
        Returns Maintenance or Outage details depending on type.
        """
        if not obj.event:
            return None

        event_type = obj.event_content_type.model
        if event_type == "maintenance":
            return NestedMaintenanceSerializer(obj.event, context=self.context).data
        elif event_type == "outage":
            return NestedOutageSerializer(obj.event, context=self.context).data

        # Fallback for unknown types
        return {
            "id": obj.event_object_id,
            "name": str(obj.event),
            "type": f"{obj.event_content_type.app_label}.{obj.event_content_type.model}",
        }

    def get_target(self, obj):
        """
        Return nested representation of the target object.
        Returns Circuit details if target is a circuit, otherwise basic info.
        """
        if not obj.target:
            return None

        target_type = obj.target_content_type.model

        # Use CircuitSerializer for circuits
        if target_type == "circuit":
            return CircuitSerializer(obj.target, context=self.context).data

        # For other types, return basic representation
        return {
            "id": obj.target_object_id,
            "name": str(obj.target),
            "type": f"{obj.target_content_type.app_label}.{obj.target_content_type.model}",
        }


class EventNotificationSerializer(NetBoxModelSerializer):
    """
    Full serializer for EventNotification model.
    Handles GenericForeignKey relationship to event (Maintenance or Outage).
    """

    url = serializers.HyperlinkedIdentityField(
        view_name="plugins-api:notices-api:eventnotification-detail"
    )

    # Write fields for GenericForeignKey
    event_content_type = serializers.PrimaryKeyRelatedField(
        queryset=ContentType.objects.filter(
            app_label="notices", model__in=["maintenance", "outage"]
        ),
        help_text="Content type of the event (Maintenance or Outage)",
    )
    event_object_id = serializers.IntegerField(help_text="ID of the event object")

    # Read-only nested representation
    event = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = EventNotification
        fields = (
            "id",
            "url",
            "display",
            "event_content_type",
            "event_object_id",
            "event",
            "email_body",
            "subject",
            "email_from",
            "email_received",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )

    def get_event(self, obj):
        """
        Return nested representation of the event object.
        Returns Maintenance or Outage details depending on type.
        """
        if not obj.event:
            return None

        event_type = obj.event_content_type.model
        if event_type == "maintenance":
            return NestedMaintenanceSerializer(obj.event, context=self.context).data
        elif event_type == "outage":
            return NestedOutageSerializer(obj.event, context=self.context).data

        # Fallback for unknown types
        return {
            "id": obj.event_object_id,
            "name": str(obj.event),
            "type": f"{obj.event_content_type.app_label}.{obj.event_content_type.model}",
        }
