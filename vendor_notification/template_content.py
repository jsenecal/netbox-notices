from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from netbox.plugins import PluginTemplateExtension

from .models import Impact, Maintenance, Outage


def add_impact_button(instance):
    """
    Add 'Add Impact' button to Maintenance and Outage detail pages.
    Pre-fills event content type and object ID via URL parameters.

    Args:
        instance: Maintenance or Outage instance

    Returns:
        HTML string with button linking to Impact creation form
    """
    ct = ContentType.objects.get_for_model(instance)
    url = f"{reverse('plugins:vendor_notification:impact_add')}?event_content_type={ct.pk}&event_object_id={instance.pk}"
    return f'''
    <div class="card">
        <div class="card-body">
            <h5 class="card-title">Impacts</h5>
            <p class="card-text">Add affected objects for this event.</p>
            <a href="{url}" class="btn btn-sm btn-primary">
                <i class="mdi mdi-plus-thick"></i> Add Impact
            </a>
        </div>
    </div>
    '''


class CircuitMaintenanceList(PluginTemplateExtension):
    models = ("circuits.circuit",)

    def left_page(self):
        circuit_ct = ContentType.objects.get_for_model(self.context["object"])

        return self.render(
            "vendor_notification/maintenance_include.html",
            extra_context={
                "impacts": Impact.objects.filter(
                    target_content_type=circuit_ct,
                    target_object_id=self.context["object"].pk,
                    event_content_type__model__in=["maintenance", "outage"],
                )
                .select_related("event_content_type")
                .prefetch_related("event"),
            },
        )


class ProviderMaintenanceList(PluginTemplateExtension):
    models = ("circuits.provider",)

    def left_page(self):
        return self.render(
            "vendor_notification/provider_include.html",
            extra_context={
                "maintenances": Maintenance.objects.filter(
                    provider=self.context["object"],
                    status__in=[
                        "TENTATIVE",
                        "CONFIRMED",
                        "IN-PROCESS",
                        "RE-SCHEDULED",
                        "UNKNOWN",
                    ],
                ),
                "outages": Outage.objects.filter(
                    provider=self.context["object"],
                    status__in=[
                        "IN-PROCESS",
                        "UNKNOWN",
                    ],
                ),
            },
        )


class SiteMaintenanceList(PluginTemplateExtension):
    models = ("dcim.site",)

    def left_page(self):
        site_ct = ContentType.objects.get_for_model(self.context["object"])

        return self.render(
            "vendor_notification/provider_include.html",
            extra_context={
                "impacts": Impact.objects.filter(
                    target_content_type=site_ct,
                    target_object_id=self.context["object"].pk,
                    event_content_type__model__in=["maintenance", "outage"],
                )
                .select_related("event_content_type")
                .prefetch_related("event"),
            },
        )


class MaintenanceImpactButton(PluginTemplateExtension):
    models = ("vendor_notification.maintenance",)

    def right_page(self):
        return add_impact_button(self.context["object"])


class OutageImpactButton(PluginTemplateExtension):
    models = ("vendor_notification.outage",)

    def right_page(self):
        return add_impact_button(self.context["object"])


template_extensions = [
    CircuitMaintenanceList,
    ProviderMaintenanceList,
    SiteMaintenanceList,
    MaintenanceImpactButton,
    OutageImpactButton,
]
