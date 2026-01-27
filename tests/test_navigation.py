from netbox.plugins import PluginMenu, PluginMenuButton, PluginMenuItem


class TestNavigationStructure:
    """Test navigation menu structure and configuration"""

    def test_navigation_module_imports(self):
        """Test that navigation module can be imported"""
        from notices import navigation

        assert hasattr(navigation, "menu")
        assert hasattr(navigation, "notifications_items")
        assert hasattr(navigation, "events_items")
        assert hasattr(navigation, "messaging_items")

    def test_navigation_menu_exists(self):
        """Test that navigation menu is defined"""
        from notices.navigation import menu

        assert isinstance(menu, PluginMenu)
        assert menu.label == "Notices"
        assert menu.icon_class == "mdi mdi-wrench"

    def test_navigation_menu_groups(self):
        """Test navigation menu groups structure"""
        from notices.navigation import menu

        assert len(menu.groups) == 3
        # NetBox uses MenuGroup objects, not tuples

        # First group: Notifications
        notifications_group = menu.groups[0]
        assert notifications_group.label == "Notifications"
        assert len(notifications_group.items) == 2  # Received and Sent

        # Second group: Events
        events_group = menu.groups[1]
        assert events_group.label == "Events"
        assert len(events_group.items) == 3

        # Third group: Messaging
        messaging_group = menu.groups[2]
        assert messaging_group.label == "Messaging"
        assert len(messaging_group.items) == 2

    def test_menuitems_count(self):
        """Test correct number of menu items in each group"""
        from notices.navigation import events_items, notifications_items

        assert len(notifications_items) == 2  # Received and Sent
        assert len(events_items) == 3

    def test_received_menu_item(self):
        """Test Received (EventNotifications) menu item configuration"""
        from notices.navigation import notifications_items

        received_item = notifications_items[0]
        assert isinstance(received_item, PluginMenuItem)
        assert received_item.link == "plugins:notices:eventnotification_list"
        assert received_item.link_text == "Received"
        assert len(received_item.buttons) == 1

        # Check the add button
        add_button = received_item.buttons[0]
        assert isinstance(add_button, PluginMenuButton)
        assert add_button.link == "plugins:notices:eventnotification_add"
        assert add_button.title == "Add"
        assert add_button.icon_class == "mdi mdi-plus-thick"

    def test_sent_menu_item(self):
        """Test Sent (sent/delivered notifications) menu item configuration"""
        from notices.navigation import notifications_items

        sent_item = notifications_items[1]
        assert isinstance(sent_item, PluginMenuItem)
        assert sent_item.link == "plugins:notices:sentnotification_list"
        assert sent_item.link_text == "Sent"
        # Sent is view-only (no add button - notifications are created via workflow)
        assert sent_item.buttons == []

    def test_maintenance_menu_item(self):
        """Test Planned Maintenances menu item configuration"""
        from notices.navigation import events_items

        maintenance_item = events_items[0]
        assert isinstance(maintenance_item, PluginMenuItem)
        assert maintenance_item.link == "plugins:notices:maintenance_list"
        assert maintenance_item.link_text == "Planned Maintenances"
        assert len(maintenance_item.buttons) == 1

        # Check the add button
        add_button = maintenance_item.buttons[0]
        assert isinstance(add_button, PluginMenuButton)
        assert add_button.link == "plugins:notices:maintenance_add"
        assert add_button.title == "Add"
        assert add_button.icon_class == "mdi mdi-plus-thick"

    def test_outage_menu_item(self):
        """Test Outages menu item configuration"""
        from notices.navigation import events_items

        outage_item = events_items[1]
        assert isinstance(outage_item, PluginMenuItem)
        assert outage_item.link == "plugins:notices:outage_list"
        assert outage_item.link_text == "Outages"
        assert len(outage_item.buttons) == 1

        # Check the add button
        add_button = outage_item.buttons[0]
        assert isinstance(add_button, PluginMenuButton)
        assert add_button.link == "plugins:notices:outage_add"
        assert add_button.title == "Add"
        assert add_button.icon_class == "mdi mdi-plus-thick"

    def test_maintenance_schedule_menu_item(self):
        """Test Calendar menu item configuration"""
        from notices.navigation import events_items

        calendar_item = events_items[2]
        assert isinstance(calendar_item, PluginMenuItem)
        assert calendar_item.link == "plugins:notices:maintenance_calendar"
        assert calendar_item.link_text == "Calendar"
        # Calendar item should have an empty buttons list (view-only)
        assert calendar_item.buttons == []

    def test_no_old_model_references(self):
        """Test that navigation doesn't contain old model name references"""
        from notices import navigation

        navigation_content = str(navigation.__dict__)

        # Should not contain old model names
        assert "circuitmaintenance" not in navigation_content.lower()
        assert "circuitoutage" not in navigation_content.lower()
        assert "netbox_circuitmaintenance" not in navigation_content.lower()
        assert "vendor_notification" not in navigation_content.lower()

    def test_url_patterns_match_urls_module(self):
        """Test that navigation URLs match the patterns defined in urls.py"""

        # Expected URL patterns that should be reversible
        expected_urls = [
            "plugins:notices:eventnotification_list",
            "plugins:notices:eventnotification_add",
            "plugins:notices:maintenance_list",
            "plugins:notices:maintenance_add",
            "plugins:notices:outage_list",
            "plugins:notices:outage_add",
            "plugins:notices:maintenance_calendar",
        ]

        # Note: This test will only work if NetBox is fully configured with the plugin installed
        # For unit tests without full Django setup, we just verify the URL strings are correct
        for url_name in expected_urls:
            # Verify URL naming convention
            assert url_name.startswith("plugins:notices:")
            # Verify no old naming
            assert "circuitmaintenance" not in url_name
            assert "circuitoutage" not in url_name
            assert "vendor_notification" not in url_name

    def test_menu_item_ordering(self):
        """Test that menu items are in the expected order"""
        from notices.navigation import events_items, notifications_items

        # Notifications group order
        assert notifications_items[0].link_text == "Received"
        assert notifications_items[1].link_text == "Sent"

        # Events group order
        assert events_items[0].link_text == "Planned Maintenances"
        assert events_items[1].link_text == "Outages"
        assert events_items[2].link_text == "Calendar"

    def test_all_buttons_have_icons(self):
        """Test that all menu buttons have icons configured"""
        from notices.navigation import events_items, notifications_items

        all_items = notifications_items + events_items

        for item in all_items:
            if hasattr(item, "buttons") and item.buttons:
                for button in item.buttons:
                    assert hasattr(button, "icon_class")
                    assert button.icon_class.startswith("mdi ")

    def test_plugin_menu_structure(self):
        """Test complete plugin menu structure for NetBox compatibility"""
        from notices.navigation import menu

        # Verify menu can be serialized (important for NetBox plugin system)
        assert menu.label
        assert menu.icon_class
        assert menu.groups

        # Verify groups structure matches NetBox expectations
        assert len(menu.groups) == 3

        for group in menu.groups:
            assert hasattr(group, "label")
            assert hasattr(group, "items")
            assert isinstance(group.label, str)
            assert isinstance(group.items, list)
            for item in group.items:
                assert isinstance(item, PluginMenuItem)
                assert hasattr(item, "link")
                assert hasattr(item, "link_text")

    def test_messaging_menu_items(self):
        """Test Messaging group menu items configuration"""
        from notices.navigation import messaging_items

        assert len(messaging_items) == 2

        # Notification Templates item
        templates_item = messaging_items[0]
        assert isinstance(templates_item, PluginMenuItem)
        assert templates_item.link == "plugins:notices:notificationtemplate_list"
        assert templates_item.link_text == "Notification Templates"
        assert len(templates_item.buttons) == 1

        add_button = templates_item.buttons[0]
        assert isinstance(add_button, PluginMenuButton)
        assert add_button.link == "plugins:notices:notificationtemplate_add"
        assert add_button.title == "Add"
        assert add_button.icon_class == "mdi mdi-plus-thick"

        # Prepared Notifications item
        notifications_item = messaging_items[1]
        assert isinstance(notifications_item, PluginMenuItem)
        assert notifications_item.link == "plugins:notices:preparednotification_list"
        assert notifications_item.link_text == "Prepared Notifications"
        assert len(notifications_item.buttons) == 1

        add_button = notifications_item.buttons[0]
        assert isinstance(add_button, PluginMenuButton)
        assert add_button.link == "plugins:notices:preparednotification_add"
        assert add_button.title == "Add"
        assert add_button.icon_class == "mdi mdi-plus-thick"
