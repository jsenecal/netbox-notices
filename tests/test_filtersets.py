"""
Unit tests for filterset classes.
These tests validate the code structure by reading the source file directly.
This approach works without requiring NetBox installation.
"""

import ast
import os
import unittest


class FilterSetTestBase(unittest.TestCase):
    """Base class for filterset tests with common helper methods"""

    def _get_filtersets_file_ast(self):
        """Parse the filtersets.py file and return AST"""
        filtersets_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "notices",
            "filtersets.py",
        )
        with open(filtersets_path, "r") as f:
            return ast.parse(f.read())

    def _find_class(self, tree, class_name):
        """Find a class definition in the AST"""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                return node
        return None

    def _get_meta_fields(self, class_node):
        """Extract fields from Meta class"""
        for item in class_node.body:
            if isinstance(item, ast.ClassDef) and item.name == "Meta":
                for meta_item in item.body:
                    if isinstance(meta_item, ast.Assign):
                        for target in meta_item.targets:
                            if isinstance(target, ast.Name) and target.id == "fields":
                                # Extract list or tuple values
                                if isinstance(meta_item.value, (ast.List, ast.Tuple)):
                                    return [elt.value for elt in meta_item.value.elts if isinstance(elt, ast.Constant)]
        return []

    def _get_meta_model(self, class_node):
        """Extract model from Meta class"""
        for item in class_node.body:
            if isinstance(item, ast.ClassDef) and item.name == "Meta":
                for meta_item in item.body:
                    if isinstance(meta_item, ast.Assign):
                        for target in meta_item.targets:
                            if isinstance(target, ast.Name) and target.id == "model":
                                if isinstance(meta_item.value, ast.Name):
                                    return meta_item.value.id
        return None

    def _get_class_attributes(self, class_node):
        """Extract class-level attribute assignments"""
        attributes = {}
        for item in class_node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        # Get the type of the value being assigned
                        if isinstance(item.value, ast.Call):
                            if isinstance(item.value.func, ast.Name):
                                attributes[target.id] = item.value.func.id
        return attributes

    def _has_search_method(self, class_node):
        """Check if class has a search method"""
        for item in class_node.body:
            if isinstance(item, ast.FunctionDef) and item.name == "search":
                return True
        return False


class TestMaintenanceFilterSet(FilterSetTestBase):
    """Test the MaintenanceFilterSet class structure"""

    def test_maintenance_filterset_exists(self):
        """Test that MaintenanceFilterSet is defined"""
        tree = self._get_filtersets_file_ast()
        class_node = self._find_class(tree, "MaintenanceFilterSet")
        self.assertIsNotNone(class_node, "MaintenanceFilterSet class not found in filtersets.py")

    def test_maintenance_filterset_meta_model(self):
        """Test that MaintenanceFilterSet references Maintenance model"""
        tree = self._get_filtersets_file_ast()
        class_node = self._find_class(tree, "MaintenanceFilterSet")
        self.assertIsNotNone(class_node, "MaintenanceFilterSet class not found")

        model = self._get_meta_model(class_node)
        self.assertEqual(
            model,
            "Maintenance",
            f"MaintenanceFilterSet should reference Maintenance model, got {model}",
        )

    def test_maintenance_filterset_fields(self):
        """Test that MaintenanceFilterSet includes key filter fields"""
        tree = self._get_filtersets_file_ast()
        class_node = self._find_class(tree, "MaintenanceFilterSet")
        self.assertIsNotNone(class_node, "MaintenanceFilterSet class not found")

        fields = self._get_meta_fields(class_node)
        expected_fields = [
            "id",
            "name",
            "summary",
            "status",
            "provider",
            "start",
            "end",
            "original_timezone",
            "internal_ticket",
            "acknowledged",
            "comments",
        ]

        for field in expected_fields:
            self.assertIn(field, fields, f"Missing expected filter field in Maintenance: {field}")

    def test_maintenance_filterset_has_search(self):
        """Test that MaintenanceFilterSet has search method"""
        tree = self._get_filtersets_file_ast()
        class_node = self._find_class(tree, "MaintenanceFilterSet")
        self.assertIsNotNone(class_node, "MaintenanceFilterSet class not found")

        has_search = self._has_search_method(class_node)
        self.assertTrue(has_search, "MaintenanceFilterSet should have a search method")


