from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.urls import reverse
from netbox.models import NetBoxModel
from tenancy.models import ContactRole

from ..choices import (
    BodyFormatChoices,
    ContactPriorityChoices,
    MessageEventTypeChoices,
    MessageGranularityChoices,
)

__all__ = (
    "MessageTemplate",
    "TemplateScope",
)


class MessageTemplate(NetBoxModel):
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
        help_text="How messages are grouped when generated from events.",
    )

    # Content templates
    subject_template = models.TextField(
        help_text="Jinja template for the email subject line.",
    )
    body_template = models.TextField(
        help_text="Jinja template for the message body. Supports {% block %} inheritance.",
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
        related_name="message_templates",
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
        verbose_name = "Message Template"
        verbose_name_plural = "Message Templates"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:notices:messagetemplate", args=[self.pk])


class TemplateScope(models.Model):
    """
    Links a MessageTemplate to NetBox objects for Config Context-like matching.

    When generating messages, templates with matching scopes are selected
    and merged by weight.
    """

    template = models.ForeignKey(
        to=MessageTemplate,
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
