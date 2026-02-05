"""
Tests for notices tables.
These tests validate the code structure by reading the source file directly.
This approach works without requiring NetBox installation.
"""

import ast
import os
import unittest


class BaseTableTest(unittest.TestCase):
    """Base class for table tests with common helper methods"""

    def _get_tables_file_ast(self):
        """Parse the tables.py file and return AST"""
        tables_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "notices",
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

    def _find_meta_class(self, class_node):
        """Find the Meta class within a table class"""
        for item in class_node.body:
            if isinstance(item, ast.ClassDef) and item.name == "Meta":
                return item
        return None

    def _get_class_attributes(self, class_node):
        """Get all attribute assignments in a class"""
        attributes = {}
        for item in class_node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        attributes[target.id] = item.value
        return attributes

    def _get_meta_field_names(self, meta_node):
        """Extract field names from Meta.fields tuple"""
        for item in meta_node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and target.id == "fields":
                        if isinstance(item.value, ast.Tuple):
                            return [elt.value for elt in item.value.elts if isinstance(elt, ast.Constant)]
        return []

    def _get_meta_default_columns(self, meta_node):
        """Extract default column names from Meta.default_columns tuple"""
        for item in meta_node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and target.id == "default_columns":
                        if isinstance(item.value, ast.Tuple):
                            return [elt.value for elt in item.value.elts if isinstance(elt, ast.Constant)]
        return []


class TestMaintenanceTable(BaseTableTest):
    """Test the MaintenanceTable class structure"""

    def test_maintenance_table_exists(self):
        """Test that MaintenanceTable is defined"""
        tree = self._get_tables_file_ast()
        class_node = self._find_class(tree, "MaintenanceTable")
        self.assertIsNotNone(class_node, "MaintenanceTable class not found")

    def test_maintenance_table_has_column_definitions(self):
        """Test that table defines expected column attributes"""
        tree = self._get_tables_file_ast()
        class_node = self._find_class(tree, "MaintenanceTable")

        if class_node is None:
            self.fail("MaintenanceTable class not found")

        # Check for column definitions in class body
        attributes = self._get_class_attributes(class_node)

        expected_columns = [
            "name",
            "provider",
            "status",
            "impact_count",
            "summary",
        ]

        for col in expected_columns:
            self.assertIn(col, attributes, f"Missing column definition: {col}")

    def test_maintenance_table_has_meta_class(self):
        """Test that MaintenanceTable has a Meta class"""
        tree = self._get_tables_file_ast()
        class_node = self._find_class(tree, "MaintenanceTable")
        meta_node = self._find_meta_class(class_node)
        self.assertIsNotNone(meta_node, "MaintenanceTable.Meta class not found")

    def test_maintenance_table_meta_fields(self):
        """Test that Meta.fields includes all expected fields"""
        tree = self._get_tables_file_ast()
        class_node = self._find_class(tree, "MaintenanceTable")
        meta_node = self._find_meta_class(class_node)

        field_names = self._get_meta_field_names(meta_node)

        expected_fields = [
            "pk",
            "id",
            "name",
            "summary",
            "status",
            "provider",
            "start",
            "end",
            "internal_ticket",
            "acknowledged",
            "impact_count",
            "actions",
        ]

        for field in expected_fields:
            self.assertIn(field, field_names, f"Missing field in Meta.fields: {field}")


