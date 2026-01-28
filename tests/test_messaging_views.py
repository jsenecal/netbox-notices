"""Tests for NotificationTemplate and PreparedNotification views."""

import pytest
from django.urls import reverse


class TestNotificationTemplateURLs:
    """Test NotificationTemplate URL patterns."""

    def test_list_url_exists(self):
        """Test that the list URL resolves."""
        url = reverse("plugins:notices:notificationtemplate_list")
        assert url == "/plugins/notices/notification-templates/"

    def test_add_url_exists(self):
        """Test that the add URL resolves."""
        url = reverse("plugins:notices:notificationtemplate_add")
        assert url == "/plugins/notices/notification-templates/add/"

    def test_detail_url_exists(self):
        """Test that the detail URL resolves."""
        url = reverse("plugins:notices:notificationtemplate", kwargs={"pk": 1})
        assert url == "/plugins/notices/notification-templates/1/"

    def test_edit_url_exists(self):
        """Test that the edit URL resolves."""
        url = reverse("plugins:notices:notificationtemplate_edit", kwargs={"pk": 1})
        assert url == "/plugins/notices/notification-templates/1/edit/"

    def test_delete_url_exists(self):
        """Test that the delete URL resolves."""
        url = reverse("plugins:notices:notificationtemplate_delete", kwargs={"pk": 1})
        assert url == "/plugins/notices/notification-templates/1/delete/"

    def test_changelog_url_exists(self):
        """Test that the changelog URL resolves."""
        url = reverse("plugins:notices:notificationtemplate_changelog", kwargs={"pk": 1})
        assert url == "/plugins/notices/notification-templates/1/changelog/"


class TestPreparedNotificationURLs:
    """Test PreparedNotification URL patterns."""

    def test_list_url_exists(self):
        """Test that the list URL resolves."""
        url = reverse("plugins:notices:preparednotification_list")
        assert url == "/plugins/notices/prepared-notifications/"

    def test_add_url_exists(self):
        """Test that the add URL resolves."""
        url = reverse("plugins:notices:preparednotification_add")
        assert url == "/plugins/notices/prepared-notifications/add/"

    def test_detail_url_exists(self):
        """Test that the detail URL resolves."""
        url = reverse("plugins:notices:preparednotification", kwargs={"pk": 1})
        assert url == "/plugins/notices/prepared-notifications/1/"

    def test_edit_url_exists(self):
        """Test that the edit URL resolves."""
        url = reverse("plugins:notices:preparednotification_edit", kwargs={"pk": 1})
        assert url == "/plugins/notices/prepared-notifications/1/edit/"

    def test_delete_url_exists(self):
        """Test that the delete URL resolves."""
        url = reverse("plugins:notices:preparednotification_delete", kwargs={"pk": 1})
        assert url == "/plugins/notices/prepared-notifications/1/delete/"

    def test_changelog_url_exists(self):
        """Test that the changelog URL resolves."""
        url = reverse("plugins:notices:preparednotification_changelog", kwargs={"pk": 1})
        assert url == "/plugins/notices/prepared-notifications/1/changelog/"


@pytest.mark.django_db
class TestNotificationTemplateViewPermissions:
    """Test NotificationTemplate view permissions."""

    def test_list_view_requires_permission(self, client):
        """Test that list view requires permission."""
        url = reverse("plugins:notices:notificationtemplate_list")
        response = client.get(url)
        # Without login, should redirect to login page
        assert response.status_code in (302, 403)

    def test_add_view_requires_permission(self, client):
        """Test that add view requires permission."""
        url = reverse("plugins:notices:notificationtemplate_add")
        response = client.get(url)
        assert response.status_code in (302, 403)


@pytest.mark.django_db
class TestPreparedNotificationViewPermissions:
    """Test PreparedNotification view permissions."""

    def test_list_view_requires_permission(self, client):
        """Test that list view requires permission."""
        url = reverse("plugins:notices:preparednotification_list")
        response = client.get(url)
        assert response.status_code in (302, 403)

    def test_add_view_requires_permission(self, client):
        """Test that add view requires permission."""
        url = reverse("plugins:notices:preparednotification_add")
        response = client.get(url)
        assert response.status_code in (302, 403)
