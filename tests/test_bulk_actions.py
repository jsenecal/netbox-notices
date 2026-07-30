"""Bulk actions: the buttons resolve to real URLs, and submitting them does the work.

Two layers, because the first alone let a 500 through.

*Resolution* asserts against `ObjectAction.get_url()` -- the code path that produced the bug. It
returns None on NoReverseMatch, and the button templates interpolate it unguarded, so a missing
URL reaches the browser as the string "None".

*Submission* covers what resolution cannot: a route that exists but whose form raises on POST,
which is how bulk edit on Prepared Notifications 500'd behind a button that reversed fine.
"""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from netbox.object_actions import BulkExport, BulkRename, CloneObject

from notices import views
from notices.choices import MessageEventTypeChoices, PreparedNotificationStatusChoices
from notices.forms import MaintenanceImportForm, OutageImportForm
from notices.models import (
    EventNotification,
    Maintenance,
    NotificationTemplate,
    Outage,
    PreparedNotification,
    SentNotification,
)

# These never render a broken button: BulkExport builds relative "?export=" links, and
# clone.html / bulk_rename.html guard on {% if url %}. All three return None for core
# NetBox models too, so a None here is not a bug.
URL_OPTIONAL_ACTIONS = {BulkExport, BulkRename, CloneObject}

# Listed explicitly, not by introspection, so a new view that forgets its tuple shows up
# as a missing test rather than silently passing.
VIEWS_WITH_EXPLICIT_ACTIONS = (
    views.MaintenanceListView,
    views.OutageListView,
    views.EventNotificationListView,
    views.NotificationTemplateListView,
    views.PreparedNotificationListView,
    views.SentNotificationListView,
    views.EventNotificationView,
    views.SentNotificationView,
)

LIST_VIEWS = (
    views.MaintenanceListView,
    views.OutageListView,
    views.EventNotificationListView,
    views.NotificationTemplateListView,
    views.PreparedNotificationListView,
    views.SentNotificationListView,
)

# URL prefix and fixture for every bulk delete view. `sentnotification` and `eventnotification`
# are deliberately absent -- neither offers bulk delete; see
# test_notification_archives_have_no_bulk_delete below.
BULK_DELETE_VIEWS = (
    ("maintenance", "maintenance"),
    ("outage", "outage"),
    ("notificationtemplate", "notification_template"),
    ("preparednotification", "prepared_notification"),
)

# Detail views, paired with the name of the fixture supplying a saved instance. Single
# object actions declare `url_kwargs = ["pk"]`, so get_url() needs a real object.
DETAIL_VIEWS = (
    (views.MaintenanceView, "maintenance"),
    (views.OutageView, "outage"),
    (views.EventNotificationView, "event_notification"),
    (views.NotificationTemplateView, "notification_template"),
    (views.PreparedNotificationView, "prepared_notification"),
    (views.SentNotificationView, "sent_notification"),
)


@pytest.fixture
def admin_user_client(db):
    """A superuser client, so every action button is rendered rather than permission-hidden."""
    get_user_model().objects.create_superuser(
        username="bulk-actions-admin",
        email="bulk-actions-admin@example.com",
        password="testpass12345",
    )
    client = Client()
    client.login(username="bulk-actions-admin", password="testpass12345")
    return client


@pytest.fixture
def outage(provider):
    """Create a test outage."""
    return Outage.objects.create(
        name="OUT-001",
        summary="Test outage",
        provider=provider,
        status="REPORTED",
        start=timezone.now(),
    )


@pytest.fixture
def event_notification(maintenance):
    """Create a received email notification attached to a maintenance."""
    return EventNotification.objects.create(
        event_content_type=ContentType.objects.get_for_model(maintenance),
        event_object_id=maintenance.pk,
        email=b"raw message",
        email_body="Test body",
        subject="Test Subject",
        email_from="noc@example.com",
        email_received=timezone.now(),
    )


@pytest.fixture
def notification_template(db):
    """Create a test notification template.

    `event_type` is required -- it has no default and is not blank -- and bulk edit runs
    `full_clean()` on every selected object, so a fixture without one cannot be bulk edited.
    """
    return NotificationTemplate.objects.create(
        name="Test Template",
        slug="test-template",
        event_type=MessageEventTypeChoices.MAINTENANCE,
        subject_template="{{ event.name }}",
        body_template="{{ event.summary }}",
    )


@pytest.fixture
def prepared_notification(notification_template, maintenance):
    """Create a draft prepared notification."""
    return PreparedNotification.objects.create(
        template=notification_template,
        event_content_type=ContentType.objects.get_for_model(maintenance),
        event_id=maintenance.pk,
        subject="Test Subject",
        body_text="Test body",
        status=PreparedNotificationStatusChoices.DRAFT,
    )


