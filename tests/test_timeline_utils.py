from unittest.mock import Mock

from notices.timeline_utils import (
    build_timeline_item,
    categorize_change,
    get_category_color,
    get_category_icon,
    get_field_display_name,
)


class TestFieldDisplayNames:
    def test_get_field_display_name_maps_known_fields(self):
        assert get_field_display_name("name") == "Event ID"
        assert get_field_display_name("status") == "Status"
        assert get_field_display_name("start") == "Start Time"
        assert get_field_display_name("acknowledged") == "Acknowledged"

    def test_get_field_display_name_handles_unknown_fields(self):
        # Should return titlecased field name with underscores replaced
        assert get_field_display_name("unknown_field") == "Unknown Field"
        assert get_field_display_name("custom") == "Custom"


class TestCategorizeChange:
    def test_categorize_status_change(self):
        """Status changes should be categorized as 'status'"""
        prechange = {"status": "TENTATIVE", "acknowledged": False}
        postchange = {"status": "CONFIRMED", "acknowledged": False}

        category = categorize_change(
            changed_object_model="maintenance",
            action="update",
            prechange_data=prechange,
            postchange_data=postchange,
        )

        assert category == "status"

    def test_categorize_acknowledgment_change(self):
        """Acknowledgment changes should be categorized as 'acknowledgment'"""
        prechange = {"status": "CONFIRMED", "acknowledged": False}
        postchange = {"status": "CONFIRMED", "acknowledged": True}

        category = categorize_change(
            changed_object_model="maintenance",
            action="update",
            prechange_data=prechange,
            postchange_data=postchange,
        )

        assert category == "acknowledgment"

    def test_categorize_time_change(self):
        """Time field changes should be categorized as 'time'"""
        prechange = {"start": "2025-01-01T10:00:00Z", "status": "CONFIRMED"}
        postchange = {"start": "2025-01-01T11:00:00Z", "status": "CONFIRMED"}

        category = categorize_change(
            changed_object_model="maintenance",
            action="update",
            prechange_data=prechange,
            postchange_data=postchange,
        )

        assert category == "time"

    def test_categorize_impact_create(self):
        """Impact object creation should be categorized as 'impact'"""
        category = categorize_change(
            changed_object_model="impact",
            action="create",
            prechange_data=None,
            postchange_data={"impact": "OUTAGE"},
        )

        assert category == "impact"

    def test_categorize_notification_create(self):
        """Notification creation should be categorized as 'notification'"""
        category = categorize_change(
            changed_object_model="eventnotification",
            action="create",
            prechange_data=None,
            postchange_data={"subject": "Maintenance notice"},
        )

        assert category == "notification"

    def test_categorize_standard_change(self):
        """Other changes should be categorized as 'standard'"""
        prechange = {"comments": "Old comment"}
        postchange = {"comments": "New comment"}

        category = categorize_change(
            changed_object_model="maintenance",
            action="update",
            prechange_data=prechange,
            postchange_data=postchange,
        )

        assert category == "standard"


class TestIconAndColorMapping:
    def test_get_icon_for_status(self):
        # Default status icon without status_value
        assert get_category_icon("status") == "check-circle"

    def test_get_icon_for_status_cancelled(self):
        # Cancelled status should return x-circle icon
        assert get_category_icon("status", "CANCELLED") == "x-circle"

    def test_get_icon_for_status_confirmed(self):
        # Other statuses should return check-circle icon
        assert get_category_icon("status", "CONFIRMED") == "check-circle"

    def test_get_icon_for_status_completed(self):
        assert get_category_icon("status", "COMPLETED") == "check-circle"

    def test_get_icon_for_impact(self):
        assert get_category_icon("impact") == "alert-triangle"

    def test_get_icon_for_notification(self):
        assert get_category_icon("notification") == "mail"

    def test_get_icon_for_acknowledgment(self):
        assert get_category_icon("acknowledgment") == "check"

    def test_get_icon_for_time(self):
        assert get_category_icon("time") == "clock"

    def test_get_icon_for_standard(self):
        assert get_category_icon("standard") == "circle"

    def test_get_color_for_status(self):
        # Status color comes from status value, returns default for testing
        assert get_category_color("status") == "secondary"

    def test_get_color_for_impact(self):
        assert get_category_color("impact") == "yellow"

    def test_get_color_for_notification(self):
        assert get_category_color("notification") == "blue"

    def test_get_color_for_acknowledgment(self):
        assert get_category_color("acknowledgment") == "green"

    def test_get_color_for_time(self):
        assert get_category_color("time") == "orange"

    def test_get_color_for_standard(self):
        assert get_category_color("standard") == "secondary"


