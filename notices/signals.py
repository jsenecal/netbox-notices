"""Signal handlers for the notices plugin."""

from circuits.models import Circuit, CircuitTermination
from dcim.models import Device, PowerFeed, PowerPanel, Site
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .choices import MaintenanceTypeChoices
from .models import Impact, Maintenance


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
# IMPORTANT: this list of handlers maps 1:1 to the default resolver registry.
# Anyone registering a resolver for a new content type via
# notices.resolvers.register_site_resolver MUST also wire equivalent signals
# for any upstream model whose change would affect that target's site, or the
# cache will silently drift.
# ---------------------------------------------------------------------------


@receiver(post_save, sender=Impact)
def _impact_refresh_on_save(sender, instance, **kwargs):
    """Recompute this impact's own site/location cache after save."""
    instance.refresh_sites()


def _refresh_impacts_for(target):
    """Refresh every Impact pointing at ``target`` (by content type + pk)."""
    if target is None or target.pk is None:
        return
    ct = ContentType.objects.get_for_model(type(target))
    for impact in Impact.objects.filter(target_content_type=ct, target_object_id=target.pk):
        impact.refresh_sites()


@receiver(post_save, sender=Site)
@receiver(post_delete, sender=Site)
def _site_changed(sender, instance, **kwargs):
    # Impacts targeting the Site itself just need re-pointing; the membership
    # is the site itself, so refresh_sites() will reassert it. Mainly useful
    # to clear membership on delete (but cascading FK already handles that).
    _refresh_impacts_for(instance)


@receiver(post_save, sender=Device)
def _device_changed(sender, instance, **kwargs):
    _refresh_impacts_for(instance)


@receiver(post_save, sender=PowerFeed)
def _powerfeed_changed(sender, instance, **kwargs):
    _refresh_impacts_for(instance)


@receiver(post_save, sender=PowerPanel)
def _powerpanel_changed(sender, instance, **kwargs):
    """A PowerPanel's site/location change cascades to every PowerFeed on it."""
    if instance.pk is None:
        return
    feed_ct = ContentType.objects.get_for_model(PowerFeed)
    feed_ids = list(PowerFeed.objects.filter(power_panel_id=instance.pk).values_list("pk", flat=True))
    if not feed_ids:
        return
    for impact in Impact.objects.filter(target_content_type=feed_ct, target_object_id__in=feed_ids):
        impact.refresh_sites()


@receiver(post_save, sender=Circuit)
def _circuit_changed(sender, instance, **kwargs):
    _refresh_impacts_for(instance)


@receiver(post_save, sender=CircuitTermination)
@receiver(post_delete, sender=CircuitTermination)
def _circuit_termination_changed(sender, instance, **kwargs):
    """A termination's site/location change reflects on its parent Circuit's cache."""
    circuit_id = getattr(instance, "circuit_id", None)
    if not circuit_id:
        return
    circuit_ct = ContentType.objects.get_for_model(Circuit)
    for impact in Impact.objects.filter(target_content_type=circuit_ct, target_object_id=circuit_id):
        impact.refresh_sites()
