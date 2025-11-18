"""
Unit tests for Outage models.
These tests validate the code structure by reading the source file directly.
This approach works without requiring NetBox installation.
"""

import ast
import os
import unittest


class TestBaseEvent(unittest.TestCase):
    """Test the BaseEvent abstract model structure"""

    def _get_models_file_ast(self):
        """Parse the models.py file and return AST"""
        models_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "notices",
            "models.py",
        )
        with open(models_path, "r") as f:
            return ast.parse(f.read())

    def _find_class(self, tree, class_name):
        """Find a class definition in the AST"""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                return node
        return None

    def _is_abstract_model(self, class_node):
        """Check if a class has Meta.abstract = True"""
        for item in class_node.body:
            if isinstance(item, ast.ClassDef) and item.name == "Meta":
                for meta_item in item.body:
                    if isinstance(meta_item, ast.Assign):
                        for target in meta_item.targets:
                            if isinstance(target, ast.Name) and target.id == "abstract":
                                if isinstance(meta_item.value, ast.Constant):
                                    return meta_item.value.value is True
        return False

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

    def test_base_circuit_event_exists(self):
        """Test that BaseEvent class exists"""
        tree = self._get_models_file_ast()
        class_node = self._find_class(tree, "BaseEvent")
        self.assertIsNotNone(class_node, "BaseEvent class not found in models.py")

    def test_base_circuit_event_is_abstract(self):
        """Test that BaseEvent is abstract"""
        tree = self._get_models_file_ast()
        class_node = self._find_class(tree, "BaseEvent")
        self.assertIsNotNone(class_node)
        self.assertTrue(
            self._is_abstract_model(class_node),
            "BaseEvent should have Meta.abstract = True",
        )

    def test_base_circuit_event_fields(self):
        """Test that BaseEvent defines expected fields"""
        expected_fields = [
            "name",
            "summary",
            "provider",
            "start",
            "original_timezone",
            "internal_ticket",
            "acknowledged",
            "comments",
        ]

        tree = self._get_models_file_ast()
        class_node = self._find_class(tree, "BaseEvent")
        self.assertIsNotNone(class_node)

        actual_fields = self._get_field_names(class_node)

        for field_name in expected_fields:
            self.assertIn(field_name, actual_fields, f"Missing field: {field_name}")


class TestOutageModel(unittest.TestCase):
    """Test renamed Outage model structure (Task 6)"""

    def _get_models_file_ast(self):
        """Parse the models.py file and return AST"""
        models_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "notices",
            "models.py",
        )
        with open(models_path, "r") as f:
            return ast.parse(f.read())

    def _find_class(self, tree, class_name):
        """Find a class definition in the AST"""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                return node
        return None

    def _get_meta_attribute(self, class_node, attr_name):
        """Get a Meta class attribute value"""
        for item in class_node.body:
            if isinstance(item, ast.ClassDef) and item.name == "Meta":
                for meta_item in item.body:
                    if isinstance(meta_item, ast.Assign):
                        for target in meta_item.targets:
                            if isinstance(target, ast.Name) and target.id == attr_name:
                                if isinstance(meta_item.value, ast.Constant):
                                    return meta_item.value.value
        return None

    def _get_method(self, class_node, method_name):
        """Find a method in a class"""
        for item in class_node.body:
            if isinstance(item, ast.FunctionDef) and item.name == method_name:
                return item
        return None

    def _get_url_pattern_from_method(self, method_node):
        """Extract URL pattern from get_absolute_url method"""
        for node in ast.walk(method_node):
            if isinstance(node, ast.Call):
                # Look for reverse() call
                if isinstance(node.func, ast.Name) and node.func.id == "reverse":
                    if node.args and isinstance(node.args[0], ast.Constant):
                        return node.args[0].value
        return None

    def test_outage_class_exists(self):
        """Test that Outage class exists (renamed from CircuitOutage)"""
        tree = self._get_models_file_ast()
        class_node = self._find_class(tree, "Outage")

        self.assertIsNotNone(
            class_node,
            "Outage class not found in models.py. Should be renamed from CircuitOutage",
        )

    def test_outage_verbose_name(self):
        """Test that Outage has correct verbose_name without 'Circuit' prefix"""
        tree = self._get_models_file_ast()
        class_node = self._find_class(tree, "Outage")

        self.assertIsNotNone(class_node)

        verbose_name = self._get_meta_attribute(class_node, "verbose_name")
        self.assertEqual(
            verbose_name,
            "Outage",
            "verbose_name should be 'Outage' (not 'Circuit Outage')",
        )

    def test_outage_verbose_name_plural(self):
        """Test that Outage has correct verbose_name_plural without 'Circuit' prefix"""
        tree = self._get_models_file_ast()
        class_node = self._find_class(tree, "Outage")

        self.assertIsNotNone(class_node)

        verbose_name_plural = self._get_meta_attribute(
            class_node, "verbose_name_plural"
        )
        self.assertEqual(
            verbose_name_plural,
            "Outages",
            "verbose_name_plural should be 'Outages' (not 'Circuit Outages')",
        )

    def test_outage_url_pattern(self):
        """Test that get_absolute_url uses correct URL pattern"""
        tree = self._get_models_file_ast()
        class_node = self._find_class(tree, "Outage")

        self.assertIsNotNone(class_node)

        method_node = self._get_method(class_node, "get_absolute_url")
        self.assertIsNotNone(method_node, "get_absolute_url method not found")

        url_pattern = self._get_url_pattern_from_method(method_node)
        self.assertEqual(
            url_pattern,
            "plugins:notices:outage",
            "URL pattern should be 'plugins:notices:outage' (not 'plugins:netbox_circuitmaintenance:circuitoutage')",
        )
