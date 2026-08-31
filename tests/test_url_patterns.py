"""URL routing contract for the plugin.

Every name below is public -- templates, `notices/navigation.py`, `linkify` columns and NetBox's
`ObjectAction` buttons resolve URLs by name, and operators bookmark the paths. The table was
captured from the routing that shipped before `urls.py` moved to `register_model_view` /
`get_model_urls`, so it doubles as proof that migration changed no URL.

Behaviour assertions, not source-text checks: `urls.py` can be rewritten in any style as long as
`reverse()` keeps returning these paths.
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import Client
from django.urls import NoReverseMatch, reverse

from notices.choices import PreparedNotificationStatusChoices
from notices.models import NotificationTemplate, PreparedNotification, SentNotification

# (url name, number of positional args, expected path)
EXPECTED_URLS = [
    ("dashboard", 0, "/plugins/notices/"),
    ("ical_maintenances", 0, "/plugins/notices/ical/maintenances.ics"),
    # Maintenance -- note the list path is singular, unlike every other model
    ("maintenance_list", 0, "/plugins/notices/maintenance/"),
    ("maintenance_add", 0, "/plugins/notices/maintenance/add/"),
    ("maintenance", 1, "/plugins/notices/maintenance/1/"),
    ("maintenance_edit", 1, "/plugins/notices/maintenance/1/edit/"),
    ("maintenance_delete", 1, "/plugins/notices/maintenance/1/delete/"),
    ("maintenance_changelog", 1, "/plugins/notices/maintenance/1/changelog/"),
    ("maintenance_calendar", 0, "/plugins/notices/maintenance/calendar/"),
    ("maintenance_bulk_edit", 0, "/plugins/notices/maintenance/edit/"),
    ("maintenance_bulk_delete", 0, "/plugins/notices/maintenance/delete/"),
    ("maintenance_bulk_import", 0, "/plugins/notices/maintenance/import/"),
    # Maintenance quick actions -- names use underscores, paths use hyphens
    ("maintenance_acknowledge", 1, "/plugins/notices/maintenance/1/acknowledge/"),
    ("maintenance_cancel", 1, "/plugins/notices/maintenance/1/cancel/"),
    ("maintenance_reschedule", 1, "/plugins/notices/maintenance/1/reschedule/"),
    ("maintenance_mark_in_progress", 1, "/plugins/notices/maintenance/1/mark-in-progress/"),
    ("maintenance_mark_completed", 1, "/plugins/notices/maintenance/1/mark-completed/"),
    # Outage
    ("outage_list", 0, "/plugins/notices/outages/"),
    ("outage_add", 0, "/plugins/notices/outages/add/"),
    ("outage", 1, "/plugins/notices/outages/1/"),
    ("outage_edit", 1, "/plugins/notices/outages/1/edit/"),
    ("outage_delete", 1, "/plugins/notices/outages/1/delete/"),
    ("outage_changelog", 1, "/plugins/notices/outages/1/changelog/"),
    ("outage_bulk_edit", 0, "/plugins/notices/outages/edit/"),
    ("outage_bulk_delete", 0, "/plugins/notices/outages/delete/"),
    ("outage_bulk_import", 0, "/plugins/notices/outages/import/"),
    # Impact -- child of an event, no list or detail view
    ("impact_add", 0, "/plugins/notices/impact/add/"),
    ("impact_edit", 1, "/plugins/notices/impact/1/edit/"),
    ("impact_delete", 1, "/plugins/notices/impact/1/delete/"),
    # EventNotification -- list is plural, per-object paths are singular
    ("eventnotification_list", 0, "/plugins/notices/notifications/"),
    ("eventnotification_add", 0, "/plugins/notices/notification/add/"),
    ("eventnotification", 1, "/plugins/notices/notification/1/"),
    ("eventnotification_delete", 1, "/plugins/notices/notification/1/delete/"),
    # NotificationTemplate
    ("notificationtemplate_list", 0, "/plugins/notices/notification-templates/"),
    ("notificationtemplate_add", 0, "/plugins/notices/notification-templates/add/"),
    ("notificationtemplate", 1, "/plugins/notices/notification-templates/1/"),
    ("notificationtemplate_edit", 1, "/plugins/notices/notification-templates/1/edit/"),
    ("notificationtemplate_delete", 1, "/plugins/notices/notification-templates/1/delete/"),
    ("notificationtemplate_changelog", 1, "/plugins/notices/notification-templates/1/changelog/"),
    ("notificationtemplate_bulk_edit", 0, "/plugins/notices/notification-templates/edit/"),
    ("notificationtemplate_bulk_delete", 0, "/plugins/notices/notification-templates/delete/"),
    # TemplateScope -- child of a template
    ("templatescope_add", 0, "/plugins/notices/template-scope/add/"),
    ("templatescope_edit", 1, "/plugins/notices/template-scope/1/edit/"),
    ("templatescope_delete", 1, "/plugins/notices/template-scope/1/delete/"),
    # PreparedNotification
    ("preparednotification_list", 0, "/plugins/notices/prepared-notifications/"),
    ("preparednotification_add", 0, "/plugins/notices/prepared-notifications/add/"),
    ("preparednotification", 1, "/plugins/notices/prepared-notifications/1/"),
    ("preparednotification_edit", 1, "/plugins/notices/prepared-notifications/1/edit/"),
    ("preparednotification_delete", 1, "/plugins/notices/prepared-notifications/1/delete/"),
    ("preparednotification_changelog", 1, "/plugins/notices/prepared-notifications/1/changelog/"),
    ("preparednotification_bulk_delete", 0, "/plugins/notices/prepared-notifications/delete/"),
    # SentNotification -- proxy over PreparedNotification, read-only
    ("sentnotification_list", 0, "/plugins/notices/sent-notifications/"),
    ("sentnotification", 1, "/plugins/notices/sent-notifications/1/"),
    ("sentnotification_changelog", 1, "/plugins/notices/sent-notifications/1/changelog/"),
]

# Registered automatically by PluginConfig.ready() -> register_models() for every model with the
# matching feature mixin. Asserted so that losing a model's detail mount point is caught here.
FEATURE_VIEW_URLS = [
    ("maintenance_journal", 1, "/plugins/notices/maintenance/1/journal/"),
    ("outage_journal", 1, "/plugins/notices/outages/1/journal/"),
    ("eventnotification_journal", 1, "/plugins/notices/notification/1/journal/"),
    ("eventnotification_changelog", 1, "/plugins/notices/notification/1/changelog/"),
    ("notificationtemplate_journal", 1, "/plugins/notices/notification-templates/1/journal/"),
    ("preparednotification_journal", 1, "/plugins/notices/prepared-notifications/1/journal/"),
    ("sentnotification_journal", 1, "/plugins/notices/sent-notifications/1/journal/"),
]


def _ids(cases):
    return [case[0] for case in cases]


@pytest.fixture
def admin_client(db):
    """A superuser client, so responses reflect routing rather than permissions."""
    get_user_model().objects.create_superuser(
        username="url-patterns-admin",
        email="url-patterns-admin@example.com",
        password="testpass12345",
    )
    client = Client()
    client.login(username="url-patterns-admin", password="testpass12345")
    return client


@pytest.fixture
def sent_and_draft_notifications(maintenance):
    """One notification the sent-notifications proxy exposes, and one it filters out."""
    template = NotificationTemplate.objects.create(
        name="URL Test Template",
        slug="url-test-template",
        subject_template="{{ event.name }}",
        body_template="{{ event.summary }}",
    )
    event_type = ContentType.objects.get_for_model(maintenance)

    def make(status, subject):
        return PreparedNotification.objects.create(
            template=template,
            event_content_type=event_type,
            event_id=maintenance.pk,
            subject=subject,
            body_text="Body",
            status=status,
        )

    sent = make(PreparedNotificationStatusChoices.SENT, "Sent")
    draft = make(PreparedNotificationStatusChoices.DRAFT, "Draft")
    return SentNotification.objects.get(pk=sent.pk), draft


@pytest.mark.parametrize("name,nargs,expected", EXPECTED_URLS, ids=_ids(EXPECTED_URLS))
def test_url_resolves_to_expected_path(name, nargs, expected):
    """Each public URL name reverses to the path it has always had."""
    assert reverse(f"plugins:notices:{name}", args=[1] * nargs) == expected


@pytest.mark.parametrize("name,nargs,expected", FEATURE_VIEW_URLS, ids=_ids(FEATURE_VIEW_URLS))
def test_feature_view_url_resolves(name, nargs, expected):
    """Changelog and journal tab views are mounted for every model that supports them."""
    assert reverse(f"plugins:notices:{name}", args=[1] * nargs) == expected


def test_no_duplicate_url_names():
    """Two patterns sharing a name makes reverse() order-dependent and dispatch ambiguous.

    `register_model_view` has no unregister API, so hand-writing a path that a registration also
    produces is a real and silent hazard.
    """
    from notices import urls

    names = []

    def collect(patterns):
        for pattern in patterns:
            if hasattr(pattern, "url_patterns"):
                collect(pattern.url_patterns)
            elif getattr(pattern, "name", None):
                names.append(pattern.name)

    collect(urls.urlpatterns)

    duplicates = sorted({name for name in names if names.count(name) > 1})
    assert not duplicates, f"URL names defined more than once: {duplicates}"


@pytest.mark.django_db
def test_sentnotification_changelog_is_scoped_to_the_proxy(admin_client, sent_and_draft_notifications):
    """The sent changelog resolves against SentNotification, not its concrete parent.

    Behaviour change from the `get_model_urls` migration: the hand-declared route carried
    `kwargs={"model": PreparedNotification}` and served drafts too. The auto-registered one uses
    the proxy's filtered manager, matching what `SentNotificationView` already did.
    """
    sent, draft = sent_and_draft_notifications

    assert admin_client.get(reverse("plugins:notices:sentnotification_changelog", args=[sent.pk])).status_code == 200
    assert admin_client.get(reverse("plugins:notices:sentnotification_changelog", args=[draft.pk])).status_code == 404


def test_impact_has_no_detail_view():
    """Impact is reached through its parent event; it has no detail page.

    `Impact.get_absolute_url()` used to reverse this name for an orphaned impact and raise
    NoReverseMatch; it now falls back to the parent type's list. Pinned so nothing reverses it
    again -- see `TestImpactMethods.test_get_absolute_url_with_orphaned_maintenance`.
    """
    with pytest.raises(NoReverseMatch):
        reverse("plugins:notices:impact", args=[1])


def test_prepared_notification_has_no_bulk_edit():
    """`status` was the only bulk-editable field, and bulk edit cannot apply a transition.

    `BulkEditView._update_objects` does `setattr` + `full_clean()` + `save()` and never calls
    `PreparedNotificationStateMachine.transition_to()`, so a bulk `draft -> ready` would skip the
    recipient snapshot, the "no recipients" guard and the timestamps. Not cosmetic: the outbound
    SES Lambda polls on `status=ready` and would retry an unsendable notification forever. The
    view is unmounted rather than left as a trap; status is owned by the REST API.
    """
    with pytest.raises(NoReverseMatch):
        reverse("plugins:notices:preparednotification_bulk_edit")


@pytest.mark.parametrize("name", ["eventnotification_bulk_delete", "sentnotification_bulk_delete"])
def test_notification_archives_have_no_bulk_delete(name):
    """Bulk actions exist only where the model is a plain record. Pinned so nothing re-adds a URL
    without revisiting the reasons.

    Received notifications: `BulkDeleteView` never calls `table.configure()`, so its confirmation
    table is unpaginated and every selected row loads the full `email` BinaryField (raw MIME).
    They stay deletable one row at a time via `eventnotification_delete`.

    Sent notifications are a proxy: `pre_delete` fires with `sender=SentNotification`, so a
    PROTECTION_RULE keyed to `notices.preparednotification` is skipped on that path alone. There
    is no `sentnotification_delete` either -- the log is read-only, and those rows are deleted
    from the Prepared Notifications list.
    """
    with pytest.raises(NoReverseMatch):
        reverse(f"plugins:notices:{name}")


@pytest.mark.parametrize("name", ["impact_changelog", "impact_journal"])
def test_impact_has_no_feature_tabs(name):
    """Impact is the one model here whose changelog and journal tabs are deliberately unmounted.

    `register_models()` gives every NetBoxModel both, and both render through
    `generic/object.html`, which builds a breadcrumb from the model's list URL -- Impact has
    neither a list nor a detail view, so the tab 500s. Nothing is lost:
    `Impact.to_objectchange()` files changes against the parent event.
    """
    with pytest.raises(NoReverseMatch):
        reverse(f"plugins:notices:{name}", args=[1])
