"""
Unit tests for Maintenance model.
Tests that the Maintenance model exists by parsing the source code.
This approach works without requiring full NetBox/Django setup.
"""

import ast
import os
import unittest


class TestMaintenanceModel(unittest.TestCase):
    """Test Maintenance model basic functionality"""

    def _get_models_file_ast(self):
        """Parse the models/events.py file and return AST"""
        models_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "notices",
            "models",
            "events.py",
        )
        with open(models_path, "r") as f:
            return ast.parse(f.read())

    def _find_class(self, tree, class_name):
        """Find a class definition in the AST"""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                return node
        return None

    def _get_base_class_name(self, class_node):
        """Get the name of the base class"""
        if class_node.bases:
            for base in class_node.bases:
                if isinstance(base, ast.Name):
                    return base.id
        return None

    def _get_field_names(self, class_node):
        """Extract field names from model class"""
        fields = []
        for item in class_node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        # Check if it's a models.Field assignment
                        if isinstance(item.value, ast.Call):
                            fields.append(target.id)
        return fields

    def _has_method(self, class_node, method_name):
        """Check if class has a specific method"""
        for item in class_node.body:
            if isinstance(item, ast.FunctionDef) and item.name == method_name:
                return True
        return False

    def test_maintenance_model_exists(self):
        """Test that Maintenance class exists"""
        tree = self._get_models_file_ast()
        class_node = self._find_class(tree, "Maintenance")
        self.assertIsNotNone(class_node, "Maintenance class not found in models.py")

    def test_maintenance_inherits_from_base_event(self):
        """Test that Maintenance inherits from BaseEvent"""
        tree = self._get_models_file_ast()
        class_node = self._find_class(tree, "Maintenance")
        self.assertIsNotNone(class_node)

        base_class = self._get_base_class_name(class_node)
        self.assertEqual(
            base_class,
            "BaseEvent",
            f"Maintenance should inherit from BaseEvent, got {base_class}",
        )

    def test_maintenance_has_end_field(self):
        """Test that Maintenance has end field"""
        tree = self._get_models_file_ast()
        class_node = self._find_class(tree, "Maintenance")
        self.assertIsNotNone(class_node)

        fields = self._get_field_names(class_node)
        self.assertIn("end", fields, "Maintenance should define 'end' field")

    def test_maintenance_has_status_field(self):
        """Test that Maintenance has status field"""
        tree = self._get_models_file_ast()
        class_node = self._find_class(tree, "Maintenance")
        self.assertIsNotNone(class_node)

        fields = self._get_field_names(class_node)
        self.assertIn("status", fields, "Maintenance should define 'status' field")

    def test_maintenance_has_get_status_color_method(self):
        """Test that Maintenance has get_status_color method"""
        tree = self._get_models_file_ast()
        class_node = self._find_class(tree, "Maintenance")
        self.assertIsNotNone(class_node)

        self.assertTrue(
            self._has_method(class_node, "get_status_color"),
            "Maintenance should define get_status_color() method",
        )
