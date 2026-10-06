"""
Opt-in automatic generation of draft notifications when an event changes meaningfully.

Runs after the surrounding transaction commits, at most once per event per transaction, and
never lets a generation failure break the save that triggered it.
"""

import logging

from django.contrib.contenttypes.models import ContentType
from django.db import DEFAULT_DB_ALIAS, connections, transaction
from netbox.config import get_config

logger = logging.getLogger("notices.auto_generation")

# Event fields whose change warrants telling customers again.
MEANINGFUL_FIELDS = ("status", "start", "end", "estimated_time_to_repair")


def auto_statuses(event):
    setting = get_config().PLUGINS_CONFIG.get("notices", {}).get("auto_generate_notifications") or {}
    return setting.get(event._meta.model_name, [])


def is_meaningful_event_change(instance, created):
    if created:
        return True
    before = getattr(instance, "_prechange_snapshot", None)
    if not before:
        # Saved outside NetBox's change logging (no snapshot): we cannot tell, so assume it matters.
        return True
    after = instance.serialize_object()
    return any(before.get(name) != after.get(name) for name in MEANINGFUL_FIELDS)


class _PendingRun:
    """An on_commit callback that runs generation once for one event."""

    def __init__(self, key, model):
        self.key = key
        self.model = model
        self.done = False

    def __call__(self):
        self.done = True
        event = self.model.objects.filter(pk=self.key[1]).first()
        if event is not None and event.status in auto_statuses(event):
            run_generation(event)


def _already_queued(key):
    """True if an unrun callback for this event is waiting on the current transaction.

    The queue lives on the connection, so it is discarded together with a rolled-back
    transaction; no per-thread state can leak between transactions.
    """
    return any(
        isinstance(func, _PendingRun) and not func.done and func.key == key
        for _, func, _ in connections[DEFAULT_DB_ALIAS].run_on_commit
    )


def schedule_generation(event):
    """Queue one generation run for this event after the current transaction commits."""
    if event is None or event.pk is None or not auto_statuses(event):
        return
    key = (ContentType.objects.get_for_model(event).pk, event.pk)
    if _already_queued(key):
        return
    transaction.on_commit(_PendingRun(key, type(event)))


def run_generation(event):
    from extras.models import JournalEntry

    from notices.choices import GenerationActionChoices
    from notices.services.notification_generation import NotificationGenerator

    try:
        generator = NotificationGenerator(event)
        result = generator.apply(generator.plan())
        errors = [item.error for item in result.items if item.action == GenerationActionChoices.ERROR]
    except Exception as e:  # never break the save that triggered us
        logger.exception("Automatic notification generation failed for %s", event)
        errors = [str(e)]
    if errors:
        JournalEntry.objects.create(
            assigned_object=event,
            kind="warning",
            comments="Automatic notification generation failed:\n\n" + "\n".join(f"- {e}" for e in errors),
        )
