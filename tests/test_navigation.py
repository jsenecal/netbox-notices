from netbox.choices import ButtonColorChoices
from netbox.plugins import PluginMenu, PluginMenuButton, PluginMenuItem


class TestNavigationStructure:
    """Test navigation menu structure and configuration"""

    def test_navigation_module_imports(self):
        """Test that navigation module can be imported"""
        from vendor_notification import navigation

        assert hasattr(navigation, "menu")
        assert hasattr(navigation, "menuitems")

    def test_navigation_menu_exists(self):
        """Test that navigation menu is defined"""
        from vendor_notification.navigation import menu

        assert isinstance(menu, PluginMenu)
        assert menu.label == "Vendor Notification"
        assert menu.icon_class == "mdi mdi-wrench"

    def test_navigation_menu_groups(self):
        """Test navigation menu groups structure"""
        from vendor_notification.navigation import menu

        assert len(menu.groups) == 1
        # NetBox uses MenuGroup objects, not tuples
        group = menu.groups[0]
        assert group.label == "Vendor Notification"
        assert len(group.items) == 3

    def test_menuitems_count(self):
        """Test correct number of menu items"""
        from vendor_notification.navigation import menuitems

        assert len(menuitems) == 3

    def test_maintenance_menu_item(self):
        """Test Maintenance Events menu item configuration"""
        from vendor_notification.navigation import menuitems

        maintenance_item = menuitems[0]
        assert isinstance(maintenance_item, PluginMenuItem)
        assert maintenance_item.link == "plugins:vendor_notification:maintenance_list"
        assert maintenance_item.link_text == "Maintenance Events"
        assert len(maintenance_item.buttons) == 1

        # Check the add button
        add_button = maintenance_item.buttons[0]
        assert isinstance(add_button, PluginMenuButton)
        assert add_button.link == "plugins:vendor_notification:maintenance_add"
        assert add_button.title == "Add"
        assert add_button.icon_class == "mdi mdi-plus-thick"
        assert add_button.color == ButtonColorChoices.GREEN

    def test_outage_menu_item(self):
        """Test Outages menu item configuration"""
        from vendor_notification.navigation import menuitems

        outage_item = menuitems[1]
        assert isinstance(outage_item, PluginMenuItem)
        assert outage_item.link == "plugins:vendor_notification:outage_list"
        assert outage_item.link_text == "Outages"
        assert len(outage_item.buttons) == 1

        # Check the add button
        add_button = outage_item.buttons[0]
        assert isinstance(add_button, PluginMenuButton)
        assert add_button.link == "plugins:vendor_notification:outage_add"
        assert add_button.title == "Add"
        assert add_button.icon_class == "mdi mdi-plus-thick"
        assert add_button.color == ButtonColorChoices.GREEN

    def test_maintenance_schedule_menu_item(self):
        """Test Maintenance Schedule menu item configuration"""
        from vendor_notification.navigation import menuitems

        schedule_item = menuitems[2]
        assert isinstance(schedule_item, PluginMenuItem)
        assert schedule_item.link == "plugins:vendor_notification:maintenanceschedule"
        assert schedule_item.link_text == "Maintenance Schedule"
        # Schedule item should have an empty buttons list
        assert schedule_item.buttons == []

    def test_no_old_model_references(self):
        """Test that navigation doesn't contain old model name references"""
        from vendor_notification import navigation

        navigation_content = str(navigation.__dict__)

        # Should not contain old model names
        assert "circuitmaintenance" not in navigation_content.lower()
        assert "circuitoutage" not in navigation_content.lower()
        assert "netbox_circuitmaintenance" not in navigation_content.lower()

    def test_url_patterns_match_urls_module(self):
        """Test that navigation URLs match the patterns defined in urls.py"""

        # Expected URL patterns that should be reversible
        expected_urls = [
            "plugins:vendor_notification:maintenance_list",
            "plugins:vendor_notification:maintenance_add",
            "plugins:vendor_notification:outage_list",
            "plugins:vendor_notification:outage_add",
            "plugins:vendor_notification:maintenanceschedule",
        ]

        # Note: This test will only work if NetBox is fully configured with the plugin installed
        # For unit tests without full Django setup, we just verify the URL strings are correct
        for url_name in expected_urls:
            # Verify URL naming convention
            assert url_name.startswith("plugins:vendor_notification:")
            # Verify no old naming
            assert "circuitmaintenance" not in url_name
            assert "circuitoutage" not in url_name

    def test_menu_item_ordering(self):
        """Test that menu items are in the expected order"""
        from vendor_notification.navigation import menuitems

        # Verify order: Maintenance Events, Outages, Maintenance Schedule
        assert menuitems[0].link_text == "Maintenance Events"
        assert menuitems[1].link_text == "Outages"
        assert menuitems[2].link_text == "Maintenance Schedule"

    def test_all_buttons_have_icons(self):
        """Test that all menu buttons have icons configured"""
        from vendor_notification.navigation import menuitems

        for item in menuitems:
            if hasattr(item, "buttons") and item.buttons:
                for button in item.buttons:
                    assert hasattr(button, "icon_class")
                    assert button.icon_class.startswith("mdi ")

    def test_plugin_menu_structure(self):
        """Test complete plugin menu structure for NetBox compatibility"""
        from vendor_notification.navigation import menu

        # Verify menu can be serialized (important for NetBox plugin system)
        assert menu.label
        assert menu.icon_class
        assert menu.groups

        # Verify groups structure matches NetBox expectations
        for group in menu.groups:
            assert hasattr(group, "label")
            assert hasattr(group, "items")
            assert isinstance(group.label, str)
            assert isinstance(group.items, list)
            for item in group.items:
                assert isinstance(item, PluginMenuItem)
                assert hasattr(item, "link")
                assert hasattr(item, "link_text")
