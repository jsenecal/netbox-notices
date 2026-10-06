"""
Turn a Maintenance or Outage into draft PreparedNotifications.

plan() is side-effect free so the same code drives the UI preview, the API dry run and auto
mode; apply() writes a plan in one transaction.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from types import SimpleNamespace

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db import transaction

from notices.choices import GenerationActionChoices as Action
from notices.choices import PreparedNotificationStatusChoices as Status
from notices.services.ical_generation import generate_ical
from notices.services.recipient_discovery import RecipientGroup, contacts_for_tenants, group_impacts
from notices.services.template_matching import (
    TemplateMatchingService,
    kinds_for_event,
    merge_templates,
    resolve_chain,
)
from notices.services.template_renderer import TemplateRenderer, TemplateRenderError, split_body

__all__ = ("GenerationResult", "NotificationGenerator", "PlannedNotification", "notifications_for_event")

SUBJECT_MAX_LENGTH = 255

_PAST_TENSE = {
    Action.CREATE: "created",
    Action.UPDATE: "updated",
    Action.KEEP: "kept",
    Action.DELETE: "deleted",
    Action.SKIP: "skipped",
    Action.ERROR: "failed",
}


_PLANNED = {
    Action.CREATE: "to create",
    Action.UPDATE: "to update",
    Action.KEEP: "to keep",
    Action.DELETE: "to delete",
    Action.SKIP: "to skip",
    Action.ERROR: "failing",
}


@dataclass
class PlannedNotification:
    """What one generation run intends to do for one recipient group."""

    action: str
    root_template: object
    template: object = None
    tenant: object = None
    impact: object = None
    contacts: list = field(default_factory=list)
    content: dict = field(default_factory=dict)
    existing: object = None
    error: str = None
    notification: object = None


@dataclass
class GenerationResult:
    items: list
    counts: dict
    planned: bool = False

    @classmethod
    def from_plan(cls, plan, planned=True):
        """Count a plan's actions; `planned` marks a result that was not applied (dry run)."""
        return cls(items=plan, counts=dict(Counter(item.action for item in plan)), planned=planned)

    def summary(self):
        words = _PLANNED if self.planned else _PAST_TENSE
        parts = [f"{count} {words[action]}" for action, count in self.counts.items() if count]
        return ", ".join(parts) or "Nothing to generate"


def _group_key(root_pk, tenant, impact):
    return (root_pk, getattr(tenant, "pk", None), getattr(impact, "pk", None))


def notifications_for_event(event):
    from notices.models import PreparedNotification

    return PreparedNotification.objects.filter(
        event_content_type=ContentType.objects.get_for_model(event), event_id=event.pk
    ).select_related("template__extends", "tenant", "impact")


def _delete_item(notification):
    return PlannedNotification(
        Action.DELETE,
        notification.template.root_kind,
        notification.template,
        notification.tenant,
        notification.impact,
        existing=notification,
    )


