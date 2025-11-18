"""Signal handlers for the notices plugin."""

from django.db.models.signals import post_save
from django.dispatch import receiver

from .choices import MaintenanceTypeChoices
from .models import Maintenance


@receiver(post_save, sender=Maintenance)
def update_replaced_maintenance_status(sender, instance, created, **kwargs):
    """
    When a new maintenance is created with a 'replaces' field,
    automatically update the original maintenance status to RE-SCHEDULED.
    """
    if created and instance.replaces:
        # Update the replaced maintenance to RE-SCHEDULED status
        # Use save() instead of update() to trigger changelog
        original_maintenance = instance.replaces
        original_maintenance.status = MaintenanceTypeChoices.STATUS_RESCHEDULED
        original_maintenance.save()
