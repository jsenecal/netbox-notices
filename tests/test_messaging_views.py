"""Tests for MessageTemplate and PreparedMessage views."""

import pytest
from django.urls import reverse


class TestMessageTemplateURLs:
    """Test MessageTemplate URL patterns."""

    def test_list_url_exists(self):
        """Test that the list URL resolves."""
        url = reverse("plugins:notices:messagetemplate_list")
        assert url == "/plugins/notices/message-templates/"

    def test_add_url_exists(self):
        """Test that the add URL resolves."""
        url = reverse("plugins:notices:messagetemplate_add")
        assert url == "/plugins/notices/message-templates/add/"

    def test_detail_url_exists(self):
        """Test that the detail URL resolves."""
        url = reverse("plugins:notices:messagetemplate", kwargs={"pk": 1})
        assert url == "/plugins/notices/message-templates/1/"

    def test_edit_url_exists(self):
        """Test that the edit URL resolves."""
        url = reverse("plugins:notices:messagetemplate_edit", kwargs={"pk": 1})
        assert url == "/plugins/notices/message-templates/1/edit/"

    def test_delete_url_exists(self):
        """Test that the delete URL resolves."""
        url = reverse("plugins:notices:messagetemplate_delete", kwargs={"pk": 1})
        assert url == "/plugins/notices/message-templates/1/delete/"

    def test_changelog_url_exists(self):
        """Test that the changelog URL resolves."""
        url = reverse("plugins:notices:messagetemplate_changelog", kwargs={"pk": 1})
        assert url == "/plugins/notices/message-templates/1/changelog/"


class TestPreparedMessageURLs:
    """Test PreparedMessage URL patterns."""

    def test_list_url_exists(self):
        """Test that the list URL resolves."""
        url = reverse("plugins:notices:preparedmessage_list")
        assert url == "/plugins/notices/prepared-messages/"

    def test_add_url_exists(self):
        """Test that the add URL resolves."""
        url = reverse("plugins:notices:preparedmessage_add")
        assert url == "/plugins/notices/prepared-messages/add/"

    def test_detail_url_exists(self):
        """Test that the detail URL resolves."""
        url = reverse("plugins:notices:preparedmessage", kwargs={"pk": 1})
        assert url == "/plugins/notices/prepared-messages/1/"

    def test_edit_url_exists(self):
        """Test that the edit URL resolves."""
        url = reverse("plugins:notices:preparedmessage_edit", kwargs={"pk": 1})
        assert url == "/plugins/notices/prepared-messages/1/edit/"

    def test_delete_url_exists(self):
        """Test that the delete URL resolves."""
        url = reverse("plugins:notices:preparedmessage_delete", kwargs={"pk": 1})
        assert url == "/plugins/notices/prepared-messages/1/delete/"

    def test_changelog_url_exists(self):
        """Test that the changelog URL resolves."""
        url = reverse("plugins:notices:preparedmessage_changelog", kwargs={"pk": 1})
        assert url == "/plugins/notices/prepared-messages/1/changelog/"


@pytest.mark.django_db
class TestMessageTemplateViewPermissions:
    """Test MessageTemplate view permissions."""

    def test_list_view_requires_permission(self, client):
        """Test that list view requires permission."""
        url = reverse("plugins:notices:messagetemplate_list")
        response = client.get(url)
        # Without login, should redirect to login page
        assert response.status_code in (302, 403)

    def test_add_view_requires_permission(self, client):
        """Test that add view requires permission."""
        url = reverse("plugins:notices:messagetemplate_add")
        response = client.get(url)
        assert response.status_code in (302, 403)


@pytest.mark.django_db
class TestPreparedMessageViewPermissions:
    """Test PreparedMessage view permissions."""

    def test_list_view_requires_permission(self, client):
        """Test that list view requires permission."""
        url = reverse("plugins:notices:preparedmessage_list")
        response = client.get(url)
        assert response.status_code in (302, 403)

    def test_add_view_requires_permission(self, client):
        """Test that add view requires permission."""
        url = reverse("plugins:notices:preparedmessage_add")
        response = client.get(url)
        assert response.status_code in (302, 403)
