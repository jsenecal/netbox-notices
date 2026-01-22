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

__all__ = ("MessageTemplate",)


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
