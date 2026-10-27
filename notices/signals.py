"""Signal handlers for the notices plugin."""

from circuits.models import Circuit, CircuitTermination
from dcim.models import Device, Location, PowerFeed, PowerPanel, Rack, Site
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .auto_generation import schedule_generation, schedule_if_meaningful
from .choices import MaintenanceTypeChoices
from .models import Impact, Maintenance, Outage


@receiver(post_save, sender=Maintenance)
def update_replaced_maintenance_status(sender, instance, created, **kwargs):
    """
    When a new maintenance is created with a 'replaces' field,
    automatically update the original maintenance status to RE-SCHEDULED.
    """
    if created and instance.replaces:
        # Update the replaced maintenance to RE-SCHEDULED status
        original_maintenance = instance.replaces

        # Take a snapshot before modification for proper changelog tracking
        original_maintenance.snapshot()

        # Update status and save to trigger changelog
        original_maintenance.status = MaintenanceTypeChoices.STATUS_RESCHEDULED
        original_maintenance.save()


# ---------------------------------------------------------------------------
# Impact site/location cache maintenance.
#
# `Impact.sites` and `Impact.locations` are caches derived from `target` via
# the resolver registry. Each handler below answers "given that THIS upstream
# object changed, which impacts need their cache rebuilt?" and calls
# refresh_sites() on each.
#
# IMPORTANT: the handlers must cover every model whose change alters a
# resolver's answer: the targets themselves and the models a site change
# cascades through (docs/developer/resolvers.md, "Keeping the cache fresh").
# Anyone registering a resolver for a new content type via
# notices.resolvers.register_site_resolver MUST also wire equivalent signals,
# or the cache will silently drift.
# ---------------------------------------------------------------------------


@receiver(post_save, sender=Impact)
def _impact_refresh_on_save(sender, instance, **kwargs):
    """Recompute this impact's own site/location cache after save."""
    instance.refresh_sites()


def _refresh_impacts_on(model, pks):
    """Refresh every Impact targeting a ``model`` instance whose pk is in ``pks`` (an iterable or a pk queryset)."""
    ct = ContentType.objects.get_for_model(model)
    for impact in Impact.objects.filter(target_content_type=ct, target_object_id__in=pks):
        impact.refresh_sites()


def _refresh_impacts_for(target):
    """Refresh every Impact pointing at ``target`` (by content type + pk)."""
    if target is None or target.pk is None:
        return
    _refresh_impacts_on(type(target), [target.pk])


def _refresh_power_panel_impacts(panel_pks):
    """Refresh impacts on the given panels and on every PowerFeed they carry."""
    _refresh_impacts_on(PowerPanel, panel_pks)
    _refresh_impacts_on(PowerFeed, PowerFeed.objects.filter(power_panel_id__in=panel_pks).values("pk"))


@receiver(post_save, sender=Site)
@receiver(post_delete, sender=Site)
def _site_changed(sender, instance, **kwargs):
    # Impacts targeting the Site itself just need re-pointing; the membership
    # is the site itself, so refresh_sites() will reassert it. Mainly useful
    # to clear membership on delete (but cascading FK already handles that).
    _refresh_impacts_for(instance)


@receiver(post_save, sender=Circuit)
@receiver(post_save, sender=Device)
@receiver(post_save, sender=PowerFeed)
def _target_changed(sender, instance, **kwargs):
    """The target's own site/location may have changed."""
    _refresh_impacts_for(instance)


@receiver(post_save, sender=Location)
def _location_changed(sender, instance, created, raw=False, **kwargs):
    """
    Refresh impacts on the location and on everything NetBox moves with it.

    NetBox's own Location post_save handler (connected by dcim, before this one) cascades a site
    change to the descendant locations, racks, devices and power panels with queryset update(),
    which fires no signals, so those impacts are refreshed here rather than by their own handlers.
    """
    if created or raw:
        return
    location_pks = list(instance.get_descendants(include_self=True).values_list("pk", flat=True))
    _refresh_impacts_on(Location, location_pks)
    _refresh_impacts_on(Device, Device.objects.filter(location_id__in=location_pks).values("pk"))
    _refresh_power_panel_impacts(PowerPanel.objects.filter(location_id__in=location_pks).values("pk"))


@receiver(post_save, sender=Rack)
def _rack_changed(sender, instance, created, raw=False, **kwargs):
    """NetBox moves a rack's devices with queryset update() (no signals); refresh their impacts."""
    if created or raw:
        return
    _refresh_impacts_on(Device, Device.objects.filter(rack_id=instance.pk).values("pk"))


@receiver(post_save, sender=PowerPanel)
def _powerpanel_changed(sender, instance, **kwargs):
    """A PowerPanel's site/location change refreshes its own impacts and cascades to every PowerFeed on it."""
    if instance.pk is None:
        return
    _refresh_power_panel_impacts([instance.pk])


@receiver(post_save, sender=CircuitTermination)
@receiver(post_delete, sender=CircuitTermination)
def _circuit_termination_changed(sender, instance, **kwargs):
    """A termination's site/location change reflects on its parent Circuit's cache."""
    circuit_id = getattr(instance, "circuit_id", None)
    if not circuit_id:
        return
    _refresh_impacts_on(Circuit, [circuit_id])


@receiver(post_save, sender=Maintenance)
@receiver(post_save, sender=Outage)
def _auto_generate_on_event_save(sender, instance, created, **kwargs):
    """Queue opt-in automatic notification generation when an event changes meaningfully."""
    schedule_if_meaningful(instance, created)


@receiver(post_save, sender=Impact)
@receiver(post_delete, sender=Impact)
def _auto_generate_on_impact_change(sender, instance, **kwargs):
    """An impact added or removed changes who must be notified."""
    schedule_generation(instance.event)
