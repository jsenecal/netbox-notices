"""
Tests for notices views.
These tests validate the code structure by reading the source file directly.
This approach works without requiring NetBox installation.
"""

import ast
import os
import unittest


class TestViewsStructure(unittest.TestCase):
    """Test the view classes structure"""

    def _get_views_file_ast(self):
        """Parse the views.py file and return AST"""
        views_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "notices",
            "views.py",
        )
        with open(views_path, "r") as f:
            return ast.parse(f.read())

    def _find_class(self, tree, class_name):
        """Find a class definition in the AST"""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                return node
        return None

    def _has_attribute(self, class_node, attribute_name):
        """Check if a class has a specific attribute"""
        for item in class_node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and target.id == attribute_name:
                        return True
        return False

    def test_maintenance_views_exist(self):
        """Test that all Maintenance views are defined"""
        tree = self._get_views_file_ast()

        view_classes = [
            "MaintenanceListView",
            "MaintenanceView",
            "MaintenanceEditView",
            "MaintenanceDeleteView",
        ]

        for view_class in view_classes:
            class_node = self._find_class(tree, view_class)
            self.assertIsNotNone(class_node, f"{view_class} class not found")

    def test_outage_views_exist(self):
        """Test that all Outage views are defined"""
        tree = self._get_views_file_ast()

        view_classes = [
            "OutageListView",
            "OutageView",
            "OutageEditView",
            "OutageDeleteView",
        ]

        for view_class in view_classes:
            class_node = self._find_class(tree, view_class)
            self.assertIsNotNone(class_node, f"{view_class} class not found")

    def test_impact_views_exist(self):
        """Test that Impact views are defined"""
        tree = self._get_views_file_ast()

        view_classes = [
            "ImpactEditView",
            "ImpactDeleteView",
        ]

        for view_class in view_classes:
            class_node = self._find_class(tree, view_class)
            self.assertIsNotNone(class_node, f"{view_class} class not found")

    def test_event_notification_views_exist(self):
        """Test that EventNotification views are defined"""
        tree = self._get_views_file_ast()

        view_classes = [
            "EventNotificationView",
            "EventNotificationEditView",
            "EventNotificationDeleteView",
        ]

        for view_class in view_classes:
            class_node = self._find_class(tree, view_class)
            self.assertIsNotNone(class_node, f"{view_class} class not found")

    def test_maintenance_list_view_attributes(self):
        """Test that MaintenanceListView has required attributes"""
        tree = self._get_views_file_ast()
        class_node = self._find_class(tree, "MaintenanceListView")

        if class_node is None:
            self.fail("MaintenanceListView class not found")

        # Check for required attributes
        self.assertTrue(
            self._has_attribute(class_node, "queryset"),
            "MaintenanceListView missing queryset attribute",
        )
        self.assertTrue(
            self._has_attribute(class_node, "table"),
            "MaintenanceListView missing table attribute",
        )
        self.assertTrue(
            self._has_attribute(class_node, "filterset"),
            "MaintenanceListView missing filterset attribute",
        )
        self.assertTrue(
            self._has_attribute(class_node, "filterset_form"),
            "MaintenanceListView missing filterset_form attribute",
        )

    def test_outage_list_view_attributes(self):
        """Test that OutageListView has required attributes"""
        tree = self._get_views_file_ast()
        class_node = self._find_class(tree, "OutageListView")

        if class_node is None:
            self.fail("OutageListView class not found")

        # Check for required attributes
        self.assertTrue(
            self._has_attribute(class_node, "queryset"),
            "OutageListView missing queryset attribute",
        )
        self.assertTrue(
            self._has_attribute(class_node, "table"),
            "OutageListView missing table attribute",
        )
        self.assertTrue(
            self._has_attribute(class_node, "filterset"),
            "OutageListView missing filterset attribute",
        )
        self.assertTrue(
            self._has_attribute(class_node, "filterset_form"),
            "OutageListView missing filterset_form attribute",
        )

    def test_maintenance_edit_view_attributes(self):
        """Test that MaintenanceEditView has required attributes"""
        tree = self._get_views_file_ast()
        class_node = self._find_class(tree, "MaintenanceEditView")

        if class_node is None:
            self.fail("MaintenanceEditView class not found")

        # Check for required attributes
        self.assertTrue(
            self._has_attribute(class_node, "queryset"),
            "MaintenanceEditView missing queryset attribute",
        )
        self.assertTrue(
            self._has_attribute(class_node, "form"),
            "MaintenanceEditView missing form attribute",
        )

    def test_outage_edit_view_attributes(self):
        """Test that OutageEditView has required attributes"""
        tree = self._get_views_file_ast()
        class_node = self._find_class(tree, "OutageEditView")

        if class_node is None:
            self.fail("OutageEditView class not found")

        # Check for required attributes
        self.assertTrue(
            self._has_attribute(class_node, "queryset"),
            "OutageEditView missing queryset attribute",
        )
        self.assertTrue(
            self._has_attribute(class_node, "form"),
            "OutageEditView missing form attribute",
        )

    def test_impact_edit_view_attributes(self):
        """Test that ImpactEditView has required attributes"""
        tree = self._get_views_file_ast()
        class_node = self._find_class(tree, "ImpactEditView")

        if class_node is None:
            self.fail("ImpactEditView class not found")

        # Check for required attributes
        self.assertTrue(
            self._has_attribute(class_node, "queryset"),
            "ImpactEditView missing queryset attribute",
        )
        self.assertTrue(
            self._has_attribute(class_node, "form"),
            "ImpactEditView missing form attribute",
        )

    def test_event_notification_edit_view_attributes(self):
        """Test that EventNotificationEditView has required attributes"""
        tree = self._get_views_file_ast()
        class_node = self._find_class(tree, "EventNotificationEditView")

        if class_node is None:
            self.fail("EventNotificationEditView class not found")

        # Check for required attributes
        self.assertTrue(
            self._has_attribute(class_node, "queryset"),
            "EventNotificationEditView missing queryset attribute",
        )
        self.assertTrue(
            self._has_attribute(class_node, "form"),
            "EventNotificationEditView missing form attribute",
        )

    def test_maintenance_view_has_queryset(self):
        """Test that MaintenanceView defines queryset attribute"""
        tree = self._get_views_file_ast()
        class_node = self._find_class(tree, "MaintenanceView")

        if class_node is None:
            self.fail("MaintenanceView class not found")

        self.assertTrue(
            self._has_attribute(class_node, "queryset"),
            "MaintenanceView missing queryset attribute",
        )

    def test_outage_view_has_queryset(self):
        """Test that OutageView defines queryset attribute"""
        tree = self._get_views_file_ast()
        class_node = self._find_class(tree, "OutageView")

        if class_node is None:
            self.fail("OutageView class not found")

        self.assertTrue(
            self._has_attribute(class_node, "queryset"),
            "OutageView missing queryset attribute",
        )

    def test_delete_views_have_queryset(self):
        """Test that all delete views have queryset attribute"""
        tree = self._get_views_file_ast()

        delete_views = [
            "MaintenanceDeleteView",
            "OutageDeleteView",
            "ImpactDeleteView",
            "EventNotificationDeleteView",
        ]

        for view_class in delete_views:
            class_node = self._find_class(tree, view_class)
            if class_node is None:
                self.fail(f"{view_class} class not found")

            self.assertTrue(
                self._has_attribute(class_node, "queryset"),
                f"{view_class} missing queryset attribute",
            )

    def test_old_view_names_removed(self):
        """Test that old view class names no longer exist"""
        tree = self._get_views_file_ast()

        old_view_classes = [
            "CircuitMaintenanceView",
            "CircuitMaintenanceListView",
            "CircuitMaintenanceEditView",
            "CircuitMaintenanceDeleteView",
            "CircuitOutageListView",
            "CircuitOutageView",
            "CircuitOutageEditView",
            "CircuitOutageDeleteView",
            "CircuitMaintenanceImpactEditView",
            "CircuitMaintenanceImpactDeleteView",
            "CircuitMaintenanceNotificationsView",
            "CircuitMaintenanceNotificationsEditView",
            "CircuitMaintenanceNotificationsDeleteView",
            "CircuitMaintenanceNotificationView",
        ]

        for view_class in old_view_classes:
            class_node = self._find_class(tree, view_class)
            self.assertIsNone(
                class_node, f"Old view class {view_class} should not exist"
            )

    def test_calendar_view_exists(self):
        """Test that MaintenanceCalendarView exists"""
        tree = self._get_views_file_ast()
        class_node = self._find_class(tree, "MaintenanceCalendarView")
        self.assertIsNotNone(class_node, "MaintenanceCalendarView class not found")

    def test_old_calendar_view_removed(self):
        """Test that old CircuitMaintenanceScheduleView no longer exists"""
        tree = self._get_views_file_ast()
        class_node = self._find_class(tree, "CircuitMaintenanceScheduleView")
        self.assertIsNone(
            class_node, "Old CircuitMaintenanceScheduleView should not exist"
        )


if __name__ == "__main__":
    unittest.main()