class TestOutageTable(BaseTableTest):
    """Test the OutageTable class structure"""

    def test_outage_table_exists(self):
        """Test that OutageTable is defined"""
        tree = self._get_tables_file_ast()
        class_node = self._find_class(tree, "OutageTable")
        self.assertIsNotNone(class_node, "OutageTable class not found")

    def test_outage_table_has_column_definitions(self):
        """Test that table defines expected column attributes"""
        tree = self._get_tables_file_ast()
        class_node = self._find_class(tree, "OutageTable")

        if class_node is None:
            self.fail("OutageTable class not found")

        # Check for column definitions in class body
        attributes = self._get_class_attributes(class_node)

        expected_columns = [
            "name",
            "provider",
            "status",
            "start",
            "end",
            "estimated_time_to_repair",
        ]

        for col in expected_columns:
            self.assertIn(col, attributes, f"Missing column definition: {col}")

    def test_outage_table_has_meta_class(self):
        """Test that OutageTable has a Meta class"""
        tree = self._get_tables_file_ast()
        class_node = self._find_class(tree, "OutageTable")
        meta_node = self._find_meta_class(class_node)
        self.assertIsNotNone(meta_node, "OutageTable.Meta class not found")

    def test_outage_table_meta_fields(self):
        """Test that Meta.fields includes all expected fields"""
        tree = self._get_tables_file_ast()
        class_node = self._find_class(tree, "OutageTable")
        meta_node = self._find_meta_class(class_node)

        field_names = self._get_meta_field_names(meta_node)

        expected_fields = [
            "pk",
            "name",
            "provider",
            "summary",
            "status",
            "start",
            "end",
            "estimated_time_to_repair",
            "internal_ticket",
            "acknowledged",
            "created",
        ]

        for field in expected_fields:
            self.assertIn(field, field_names, f"Missing field in Meta.fields: {field}")


class TestImpactTable(BaseTableTest):
    """Test the ImpactTable class structure"""

    def test_impact_table_exists(self):
        """Test that ImpactTable is defined"""
        tree = self._get_tables_file_ast()
        class_node = self._find_class(tree, "ImpactTable")
        self.assertIsNotNone(class_node, "ImpactTable class not found")

    def test_impact_table_has_column_definitions(self):
        """Test that table defines expected column attributes including GenericForeignKey columns"""
        tree = self._get_tables_file_ast()
        class_node = self._find_class(tree, "ImpactTable")

        if class_node is None:
            self.fail("ImpactTable class not found")

        # Check for column definitions in class body
        attributes = self._get_class_attributes(class_node)

        expected_columns = [
            "event",  # GenericForeignKey to Maintenance/Outage
            "event_type",  # ContentType display
            "target",  # GenericForeignKey to impacted object
            "target_type",  # ContentType display
            "impact",  # Impact level
        ]

        for col in expected_columns:
            self.assertIn(col, attributes, f"Missing column definition: {col}")

    def test_impact_table_has_meta_class(self):
        """Test that ImpactTable has a Meta class"""
        tree = self._get_tables_file_ast()
        class_node = self._find_class(tree, "ImpactTable")
        meta_node = self._find_meta_class(class_node)
        self.assertIsNotNone(meta_node, "ImpactTable.Meta class not found")

    def test_impact_table_meta_fields(self):
        """Test that Meta.fields includes all expected fields"""
        tree = self._get_tables_file_ast()
        class_node = self._find_class(tree, "ImpactTable")
        meta_node = self._find_meta_class(class_node)

        field_names = self._get_meta_field_names(meta_node)

        expected_fields = [
            "pk",
            "id",
            "event",
            "event_type",
            "target",
            "target_type",
            "impact",
            "created",
            "last_updated",
            "actions",
        ]

        for field in expected_fields:
            self.assertIn(field, field_names, f"Missing field in Meta.fields: {field}")

    def test_impact_table_default_columns(self):
        """Test that ImpactTable has reasonable default columns"""
        tree = self._get_tables_file_ast()
        class_node = self._find_class(tree, "ImpactTable")
        meta_node = self._find_meta_class(class_node)

        default_columns = self._get_meta_default_columns(meta_node)

        # Should include the key columns for GenericForeignKey display
        expected_defaults = [
            "event",
            "event_type",
            "target",
            "target_type",
            "impact",
        ]

        for col in expected_defaults:
            self.assertIn(col, default_columns, f"Missing default column: {col}")


