from django.contrib.contenttypes.models import ContentType
from netbox.plugins import PluginTemplateExtension

from .models import Impact, Maintenance, Outage


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


template_extensions = [
    CircuitMaintenanceList,
    ProviderMaintenanceList,
    SiteMaintenanceList,
]