class TestOutageFilterSet(FilterSetTestBase):
    """Test the OutageFilterSet class structure"""

    def test_outage_filterset_exists(self):
        """Test that OutageFilterSet is defined"""
        tree = self._get_filtersets_file_ast()
        class_node = self._find_class(tree, "OutageFilterSet")
        self.assertIsNotNone(class_node, "OutageFilterSet class not found in filtersets.py")

    def test_outage_filterset_meta_model(self):
        """Test that OutageFilterSet references Outage model"""
        tree = self._get_filtersets_file_ast()
        class_node = self._find_class(tree, "OutageFilterSet")
        self.assertIsNotNone(class_node, "OutageFilterSet class not found")

        model = self._get_meta_model(class_node)
        self.assertEqual(
            model,
            "Outage",
            f"OutageFilterSet should reference Outage model, got {model}",
        )

    def test_outage_filterset_fields(self):
        """Test that OutageFilterSet includes key filter fields"""
        tree = self._get_filtersets_file_ast()
        class_node = self._find_class(tree, "OutageFilterSet")
        self.assertIsNotNone(class_node, "OutageFilterSet class not found")

        fields = self._get_meta_fields(class_node)
        expected_fields = [
            "id",
            "name",
            "summary",
            "status",
            "provider",
            "start",
            "end",
            "estimated_time_to_repair",
            "original_timezone",
            "internal_ticket",
            "acknowledged",
            "comments",
        ]

        for field in expected_fields:
            self.assertIn(field, fields, f"Missing expected filter field in Outage: {field}")

    def test_outage_filterset_has_search(self):
        """Test that OutageFilterSet has search method"""
        tree = self._get_filtersets_file_ast()
        class_node = self._find_class(tree, "OutageFilterSet")
        self.assertIsNotNone(class_node, "OutageFilterSet class not found")

        has_search = self._has_search_method(class_node)
        self.assertTrue(has_search, "OutageFilterSet should have a search method")


class TestImpactFilterSet(FilterSetTestBase):
    """Test the ImpactFilterSet class structure"""

    def test_impact_filterset_exists(self):
        """Test that ImpactFilterSet is defined"""
        tree = self._get_filtersets_file_ast()
        class_node = self._find_class(tree, "ImpactFilterSet")
        self.assertIsNotNone(class_node, "ImpactFilterSet class not found in filtersets.py")

    def test_impact_filterset_meta_model(self):
        """Test that ImpactFilterSet references Impact model"""
        tree = self._get_filtersets_file_ast()
        class_node = self._find_class(tree, "ImpactFilterSet")
        self.assertIsNotNone(class_node, "ImpactFilterSet class not found")

        model = self._get_meta_model(class_node)
        self.assertEqual(
            model,
            "Impact",
            f"ImpactFilterSet should reference Impact model, got {model}",
        )

    def test_impact_filterset_fields(self):
        """Test that ImpactFilterSet includes key filter fields"""
        tree = self._get_filtersets_file_ast()
        class_node = self._find_class(tree, "ImpactFilterSet")
        self.assertIsNotNone(class_node, "ImpactFilterSet class not found")

        fields = self._get_meta_fields(class_node)
        expected_fields = [
            "id",
            "event_content_type",
            "event_object_id",
            "target_content_type",
            "target_object_id",
            "impact",
        ]

        for field in expected_fields:
            self.assertIn(field, fields, f"Missing expected filter field in Impact: {field}")

    def test_impact_filterset_has_content_type_filters(self):
        """Test that ImpactFilterSet has ContentTypeFilter attributes"""
        tree = self._get_filtersets_file_ast()
        class_node = self._find_class(tree, "ImpactFilterSet")
        self.assertIsNotNone(class_node, "ImpactFilterSet class not found")

        attributes = self._get_class_attributes(class_node)

        # Check for event_content_type filter
        self.assertIn(
            "event_content_type",
            attributes,
            "ImpactFilterSet should have event_content_type filter",
        )
        self.assertEqual(
            attributes.get("event_content_type"),
            "ContentTypeFilter",
            "event_content_type should be a ContentTypeFilter",
        )

        # Check for target_content_type filter
        self.assertIn(
            "target_content_type",
            attributes,
            "ImpactFilterSet should have target_content_type filter",
        )
        self.assertEqual(
            attributes.get("target_content_type"),
            "ContentTypeFilter",
            "target_content_type should be a ContentTypeFilter",
        )

    def test_impact_filterset_has_search(self):
        """Test that ImpactFilterSet has search method"""
        tree = self._get_filtersets_file_ast()
        class_node = self._find_class(tree, "ImpactFilterSet")
        self.assertIsNotNone(class_node, "ImpactFilterSet class not found")

        has_search = self._has_search_method(class_node)
        self.assertTrue(has_search, "ImpactFilterSet should have a search method")


