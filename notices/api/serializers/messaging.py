import yaml
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError as DjangoValidationError
from netbox.api.serializers import NetBoxModelSerializer, WritableNestedSerializer
from rest_framework import serializers
from tenancy.api.serializers import ContactRoleSerializer, ContactSerializer
from tenancy.models import Contact

from notices.models import MessageTemplate, PreparedMessage, TemplateScope
from notices.validators import PreparedMessageStateMachine

__all__ = (
    "MessageTemplateSerializer",
    "NestedMessageTemplateSerializer",
    "TemplateScopeSerializer",
    "PreparedMessageSerializer",
)


class TemplateScopeSerializer(serializers.ModelSerializer):
    """Serializer for TemplateScope."""

    content_type = serializers.SlugRelatedField(
        queryset=ContentType.objects.all(),
        slug_field="model",
    )
    object_repr = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = TemplateScope
        fields = [
            "id",
            "content_type",
            "object_id",
            "object_repr",
            "event_type",
            "event_status",
            "weight",
        ]

    def get_object_repr(self, obj):
        """Return string representation of the scoped object."""
        if obj.object:
            return str(obj.object)
        return f"All {obj.content_type.model}s"


class MessageTemplateSerializer(NetBoxModelSerializer):
    """Serializer for MessageTemplate."""

    url = serializers.HyperlinkedIdentityField(
        view_name="plugins-api:notices-api:messagetemplate-detail",
    )
    scopes = TemplateScopeSerializer(many=True, required=False)
    contact_roles = ContactRoleSerializer(many=True, required=False, nested=True)
    extends = serializers.PrimaryKeyRelatedField(
        queryset=MessageTemplate.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = MessageTemplate
        fields = [
            "id",
            "url",
            "display",
            "name",
            "slug",
            "description",
            "event_type",
            "granularity",
            "subject_template",
            "body_template",
            "body_format",
            "css_template",
            "headers_template",
            "include_ical",
            "ical_template",
            "contact_roles",
            "contact_priorities",
            "is_base_template",
            "extends",
            "weight",
            "scopes",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        ]

    def validate_headers_template(self, value):
        """Accept YAML input and convert to dict."""
        if isinstance(value, str):
            try:
                return yaml.safe_load(value) or {}
            except yaml.YAMLError as e:
                raise serializers.ValidationError(f"Invalid YAML: {e}")
        return value

    def create(self, validated_data):
        scopes_data = validated_data.pop("scopes", [])
        contact_roles = validated_data.pop("contact_roles", [])

        instance = super().create(validated_data)

        # Create scopes
        for scope_data in scopes_data:
            TemplateScope.objects.create(template=instance, **scope_data)

        # Set contact roles
        if contact_roles:
            instance.contact_roles.set(contact_roles)

        return instance

    def update(self, instance, validated_data):
        scopes_data = validated_data.pop("scopes", None)
        contact_roles = validated_data.pop("contact_roles", None)

        instance = super().update(instance, validated_data)

        # Update scopes if provided
        if scopes_data is not None:
            instance.scopes.all().delete()
            for scope_data in scopes_data:
                TemplateScope.objects.create(template=instance, **scope_data)

        # Update contact roles if provided
        if contact_roles is not None:
            instance.contact_roles.set(contact_roles)

        return instance


class NestedMessageTemplateSerializer(WritableNestedSerializer):
    """Nested serializer for MessageTemplate."""

    url = serializers.HyperlinkedIdentityField(
        view_name="plugins-api:notices-api:messagetemplate-detail",
    )

    class Meta:
        model = MessageTemplate
        fields = ["id", "url", "display", "name", "slug"]


class PreparedMessageSerializer(NetBoxModelSerializer):
    """Serializer for PreparedMessage."""

    url = serializers.HyperlinkedIdentityField(
        view_name="plugins-api:notices-api:preparedmessage-detail",
    )
    template = NestedMessageTemplateSerializer(read_only=True)
    template_id = serializers.PrimaryKeyRelatedField(
        queryset=MessageTemplate.objects.all(),
        source="template",
        write_only=True,
    )
    contacts = ContactSerializer(many=True, read_only=True, nested=True)
    contact_ids = serializers.PrimaryKeyRelatedField(
        queryset=Contact.objects.all(),
        many=True,
        source="contacts",
        write_only=True,
        required=False,
    )
    recipients = serializers.JSONField(read_only=True)

    # Status change message (for journal entry)
    message = serializers.CharField(write_only=True, required=False, allow_blank=True)
    timestamp = serializers.DateTimeField(
        write_only=True,
        required=False,
        help_text="Optional timestamp for the transition (for external systems with batch processing)",
    )

    class Meta:
        model = PreparedMessage
        fields = [
            "id",
            "url",
            "display",
            "template",
            "template_id",
            "event_content_type",
            "event_id",
            "status",
            "message",
            "timestamp",
            "contacts",
            "contact_ids",
            "recipients",
            "subject",
            "body_text",
            "body_html",
            "headers",
            "css",
            "ical_content",
            "approved_by",
            "approved_at",
            "sent_at",
            "delivered_at",
            "viewed_at",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        ]
        read_only_fields = [
            "recipients",
            "approved_by",
            "approved_at",
            "sent_at",
            "delivered_at",
            "viewed_at",
        ]

    def validate(self, data):
        """Validate status transitions using state machine."""
        if self.instance and "status" in data:
            new_status = data["status"]
            if new_status != self.instance.status:
                sm = PreparedMessageStateMachine(self.instance)
                if not sm.can_transition_to(new_status):
                    valid = sm.get_valid_transitions()
                    raise serializers.ValidationError(
                        {
                            "status": f"Cannot transition from '{self.instance.status}' to '{new_status}'. "
                            f"Valid: {', '.join(valid) or 'none'}"
                        }
                    )
        return data

    def update(self, instance, validated_data):
        message_text = validated_data.pop("message", None)
        timestamp = validated_data.pop("timestamp", None)
        new_status = validated_data.get("status")

        # Handle status transition with state machine
        if new_status and new_status != instance.status:
            request = self.context.get("request")
            user = request.user if request else None

            sm = PreparedMessageStateMachine(instance, user=user)
            try:
                sm.transition_to(new_status, message_text=message_text, timestamp=timestamp)
            except DjangoValidationError as e:
                raise serializers.ValidationError({"timestamp": e.message})

            # Remove status from validated_data since state machine handled it
            validated_data.pop("status", None)

            # Refresh instance from database after state machine saved it
            instance.refresh_from_db()

        return super().update(instance, validated_data)
