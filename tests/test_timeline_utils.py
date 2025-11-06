from vendor_notification.timeline_utils import categorize_change, get_field_display_name, get_category_icon, get_category_color


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
        prechange = {'status': 'TENTATIVE', 'acknowledged': False}
        postchange = {'status': 'CONFIRMED', 'acknowledged': False}

        category = categorize_change(
            changed_object_model='maintenance',
            action='update',
            prechange_data=prechange,
            postchange_data=postchange
        )

        assert category == 'status'

    def test_categorize_acknowledgment_change(self):
        """Acknowledgment changes should be categorized as 'acknowledgment'"""
        prechange = {'status': 'CONFIRMED', 'acknowledged': False}
        postchange = {'status': 'CONFIRMED', 'acknowledged': True}

        category = categorize_change(
            changed_object_model='maintenance',
            action='update',
            prechange_data=prechange,
            postchange_data=postchange
        )

        assert category == 'acknowledgment'

    def test_categorize_time_change(self):
        """Time field changes should be categorized as 'time'"""
        prechange = {'start': '2025-01-01T10:00:00Z', 'status': 'CONFIRMED'}
        postchange = {'start': '2025-01-01T11:00:00Z', 'status': 'CONFIRMED'}

        category = categorize_change(
            changed_object_model='maintenance',
            action='update',
            prechange_data=prechange,
            postchange_data=postchange
        )

        assert category == 'time'

    def test_categorize_impact_create(self):
        """Impact object creation should be categorized as 'impact'"""
        category = categorize_change(
            changed_object_model='impact',
            action='create',
            prechange_data=None,
            postchange_data={'impact': 'OUTAGE'}
        )

        assert category == 'impact'

    def test_categorize_notification_create(self):
        """Notification creation should be categorized as 'notification'"""
        category = categorize_change(
            changed_object_model='eventnotification',
            action='create',
            prechange_data=None,
            postchange_data={'subject': 'Maintenance notice'}
        )

        assert category == 'notification'

    def test_categorize_standard_change(self):
        """Other changes should be categorized as 'standard'"""
        prechange = {'comments': 'Old comment'}
        postchange = {'comments': 'New comment'}

        category = categorize_change(
            changed_object_model='maintenance',
            action='update',
            prechange_data=prechange,
            postchange_data=postchange
        )

        assert category == 'standard'


class TestIconAndColorMapping:
    def test_get_icon_for_status(self):
        assert get_category_icon('status') == 'check-circle'

    def test_get_icon_for_impact(self):
        assert get_category_icon('impact') == 'alert-triangle'

    def test_get_icon_for_notification(self):
        assert get_category_icon('notification') == 'mail'

    def test_get_icon_for_acknowledgment(self):
        assert get_category_icon('acknowledgment') == 'check'

    def test_get_icon_for_time(self):
        assert get_category_icon('time') == 'clock'

    def test_get_icon_for_standard(self):
        assert get_category_icon('standard') == 'circle'

    def test_get_color_for_status(self):
        # Status color comes from status value, returns default for testing
        assert get_category_color('status') == 'secondary'

    def test_get_color_for_impact(self):
        assert get_category_color('impact') == 'yellow'

    def test_get_color_for_notification(self):
        assert get_category_color('notification') == 'blue'

    def test_get_color_for_acknowledgment(self):
        assert get_category_color('acknowledgment') == 'green'

    def test_get_color_for_time(self):
        assert get_category_color('time') == 'orange'

    def test_get_color_for_standard(self):
        assert get_category_color('standard') == 'secondary'