class NotificationGenerator:
    def __init__(self, event, templates=None):
        self.event = event
        self.templates = list(templates) if templates is not None else None

    def applicable_kinds(self):
        return kinds_for_event(self.event)

    def plan(self):
        kinds = self.templates if self.templates is not None else list(self.applicable_kinds())
        existing = self._existing_by_group({kind.pk for kind in kinds})
        items = []
        for root in kinds:
            for group in group_impacts(self.event, root.granularity):
                matcher = TemplateMatchingService(event=self.event, tenant=group.tenant)
                if matcher.score(root) is None:
                    continue  # this kind does not apply to this group; leftovers handled below
                siblings = existing.pop(_group_key(root.pk, group.tenant, group.impact), [])
                items += self._plan_group(root, group, matcher, siblings)
        # Groups that no longer exist (or no longer match): drop their untouched drafts.
        for siblings in existing.values():
            items += [_delete_item(n) for n in siblings if n.status == Status.DRAFT and not n.is_modified]
        return items

    @transaction.atomic
    def apply(self, plan, user=None):
        """Write a plan. With `user`, every write must be allowed by that user's object permissions.

        A violation raises PermissionDenied and rolls the whole run back; `user=None` skips the checks.
        """
        from notices.models import PreparedNotification

        def require(obj, action):
            if user is not None and not PreparedNotification.objects.restrict(user, action).filter(pk=obj.pk).exists():
                raise PermissionDenied(f"You do not have permission to {action} this notification.")

        for item in plan:
            if item.action == Action.DELETE:
                require(item.existing, "delete")
                item.existing.delete()
                continue
            if item.action == Action.CREATE:
                item.notification = PreparedNotification(
                    template=item.template,
                    event=self.event,
                    tenant=item.tenant,
                    impact=item.impact,
                    status=Status.DRAFT,
                    **item.content,
                )
            elif item.action == Action.UPDATE:
                item.notification = item.existing
                item.notification.snapshot()
                item.notification.template = item.template
                for name, value in item.content.items():
                    setattr(item.notification, name, value)
            else:
                continue
            # No full_clean(): it would try to validate the database-generated content_hash.
            item.notification.save()
            require(item.notification, "add" if item.action == Action.CREATE else "change")
            item.notification.contacts.set(item.contacts)
            item.notification.mark_rendered()
        return GenerationResult.from_plan(plan, planned=False)

    def reset(self, notification, user=None):
        """Re-render one draft from its template family, event and group, discarding edits."""
        if notification.status != Status.DRAFT or notification.event is None:
            raise ValueError("Only drafts linked to an event can be reset.")
        root = notification.template.root_kind
        group = self._group_for(notification, root.granularity)
        matcher = TemplateMatchingService(event=self.event, tenant=group.tenant)
        siblings = [
            n
            for n in notifications_for_event(self.event)
            if n.template.root_kind.pk == root.pk
            and (n.tenant_id, n.impact_id) == (notification.tenant_id, notification.impact_id)
        ]
        item = self._render_item(root, group, matcher, sent_count=self._sent_count(siblings), require_contacts=False)
        if item.action == Action.ERROR:
            raise TemplateRenderError(item.error)
        item.action, item.existing = Action.UPDATE, notification
        self.apply([item], user=user)
        return notification

    # -- internals --------------------------------------------------------------------------

    def _existing_by_group(self, root_pks):
        by_group = defaultdict(list)
        # Notifications without a rendered_hash were created by hand, not by the generator, so
        # they belong to no recipient group and must never be updated, kept or deleted.
        for n in notifications_for_event(self.event).exclude(rendered_hash=""):
            root = n.template.root_kind
            if root.pk in root_pks:
                by_group[_group_key(root.pk, n.tenant, n.impact)].append(n)
        return by_group

    @staticmethod
    def _sent_count(siblings):
        return sum(1 for n in siblings if n.status != Status.DRAFT)

    def _plan_group(self, root, group, matcher, siblings):
        drafts = [n for n in siblings if n.status == Status.DRAFT]
        untouched = [n for n in drafts if not n.is_modified]
        item = self._render_item(root, group, matcher, sent_count=self._sent_count(siblings))
        if item.action == Action.SKIP:
            # Nobody to notify any more: untouched drafts for this group are stale.
            return [item] + [_delete_item(n) for n in untouched]
        if item.action == Action.ERROR:
            return [item]
        modified = [n for n in drafts if n.is_modified]
        if modified:
            item.action, item.existing = Action.KEEP, modified[0]
            return [item]
        if untouched:
            item.action, item.existing = Action.UPDATE, untouched[0]
            return [item] + [_delete_item(n) for n in untouched[1:]]
        return [item]

    def _render_item(self, root, group, matcher, sent_count, require_contacts=True):
        chain = resolve_chain(root, matcher)
        config = merge_templates(chain)
        item = PlannedNotification(Action.CREATE, root, chain[0], group.tenant, group.impact)
        item.contacts = contacts_for_tenants(group.tenants, config["contact_roles"], config["contact_priorities"])
        if require_contacts and not item.contacts:
            item.action = Action.SKIP
            return item
        impacts = list(group.impacts)
        try:
            context = TemplateRenderer.build_context(chain[0], event=self.event, tenant=group.tenant, impacts=impacts)
            renderer = TemplateRenderer.for_chain(chain)
            body_text, body_html = split_body(config["body_format"], renderer.render_body(chain, context))
            ical_source = SimpleNamespace(include_ical=config["include_ical"], ical_template=config["ical_template"])
            item.content = {
                "subject": renderer.render(config["subject_template"], context)[:SUBJECT_MAX_LENGTH],
                "body_text": body_text,
                "body_html": body_html,
                "headers": {k: renderer.render(v, context) for k, v in config["headers_template"].items()},
                "css": renderer.render(config["css_template"], context) if config["css_template"] else "",
                "ical_content": generate_ical(
                    ical_source, self.event, tenant=group.tenant, impacts=impacts, message_sequence=sent_count + 1
                )
                or "",
            }
        except TemplateRenderError as e:
            item.action, item.error = Action.ERROR, str(e)
        return item

    def _group_for(self, notification, granularity):
        for group in group_impacts(self.event, granularity):
            if (getattr(group.tenant, "pk", None), getattr(group.impact, "pk", None)) == (
                notification.tenant_id,
                notification.impact_id,
            ):
                return group
        tenant = notification.tenant
        return RecipientGroup(tenant=tenant, impact=notification.impact, tenants=(tenant,) if tenant else ())
