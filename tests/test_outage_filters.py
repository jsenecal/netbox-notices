"""
Unit tests for CircuitOutage filtersets.
These tests validate the code structure by reading the source file directly.
This approach works without requiring NetBox installation.
"""

import ast
import os
import unittest


class TestCircuitOutageFilterSet(unittest.TestCase):
    """Test the CircuitOutageFilterSet class structure"""

    def _get_filtersets_file_ast(self):
        """Parse the filtersets.py file and return AST"""
        filtersets_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "vendor_notification",
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

    def test_circuit_outage_filterset_exists(self):
        """Test that CircuitOutageFilterSet is defined"""
        tree = self._get_filtersets_file_ast()
        class_node = self._find_class(tree, "CircuitOutageFilterSet")
        self.assertIsNotNone(class_node, "CircuitOutageFilterSet class not found in filtersets.py")

    def test_circuit_outage_filterset_fields(self):
        """Test that filterset includes key filter fields"""
        tree = self._get_filtersets_file_ast()
        class_node = self._find_class(tree, "CircuitOutageFilterSet")
        self.assertIsNotNone(class_node, "CircuitOutageFilterSet class not found")

        fields = self._get_meta_fields(class_node)
        expected_fields = ["name", "status", "provider", "start", "end"]

        for field in expected_fields:
            self.assertIn(field, fields, f"Missing expected filter field: {field}")