@pytest.fixture
def sent_notification(prepared_notification):
    """Create a prepared notification promoted to SENT, read back through the proxy."""
    prepared_notification.status = PreparedNotificationStatusChoices.SENT
    prepared_notification.save()
    return SentNotification.objects.get(pk=prepared_notification.pk)


@pytest.mark.django_db
@pytest.mark.parametrize("view_class", LIST_VIEWS, ids=lambda v: v.__name__)
def test_list_view_actions_resolve(view_class):
    """Every action on a list view resolves to a real URL."""
    model = view_class.queryset.model

    for action in view_class.actions:
        if action in URL_OPTIONAL_ACTIONS:
            continue
        assert action.get_url(model) is not None, (
            f"{view_class.__name__} declares {action.__name__}, but "
            f"{action.__name__}.get_url({model.__name__}) is None -- the button will "
            f'render formaction="None"'
        )


@pytest.mark.django_db
@pytest.mark.parametrize("view_class,fixture_name", DETAIL_VIEWS, ids=lambda v: getattr(v, "__name__", v))
def test_detail_view_actions_resolve(view_class, fixture_name, request):
    """Every action on a detail view resolves to a real URL for a saved instance."""
    instance = request.getfixturevalue(fixture_name)

    for action in view_class.actions:
        if action in URL_OPTIONAL_ACTIONS:
            continue
        assert action.get_url(instance) is not None, (
            f"{view_class.__name__} declares {action.__name__}, but "
            f"{action.__name__}.get_url() is None for a saved "
            f'{type(instance).__name__} -- the button will render href="None"'
        )


@pytest.mark.django_db
def test_maintenance_bulk_edit_applies_and_leaves_status_alone(admin_user_client, maintenance):
    """Submitting bulk edit must actually work, not just resolve to a URL.

    The URL-resolution guard above passes for any route that exists, including one whose form
    raises on submit -- which is how a 500 behind "Edit Selected" went unnoticed.
    """
    original_status = maintenance.status
    response = admin_user_client.post(
        reverse("plugins:notices:maintenance_bulk_edit"),
        {"pk": [maintenance.pk], "_apply": "", "internal_ticket": "INC-4242"},
    )

    assert response.status_code in (200, 302)
    maintenance.refresh_from_db()
    assert maintenance.internal_ticket == "INC-4242"
    # `status` is not on the form, so bulk edit must not be able to move it
    assert maintenance.status == original_status


@pytest.mark.django_db
def test_outage_bulk_edit_applies_and_leaves_status_alone(admin_user_client, outage):
    """`status` is off `OutageBulkEditForm` on purpose -- bulk edit must not reach it.

    `Outage.clean()` requires an `end` when the status is RESOLVED, so a bulk status change
    would succeed on some selected rows and fail on others.
    """
    original_status = outage.status
    response = admin_user_client.post(
        reverse("plugins:notices:outage_bulk_edit"),
        {"pk": [outage.pk], "_apply": "", "internal_ticket": "INC-9001"},
    )

    assert response.status_code in (200, 302)
    outage.refresh_from_db()
    assert outage.internal_ticket == "INC-9001"
    assert outage.status == original_status


@pytest.mark.django_db
def test_notification_template_bulk_edit_applies_and_leaves_slug_alone(admin_user_client, notification_template):
    """The form carries metadata only -- the unique `slug` and the Jinja bodies stay per-template."""
    original_slug = notification_template.slug
    response = admin_user_client.post(
        reverse("plugins:notices:notificationtemplate_bulk_edit"),
        {"pk": [notification_template.pk], "_apply": "", "weight": 250},
    )

    assert response.status_code in (200, 302)
    notification_template.refresh_from_db()
    assert notification_template.weight == 250
    assert notification_template.slug == original_slug


@pytest.mark.django_db
def test_prepared_notification_edit_form_cannot_set_status(admin_user_client, prepared_notification):
    """The single-object edit form must not accept `status` -- transitions are API-only.

    A ModelForm writes the column directly, so a UI-driven `draft -> ready` would leave
    `recipients` unsnapshotted and `approved_by` / `approved_at` null. The field is absent from
    `Meta.fields`, so Django ignores a posted value rather than applying it.
    """
    response = admin_user_client.post(
        reverse("plugins:notices:preparednotification_edit", args=[prepared_notification.pk]),
        {
            "template": prepared_notification.template.pk,
            "subject": prepared_notification.subject,
            "body_text": prepared_notification.body_text,
            "status": PreparedNotificationStatusChoices.READY,
        },
    )

    assert response.status_code in (200, 302)
    prepared_notification.refresh_from_db()
    assert prepared_notification.status == PreparedNotificationStatusChoices.DRAFT


