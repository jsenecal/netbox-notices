from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.urls import reverse
from netbox.models import NetBoxModel
from tenancy.models import Contact, ContactRole

from ..choices import (
    BodyFormatChoices,
    ContactPriorityChoices,
    MessageEventTypeChoices,
    MessageGranularityChoices,
    PreparedNotificationStatusChoices,
)

User = get_user_model()

__all__ = (
    "NotificationTemplate",
    "TemplateScope",
    "PreparedNotification",
    "SentNotification",
)


class NotificationTemplate(NetBoxModel):
    """
    A Jinja template for generating outgoing notifications.

    Templates can be scoped to specific objects (tenants, providers, sites, etc.)
    via TemplateScope assignments, similar to Config Contexts.
    """

    name = models.CharField(
        max_length=100,
    )
    slug = models.SlugField(
        unique=True,
    )
    description = models.TextField(
        blank=True,
    )

    # Event type targeting
    event_type = models.CharField(
        max_length=20,
        choices=MessageEventTypeChoices,
        help_text="Which event types this template applies to.",
    )

    # Generation granularity
    granularity = models.CharField(
        max_length=20,
        choices=MessageGranularityChoices,
        default=MessageGranularityChoices.PER_TENANT,
        help_text="How notifications are grouped when generated from events.",
    )

    # Content templates
    subject_template = models.TextField(
        help_text="Jinja template for the email subject line.",
    )
    body_template = models.TextField(
        help_text="Jinja template for the notification body. Supports {% block %} inheritance.",
    )
    body_format = models.CharField(
        max_length=20,
        choices=BodyFormatChoices,
        default=BodyFormatChoices.MARKDOWN,
        help_text="Format of the body template.",
    )
    css_template = models.TextField(
        blank=True,
        help_text="CSS styles for HTML output.",
    )
    headers_template = models.JSONField(
        default=dict,
        blank=True,
        help_text="Jinja templates for email headers (stored as JSON, accepts YAML input).",
    )

    # iCal (Maintenance only)
    include_ical = models.BooleanField(
        default=False,
        help_text="Whether to generate an iCal attachment (Maintenance only).",
    )
    ical_template = models.TextField(
        blank=True,
        help_text="Jinja template for iCal content (BCOP-compliant).",
    )

    # Recipient discovery
    contact_roles = models.ManyToManyField(
        to=ContactRole,
        blank=True,
        related_name="notification_templates",
        help_text="Contact roles to include when discovering recipients.",
    )
    contact_priorities = ArrayField(
        base_field=models.CharField(max_length=20, choices=ContactPriorityChoices),
        default=list,
        blank=True,
        help_text="Contact priorities to include (e.g., primary, secondary).",
    )

    # Template inheritance
    is_base_template = models.BooleanField(
        default=False,
        help_text="Whether this template can be extended by other templates.",
    )
    extends = models.ForeignKey(
        to="self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
        help_text="Parent template to extend (for Jinja block inheritance).",
    )

    # Merge weight
    weight = models.IntegerField(
        default=1000,
        help_text="Base weight for template matching (higher = wins conflicts).",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Notification Template"
        verbose_name_plural = "Notification Templates"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:notices:notificationtemplate", args=[self.pk])


class TemplateScope(models.Model):
    """
    Links a NotificationTemplate to NetBox objects for Config Context-like matching.

    When generating notifications, templates with matching scopes are selected
    and merged by weight.
    """

    template = models.ForeignKey(
        to=NotificationTemplate,
        on_delete=models.CASCADE,
        related_name="scopes",
    )

    # GenericFK to any NetBox object
    content_type = models.ForeignKey(
        to=ContentType,
        on_delete=models.CASCADE,
        help_text="The type of object this scope matches.",
    )
    object_id = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        help_text="Specific object ID (null = all of this type).",
    )
    object = GenericForeignKey("content_type", "object_id")

    # Event filtering
    event_type = models.CharField(
        max_length=20,
        choices=MessageEventTypeChoices,
        null=True,
        blank=True,
        help_text="Filter by event type.",
    )
    event_status = models.CharField(
        max_length=50,
        blank=True,
        help_text="Filter by event status (e.g., CONFIRMED, TENTATIVE).",
    )

    # Merge priority
    weight = models.IntegerField(
        default=1000,
        help_text="Weight for this scope (higher = higher priority in merge).",
    )

    class Meta:
        ordering = ["template", "-weight"]
        verbose_name = "Template Scope"
        verbose_name_plural = "Template Scopes"
        constraints = [
            models.UniqueConstraint(
                fields=["template", "content_type", "object_id", "event_type", "event_status"],
                name="unique_template_scope",
            ),
        ]

    def __str__(self):
        obj_str = str(self.object) if self.object_id else f"All {self.content_type.model}s"
        return f"{self.template.name} → {obj_str}"


class PreparedNotification(NetBoxModel):
    """
    A rendered notification ready for delivery.

    Stores a snapshot of rendered content and recipients at generation time.
    Status transitions are validated via state machine.
    """

    # Source template
    template = models.ForeignKey(
        to=NotificationTemplate,
        on_delete=models.PROTECT,
        related_name="prepared_notifications",
    )

    # Linked event (optional)
    event_content_type = models.ForeignKey(
        to=ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    event_id = models.PositiveBigIntegerField(
        null=True,
        blank=True,
    )
    event = GenericForeignKey("event_content_type", "event_id")

    # Status
    status = models.CharField(
        max_length=20,
        choices=PreparedNotificationStatusChoices,
        default=PreparedNotificationStatusChoices.DRAFT,
    )

    # Recipients
    contacts = models.ManyToManyField(
        to=Contact,
        blank=True,
        related_name="prepared_notifications",
        help_text="Contacts to receive this notification.",
    )
    recipients = models.JSONField(
        default=list,
        help_text="Readonly snapshot of recipients at send time.",
    )

    # Rendered content snapshot
    subject = models.CharField(
        max_length=255,
    )
    body_text = models.TextField()
    body_html = models.TextField(
        blank=True,
    )
    headers = models.JSONField(
        default=dict,
    )
    css = models.TextField(
        blank=True,
    )
    ical_content = models.TextField(
        blank=True,
    )

    # Approval tracking
    approved_by = models.ForeignKey(
        to=User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    # Delivery tracking
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    delivered_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    viewed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-created"]
        verbose_name = "Prepared Notification"
        verbose_name_plural = "Prepared Notifications"

    def __str__(self):
        return f"{self.subject[:50]}..." if len(self.subject) > 50 else self.subject

    def get_absolute_url(self):
        return reverse("plugins:notices:preparednotification", args=[self.pk])

    @property
    def event_type_name(self):
        """Return the event type name (maintenance/outage) or None."""
        if self.event_content_type:
            return self.event_content_type.model
        return None


class SentNotificationManager(models.Manager):
    """Manager that filters to only sent/delivered notifications."""

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(
                status__in=[
                    PreparedNotificationStatusChoices.SENT,
                    PreparedNotificationStatusChoices.DELIVERED,
                ]
            )
        )


class SentNotification(PreparedNotification):
    """Proxy model for sent/delivered notifications."""

    objects = SentNotificationManager()

    class Meta:
        proxy = True
        verbose_name = "Sent Notification"
        verbose_name_plural = "Sent Notifications"