class TestBuildTimelineItem:
    def test_build_timeline_item_for_status_change(self):
        """Test building timeline item for status change"""
        object_change = Mock()
        object_change.time = Mock()
        object_change.user = Mock()
        object_change.user.username = "testuser"
        object_change.user_name = "testuser"
        object_change.changed_object_type.model = "maintenance"
        object_change.action = "update"
        object_change.object_repr = "MAINT-123"
        object_change.prechange_data = {"status": "TENTATIVE", "acknowledged": False}
        object_change.postchange_data = {"status": "CONFIRMED", "acknowledged": False}

        item = build_timeline_item(object_change, "maintenance")

        assert item["category"] == "status"
        assert item["icon"] == "check-circle"
        assert item["title"] == "Status changed to Confirmed"
        assert len(item["changes"]) == 1
        assert item["changes"][0]["field"] == "status"
        assert item["changes"][0]["old_value"] == "TENTATIVE"
        assert item["changes"][0]["new_value"] == "CONFIRMED"

    def test_build_timeline_item_for_multiple_changes(self):
        """Test that all field changes are captured"""
        object_change = Mock()
        object_change.time = Mock()
        object_change.user = Mock()
        object_change.user.username = "testuser"
        object_change.user_name = "testuser"
        object_change.changed_object_type.model = "maintenance"
        object_change.action = "update"
        object_change.object_repr = "MAINT-123"
        object_change.prechange_data = {
            "status": "TENTATIVE",
            "acknowledged": False,
            "comments": "Old comment",
        }
        object_change.postchange_data = {
            "status": "CONFIRMED",
            "acknowledged": True,
            "comments": "New comment",
        }

        item = build_timeline_item(object_change, "maintenance")

        # Category based on priority (status wins)
        assert item["category"] == "status"
        # But all changes are captured
        assert len(item["changes"]) == 3
        change_fields = [c["field"] for c in item["changes"]]
        assert "status" in change_fields
        assert "acknowledged" in change_fields
        assert "comments" in change_fields

    def test_build_timeline_item_for_impact_creation(self):
        """Test building timeline item for impact creation"""
        object_change = Mock()
        object_change.time = Mock()
        object_change.user = Mock()
        object_change.user.username = "testuser"
        object_change.user_name = "testuser"
        object_change.changed_object_type.model = "impact"
        object_change.action = "create"
        object_change.object_repr = "Circuit ABC-123 - OUTAGE"
        object_change.prechange_data = None
        object_change.postchange_data = {
            "impact": "OUTAGE",
            "target": "Circuit ABC-123",
        }

        item = build_timeline_item(object_change, "maintenance")

        assert item["category"] == "impact"
        assert item["icon"] == "alert-triangle"
        assert item["title"] == "Impact added: Circuit ABC-123 - OUTAGE"
        assert item["action"] == "create"

    def test_build_timeline_item_for_cancelled_status(self):
        """Test that cancelled status changes use x-circle icon"""
        object_change = Mock()
        object_change.time = Mock()
        object_change.user = Mock()
        object_change.user.username = "testuser"
        object_change.user_name = "testuser"
        object_change.changed_object_type.model = "maintenance"
        object_change.action = "update"
        object_change.object_repr = "MAINT-123"
        object_change.prechange_data = {"status": "CONFIRMED"}
        object_change.postchange_data = {"status": "CANCELLED"}

        item = build_timeline_item(object_change, "maintenance")

        assert item["category"] == "status"
        assert item["icon"] == "x-circle"
        assert item["title"] == "Status changed to Cancelled"

    def test_build_timeline_item_for_completed_status(self):
        """Test that completed status changes use check-circle icon"""
        object_change = Mock()
        object_change.time = Mock()
        object_change.user = Mock()
        object_change.user.username = "testuser"
        object_change.user_name = "testuser"
        object_change.changed_object_type.model = "maintenance"
        object_change.action = "update"
        object_change.object_repr = "MAINT-123"
        object_change.prechange_data = {"status": "IN-PROCESS"}
        object_change.postchange_data = {"status": "COMPLETED"}

        item = build_timeline_item(object_change, "maintenance")

        assert item["category"] == "status"
        assert item["icon"] == "check-circle"
        assert item["title"] == "Status changed to Completed"