@pytest.mark.django_db
@pytest.mark.parametrize("url_prefix,fixture_name", BULK_DELETE_VIEWS)
def test_bulk_delete_removes_the_object(url_prefix, fixture_name, admin_user_client, request):
    """Submitting bulk delete must actually delete, not just resolve to a URL."""
    obj = request.getfixturevalue(fixture_name)
    model, pk = type(obj), obj.pk

    response = admin_user_client.post(
        reverse(f"plugins:notices:{url_prefix}_bulk_delete"),
        {"pk": [pk], "_confirm": "", "confirm": "true"},
    )

    assert response.status_code in (200, 302)
    assert not model.objects.filter(pk=pk).exists()


@pytest.mark.django_db
def test_sent_notification_rows_are_deletable_from_the_prepared_list(admin_user_client, sent_notification):
    """Dropping bulk delete from the sent log must not strand those rows.

    The sent list is a proxy, so its own bulk delete would send `pre_delete` with
    `sender=SentNotification` and skip any PROTECTION_RULES keyed to the concrete model. The rows
    stay reachable from the Prepared Notifications list, which does honour them.
    """
    pk = sent_notification.pk

    response = admin_user_client.post(
        reverse("plugins:notices:preparednotification_bulk_delete"),
        {"pk": [pk], "_confirm": "", "confirm": "true"},
    )

    assert response.status_code in (200, 302)
    assert not PreparedNotification.objects.filter(pk=pk).exists()


@pytest.mark.parametrize("view_class", VIEWS_WITH_EXPLICIT_ACTIONS, ids=lambda v: v.__name__)
def test_view_declares_its_own_actions(view_class):
    """The view must not fall back to NetBox's default `actions`.

    Guards against someone deleting a tuple: the defaults reference bulk_import / bulk_edit /
    bulk_rename / bulk_delete URLs this plugin does not define for every model.
    """
    assert "actions" in view_class.__dict__, (
        f"{view_class.__name__} inherits NetBox's default `actions`, which reference URLs "
        f"this plugin does not define. Declare an explicit tuple."
    )


@pytest.mark.django_db
def test_maintenance_bulk_urls_resolve():
    """The three bulk URLs reported in the original issue exist."""
    from django.urls import reverse

    assert reverse("plugins:notices:maintenance_bulk_edit")
    assert reverse("plugins:notices:maintenance_bulk_delete")
    assert reverse("plugins:notices:maintenance_bulk_import")


@pytest.mark.django_db
def test_maintenance_import_rejects_end_before_start(provider):
    """An imported row is still validated by the model, not just the form."""
    start = timezone.now()
    form = MaintenanceImportForm(
        data={
            "name": "MAINT-BAD",
            "summary": "End before start",
            "provider": provider.name,
            "status": "CONFIRMED",
            "start": start.isoformat(),
            "end": (start - timedelta(hours=1)).isoformat(),
        }
    )

    assert not form.is_valid()
    assert "The end time must be after the start time." in form.errors["end"]


@pytest.mark.django_db
def test_outage_import_requires_end_when_resolved(provider):
    """`Outage.clean()` still fires on import."""
    form = OutageImportForm(
        data={
            "name": "OUT-BAD",
            "summary": "Resolved with no end",
            "provider": provider.name,
            "status": "RESOLVED",
            "start": timezone.now().isoformat(),
        }
    )

    assert not form.is_valid()
    assert "End time is required when marking outage as resolved" in form.errors["end"]


def _import_post(client, url_name, csv_text):
    """POST a CSV to a bulk import view.

    `csv_delimiter` is required: without it the form fails with "Invalid CSV delimiter" and
    imports nothing, which is indistinguishable from a broken importer.
    """
    return client.post(
        reverse(f"plugins:notices:{url_name}"),
        {"data": csv_text, "format": "csv", "csv_delimiter": ","},
    )


@pytest.mark.django_db
def test_maintenance_bulk_import_creates_the_object(admin_user_client, provider):
    """The view-level counterpart to the form test above: a good row lands in the database."""
    start = timezone.now()
    csv_text = (
        "name,summary,provider,status,start,end\n"
        f"MAINT-CSV,Imported,{provider.name},CONFIRMED,"
        f"{start.isoformat()},{(start + timedelta(hours=2)).isoformat()}\n"
    )

    response = _import_post(admin_user_client, "maintenance_bulk_import", csv_text)

    assert response.status_code in (200, 302)
    assert Maintenance.objects.filter(name="MAINT-CSV").exists()