class TestEventNotificationFilterSet(FilterSetTestBase):
    """Test the EventNotificationFilterSet class structure"""

    def test_eventnotification_filterset_exists(self):
        """Test that EventNotificationFilterSet is defined"""
        tree = self._get_filtersets_file_ast()
        class_node = self._find_class(tree, "EventNotificationFilterSet")
        self.assertIsNotNone(
            class_node,
            "EventNotificationFilterSet class not found in filtersets.py",
        )

    def test_eventnotification_filterset_meta_model(self):
        """Test that EventNotificationFilterSet references EventNotification model"""
        tree = self._get_filtersets_file_ast()
        class_node = self._find_class(tree, "EventNotificationFilterSet")
        self.assertIsNotNone(class_node, "EventNotificationFilterSet class not found")

        model = self._get_meta_model(class_node)
        self.assertEqual(
            model,
            "EventNotification",
            f"EventNotificationFilterSet should reference EventNotification model, got {model}",
        )

    def test_eventnotification_filterset_fields(self):
        """Test that EventNotificationFilterSet includes key filter fields"""
        tree = self._get_filtersets_file_ast()
        class_node = self._find_class(tree, "EventNotificationFilterSet")
        self.assertIsNotNone(class_node, "EventNotificationFilterSet class not found")

        fields = self._get_meta_fields(class_node)
        expected_fields = [
            "id",
            "event_content_type",
            "event_object_id",
            "email_body",
            "subject",
            "email_from",
            "email_received",
        ]

        for field in expected_fields:
            self.assertIn(
                field,
                fields,
                f"Missing expected filter field in EventNotification: {field}",
            )

    def test_eventnotification_filterset_has_content_type_filter(self):
        """Test that EventNotificationFilterSet has ContentTypeFilter attribute"""
        tree = self._get_filtersets_file_ast()
        class_node = self._find_class(tree, "EventNotificationFilterSet")
        self.assertIsNotNone(class_node, "EventNotificationFilterSet class not found")

        attributes = self._get_class_attributes(class_node)

        # Check for event_content_type filter
        self.assertIn(
            "event_content_type",
            attributes,
            "EventNotificationFilterSet should have event_content_type filter",
        )
        self.assertEqual(
            attributes.get("event_content_type"),
            "ContentTypeFilter",
            "event_content_type should be a ContentTypeFilter",
        )

    def test_eventnotification_filterset_has_search(self):
        """Test that EventNotificationFilterSet has search method"""
        tree = self._get_filtersets_file_ast()
        class_node = self._find_class(tree, "EventNotificationFilterSet")
        self.assertIsNotNone(class_node, "EventNotificationFilterSet class not found")

        has_search = self._has_search_method(class_node)
        self.assertTrue(has_search, "EventNotificationFilterSet should have a search method")


class TestFilterSetImports(FilterSetTestBase):
    """Test that filtersets.py has correct imports"""

    def _get_imports(self):
        """Extract import statements from filtersets.py"""
        tree = self._get_filtersets_file_ast()
        imports = {
            "modules": [],  # from X import Y
            "names": [],  # imported names
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module
                names = [alias.name for alias in node.names]
                imports["modules"].append(module)
                imports["names"].extend(names)

        return imports

    def test_imports_content_type_filter(self):
        """Test that ContentTypeFilter is imported"""
        imports = self._get_imports()
        self.assertIn(
            "ContentTypeFilter",
            imports["names"],
            "filtersets.py should import ContentTypeFilter",
        )

    def test_imports_netbox_filterset(self):
        """Test that NetBoxModelFilterSet is imported"""
        imports = self._get_imports()
        self.assertIn(
            "NetBoxModelFilterSet",
            imports["names"],
            "filtersets.py should import NetBoxModelFilterSet",
        )

    def test_imports_models(self):
        """Test that model classes are imported"""
        imports = self._get_imports()
        expected_models = ["Maintenance", "Outage", "Impact", "EventNotification"]

        for model in expected_models:
            self.assertIn(
                model,
                imports["names"],
                f"filtersets.py should import {model} model",
            )


if __name__ == "__main__":
    unittest.main()