class TestEventNotificationTable(BaseTableTest):
    """Test the EventNotificationTable class structure"""

    def test_event_notification_table_exists(self):
        """Test that EventNotificationTable is defined"""
        tree = self._get_tables_file_ast()
        class_node = self._find_class(tree, "EventNotificationTable")
        self.assertIsNotNone(class_node, "EventNotificationTable class not found")

    def test_event_notification_table_has_column_definitions(self):
        """Test that table defines expected column attributes including GenericForeignKey columns"""
        tree = self._get_tables_file_ast()
        class_node = self._find_class(tree, "EventNotificationTable")

        if class_node is None:
            self.fail("EventNotificationTable class not found")

        # Check for column definitions in class body
        attributes = self._get_class_attributes(class_node)

        expected_columns = [
            "event",  # GenericForeignKey to Maintenance/Outage
            "event_type",  # ContentType display
            "subject",
            "email_from",
            "email_received",
            "email_body",
        ]

        for col in expected_columns:
            self.assertIn(col, attributes, f"Missing column definition: {col}")

    def test_event_notification_table_has_meta_class(self):
        """Test that EventNotificationTable has a Meta class"""
        tree = self._get_tables_file_ast()
        class_node = self._find_class(tree, "EventNotificationTable")
        meta_node = self._find_meta_class(class_node)
        self.assertIsNotNone(meta_node, "EventNotificationTable.Meta class not found")

    def test_event_notification_table_meta_fields(self):
        """Test that Meta.fields includes all expected fields"""
        tree = self._get_tables_file_ast()
        class_node = self._find_class(tree, "EventNotificationTable")
        meta_node = self._find_meta_class(class_node)

        field_names = self._get_meta_field_names(meta_node)

        expected_fields = [
            "pk",
            "id",
            "event",
            "event_type",
            "subject",
            "email_from",
            "email_received",
            "email_body",
            "created",
            "actions",
        ]

        for field in expected_fields:
            self.assertIn(field, field_names, f"Missing field in Meta.fields: {field}")

    def test_event_notification_table_default_columns(self):
        """Test that EventNotificationTable has reasonable default columns"""
        tree = self._get_tables_file_ast()
        class_node = self._find_class(tree, "EventNotificationTable")
        meta_node = self._find_meta_class(class_node)

        default_columns = self._get_meta_default_columns(meta_node)

        # Should include the key columns for GenericForeignKey display and email info
        expected_defaults = [
            "event",
            "event_type",
            "subject",
            "email_from",
            "email_received",
        ]

        for col in expected_defaults:
            self.assertIn(col, default_columns, f"Missing default column: {col}")


class TestTableImports(BaseTableTest):
    """Test that tables.py has correct imports"""

    def test_imports_exist(self):
        """Test that necessary imports are present"""
        tree = self._get_tables_file_ast()

        # Check for key imports
        imports_found = {
            "django_tables2": False,
            "NetBoxTable": False,
            "columns": False,
            "Maintenance": False,
            "Outage": False,
            "Impact": False,
            "EventNotification": False,
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "django_tables2":
                        imports_found["django_tables2"] = True

            if isinstance(node, ast.ImportFrom):
                if node.module == "netbox.tables":
                    for alias in node.names:
                        if alias.name == "NetBoxTable":
                            imports_found["NetBoxTable"] = True
                        if alias.name == "columns":
                            imports_found["columns"] = True

                # Check both ".models" and "models" (AST may normalize the relative import)
                if node.module in (".models", "models"):
                    for alias in node.names:
                        if alias.name == "Maintenance":
                            imports_found["Maintenance"] = True
                        if alias.name == "Outage":
                            imports_found["Outage"] = True
                        if alias.name == "Impact":
                            imports_found["Impact"] = True
                        if alias.name == "EventNotification":
                            imports_found["EventNotification"] = True

        for import_name, found in imports_found.items():
            self.assertTrue(found, f"Missing import: {import_name}")


if __name__ == "__main__":
    unittest.main()