@pytest.mark.django_db
def test_maintenance_bulk_import_rejects_end_before_start(admin_user_client, provider):
    """A row the model rejects must create nothing -- import is not a way around `clean()`.

    Assert the reported error too, not just the absence of the object: a malformed request
    also creates nothing, so "nothing was created" alone would pass for the wrong reason.
    """
    start = timezone.now()
    csv_text = (
        "name,summary,provider,status,start,end\n"
        f"MAINT-CSV-BAD,Imported,{provider.name},CONFIRMED,"
        f"{start.isoformat()},{(start - timedelta(hours=1)).isoformat()}\n"
    )

    response = _import_post(admin_user_client, "maintenance_bulk_import", csv_text)

    assert response.status_code == 200
    assert b"The end time must be after the start time." in response.content
    assert not Maintenance.objects.filter(name="MAINT-CSV-BAD").exists()


@pytest.mark.django_db
def test_outage_bulk_import_creates_the_object(admin_user_client, provider):
    """A good outage row lands in the database, with both timestamps supplied."""
    now = timezone.now()
    csv_text = (
        "name,summary,provider,status,start,reported_at\n"
        f"OUT-CSV,Imported,{provider.name},REPORTED,{now.isoformat()},{now.isoformat()}\n"
    )

    response = _import_post(admin_user_client, "outage_bulk_import", csv_text)

    assert response.status_code in (200, 302)
    assert Outage.objects.filter(name="OUT-CSV").exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "header,row,case",
    [
        ("name,summary,provider,status", "{name},Imported,{provider},REPORTED", "columns absent"),
        (
            "name,summary,provider,status,start,reported_at",
            "{name},Imported,{provider},REPORTED,,",
            "columns present but empty",
        ),
    ],
)
def test_outage_bulk_import_defaults_the_timestamps(header, row, case, admin_user_client, provider):
    """`start` and `reported_at` fall back to the model default however the CSV omits them.

    Both cases need their own fix: an absent column needs `required=False`, an empty cell needs
    `clean_start` / `clean_reported_at`, because `construct_instance` writes None for it and the
    row then dies at the database with an uncaught IntegrityError -- a 500 that rolls back the
    whole file. See the comment on `OutageImportForm`.
    """
    name = f"OUT-{case.split()[1].upper()}"
    csv_text = f"{header}\n{row.format(name=name, provider=provider.name)}\n"

    response = _import_post(admin_user_client, "outage_bulk_import", csv_text)

    assert response.status_code in (200, 302), response.content[:500]
    outage = Outage.objects.get(name=name)
    assert outage.start is not None
    assert outage.reported_at is not None


@pytest.mark.django_db
def test_outage_bulk_import_rejects_resolved_without_end(admin_user_client, provider):
    """`Outage.clean()` requires an `end` when RESOLVED, on import as anywhere else."""
    now = timezone.now()
    csv_text = (
        "name,summary,provider,status,start,reported_at\n"
        f"OUT-CSV-BAD,Imported,{provider.name},RESOLVED,{now.isoformat()},{now.isoformat()}\n"
    )

    response = _import_post(admin_user_client, "outage_bulk_import", csv_text)

    assert response.status_code == 200
    assert b"End time is required when marking outage as resolved" in response.content
    assert not Outage.objects.filter(name="OUT-CSV-BAD").exists()


@pytest.mark.django_db
@pytest.mark.parametrize("url_name", [v.__name__ for v in LIST_VIEWS])
def test_list_page_renders_no_none_urls(
    url_name,
    admin_user_client,
    maintenance,
    outage,
    event_notification,
    notification_template,
    prepared_notification,
    sent_notification,
):
    """The reported symptom, asserted against the rendered page: a missing URL reaches the
    browser as the literal string "None" (e.g. /plugins/notices/maintenance/None).

    Every list must have at least one row -- `ActionsColumn` reverses each row's action URLs
    eagerly, so an empty table renders fine while a populated one raises NoReverseMatch.
    """
    view_name = url_name.removesuffix("ListView").lower() + "_list"
    response = admin_user_client.get(reverse(f"plugins:notices:{view_name}"))

    assert response.status_code == 200
    body = response.content.decode()
    assert 'formaction="None"' not in body
    assert 'href="None"' not in body
    # A populated table renders a <tbody> row per object; an empty one renders the
    # "No results found" placeholder instead.
    assert "No results found" not in body, f"{view_name} rendered empty -- row actions untested"
