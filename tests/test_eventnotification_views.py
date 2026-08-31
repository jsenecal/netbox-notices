"""Rendering contract for the received-notification detail page and its tabs.

`EventNotification` stores provider email verbatim, so its detail template is the one place
untrusted HTML reaches a NetBox page. Two things are pinned: the page is a real NetBox page (not
the bare body fragment it used to be), and the body is still sanitized on the way out.

`admin_client` is pytest-django's superuser client, so responses reflect rendering, not permissions.
"""

import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils import timezone

from notices.models import EventNotification

# Distinctive markers so an assertion cannot pass on incidental page text.
SAFE_BODY = "<p>Scheduled work on link ABC-123</p>"
XSS_PAYLOAD = '<script>alert("notices-xss")</script>'
# Tabler utility classes are live on this page, so a `class` the sanitizer lets through is a
# layout primitive in the attacker's hands. `notices-overlay-probe` is a sentinel: it matches
# nothing in the NetBox chrome, so finding it proves the attribute itself survived.
OVERLAY_PAYLOAD = (
    '<div class="position-fixed top-0 start-0 w-100 h-100 bg-body notices-overlay-probe">overlay content</div>'
)


@pytest.fixture
def notification(maintenance):
    """A received email whose body carries both safe markup and a script tag."""
    return EventNotification.objects.create(
        event_content_type=ContentType.objects.get_for_model(maintenance),
        event_object_id=maintenance.pk,
        email=b"raw rfc822 message",
        email_body=f"{SAFE_BODY}{XSS_PAYLOAD}{OVERLAY_PAYLOAD}",
        subject="Planned maintenance ABC-123",
        email_from="noc@provider.example",
        email_received=timezone.now(),
    )


@pytest.fixture
def detail_body(admin_client, notification):
    """The rendered detail page, decoded."""
    response = admin_client.get(reverse("plugins:notices:eventnotification", args=[notification.pk]))
    assert response.status_code == 200
    return response.content.decode()


@pytest.mark.django_db
def test_detail_page_renders_a_full_netbox_page(detail_body):
    """The reported symptom: the page used to be a ~233 byte body fragment, no <html> at all."""
    assert "<html" in detail_body
    assert "Planned maintenance ABC-123" in detail_body
    assert "noc@provider.example" in detail_body


@pytest.mark.django_db
def test_detail_page_renders_its_tabs(detail_body, notification):
    """Navigation and tabs are half the fix -- both tabs were unreachable from the fragment."""
    for tab in ("changelog", "journal"):
        assert reverse(f"plugins:notices:eventnotification_{tab}", args=[notification.pk]) in detail_body


@pytest.mark.django_db
def test_detail_page_offers_delete_but_not_edit(detail_body, notification):
    """A captured email is not editable: `EventNotificationView.actions = (DeleteObject,)`.

    There is no `eventnotification_edit` URL to reverse, so an Edit button would not render a
    wrong path -- it would render `href="None"`. Asserted on the button's icon and on that
    symptom, since neither can be reached by matching a URL that does not exist.
    """
    assert reverse("plugins:notices:eventnotification_delete", args=[notification.pk]) in detail_body
    assert "mdi-pencil" not in detail_body
    assert 'href="None"' not in detail_body


@pytest.mark.django_db
def test_detail_page_links_the_parent_event(detail_body, maintenance):
    """The notification is only meaningful next to its event, so the event must be reachable."""
    assert maintenance.get_absolute_url() in detail_body


@pytest.mark.django_db
def test_detail_page_sanitizes_the_email_body(detail_body):
    """`sanitize_html` is what makes provider email safe to display; it must survive the rewrite.

    Asserted against the payload rather than "<script", because NetBox's own chrome ships plenty
    of script tags. Paired with the SAFE_BODY assertion, this separates `sanitize_html` from both
    `|safe` and plain autoescaping.
    """
    assert 'alert("notices-xss")' not in detail_body
    assert SAFE_BODY in detail_body


@pytest.mark.django_db
def test_detail_page_strips_layout_classes_from_the_email_body(detail_body):
    """A provider email shares the DOM with the NetBox chrome, so it must not be able to lay itself out.

    NetBox's own allow-list keeps `class` on `div`, which on a page loading Tabler is enough to
    float the email over the surrounding UI as a full-viewport overlay. The text still has to
    render -- the element is kept, only its styling hook is dropped.
    """
    assert "notices-overlay-probe" not in detail_body
    assert "overlay content" in detail_body


@pytest.mark.django_db
def test_detail_page_does_not_render_the_raw_message(detail_body):
    """`email` is a BinaryField holding the raw RFC822 message -- not page content."""
    assert "raw rfc822 message" not in detail_body


@pytest.mark.django_db
@pytest.mark.parametrize("tab", ["changelog", "journal"])
def test_tab_renders_its_own_content(admin_client, notification, tab):
    """Both tabs resolve their base template by model name, so they inherited the fragment too.

    `ObjectChangeLogView`/`ObjectJournalView` set `base_template = get_default_template(model)`.
    Extending a template with no blocks rendered that template's raw content -- the email body --
    instead of the tab's own.
    """
    response = admin_client.get(reverse(f"plugins:notices:eventnotification_{tab}", args=[notification.pk]))

    assert response.status_code == 200
    body = response.content.decode()
    assert "<html" in body
    assert SAFE_BODY not in body
