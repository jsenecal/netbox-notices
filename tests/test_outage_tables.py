"""
Tests for CircuitOutage tables.
These tests validate the code structure by reading the source file directly.
This approach works without requiring NetBox installation.
"""

import ast
import os
import unittest


class TestCircuitOutageTable(unittest.TestCase):
    """Test the CircuitOutageTable class structure"""

    def _get_tables_file_ast(self):
        """Parse the tables.py file and return AST"""
        tables_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "vendor_notification",
            "tables.py",
        )
        with open(tables_path, "r") as f:
            return ast.parse(f.read())

    def _find_class(self, tree, class_name):
        """Find a class definition in the AST"""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                return node
        return None

    def test_circuit_outage_table_exists(self):
        """Test that CircuitOutageTable is defined"""
        tree = self._get_tables_file_ast()
        class_node = self._find_class(tree, "CircuitOutageTable")
        self.assertIsNotNone(class_node, "CircuitOutageTable class not found")

    def test_circuit_outage_table_has_column_definitions(self):
        """Test that table defines expected column attributes"""
        tree = self._get_tables_file_ast()
        class_node = self._find_class(tree, "CircuitOutageTable")

        if class_node is None:
            self.fail("CircuitOutageTable class not found")

        # Check for column definitions in class body
        column_names = []
        for item in class_node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        column_names.append(target.id)

        expected_columns = [
            "name",
            "provider",
            "status",
            "start",
            "end",
            "estimated_time_to_repair",
        ]

        for col in expected_columns:
            self.assertIn(col, column_names, f"Missing column definition: {col}")
