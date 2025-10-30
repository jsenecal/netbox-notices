"""
Tests for CircuitOutage views.
These tests validate the code structure by reading the source file directly.
This approach works without requiring NetBox installation.
"""

import ast
import os
import unittest


class TestCircuitOutageViews(unittest.TestCase):
    """Test the CircuitOutage view classes structure"""

    def _get_views_file_ast(self):
        """Parse the views.py file and return AST"""
        views_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "netbox_circuitmaintenance",
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

    def test_circuit_outage_views_exist(self):
        """Test that all CircuitOutage views are defined"""
        tree = self._get_views_file_ast()

        view_classes = [
            "CircuitOutageListView",
            "CircuitOutageView",
            "CircuitOutageEditView",
            "CircuitOutageDeleteView",
        ]

        for view_class in view_classes:
            class_node = self._find_class(tree, view_class)
            self.assertIsNotNone(
                class_node, f"{view_class} class not found"
            )

    def test_circuit_outage_list_view_has_queryset(self):
        """Test that list view defines queryset attribute"""
        tree = self._get_views_file_ast()
        class_node = self._find_class(tree, "CircuitOutageListView")

        if class_node is None:
            self.fail("CircuitOutageListView class not found")

        # Check for queryset attribute
        has_queryset = False
        for item in class_node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and target.id == "queryset":
                        has_queryset = True
                        break

        self.assertTrue(has_queryset, "CircuitOutageListView missing queryset attribute")

    def test_circuit_outage_list_view_has_table(self):
        """Test that list view defines table attribute"""
        tree = self._get_views_file_ast()
        class_node = self._find_class(tree, "CircuitOutageListView")

        if class_node is None:
            self.fail("CircuitOutageListView class not found")

        # Check for table attribute
        has_table = False
        for item in class_node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and target.id == "table":
                        has_table = True
                        break

        self.assertTrue(has_table, "CircuitOutageListView missing table attribute")
