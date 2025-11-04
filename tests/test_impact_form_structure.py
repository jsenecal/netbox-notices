"""
Unit tests for ImpactForm structure.
These tests validate the code structure by reading the source file directly.
This approach works without requiring full Django model setup.
"""

import ast
import os
import unittest


class TestImpactFormStructure(unittest.TestCase):
    """Test the ImpactForm class structure"""

    def _get_forms_file_ast(self):
        """Parse the forms.py file and return AST"""
        forms_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "vendor_notification",
            "forms.py",
        )
        with open(forms_path, "r") as f:
            return ast.parse(f.read())

    def _find_class(self, tree, class_name):
        """Find a class definition in the AST"""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                return node
        return None

    def _get_meta_fields(self, class_node):
        """Extract fields tuple from Meta class"""
        for item in class_node.body:
            if isinstance(item, ast.ClassDef) and item.name == "Meta":
                for meta_item in item.body:
                    if isinstance(meta_item, ast.Assign):
                        for target in meta_item.targets:
                            if isinstance(target, ast.Name) and target.id == "fields":
                                if isinstance(meta_item.value, ast.Tuple):
                                    fields = []
                                    for elt in meta_item.value.elts:
                                        if isinstance(elt, ast.Constant):
                                            fields.append(elt.value)
                                    return tuple(fields)
        return None

    def test_impact_form_class_exists(self):
        """Test that ImpactForm class is defined"""
        tree = self._get_forms_file_ast()
        impact_form = self._find_class(tree, "ImpactForm")
        self.assertIsNotNone(impact_form, "ImpactForm class not found in forms.py")

    def test_impact_form_has_meta_class(self):
        """Test that ImpactForm has a Meta class"""
        tree = self._get_forms_file_ast()
        impact_form = self._find_class(tree, "ImpactForm")
        self.assertIsNotNone(impact_form)

        # Check for Meta class
        has_meta = False
        for item in impact_form.body:
            if isinstance(item, ast.ClassDef) and item.name == "Meta":
                has_meta = True
                break
        self.assertTrue(has_meta, "ImpactForm does not have a Meta class")

    def test_impact_form_meta_fields(self):
        """Test that ImpactForm.Meta.fields includes GenericForeignKey fields"""
        tree = self._get_forms_file_ast()
        impact_form = self._find_class(tree, "ImpactForm")
        self.assertIsNotNone(impact_form)

        fields = self._get_meta_fields(impact_form)
        self.assertIsNotNone(fields, "ImpactForm.Meta.fields not found")

        expected_fields = (
            "event_content_type",
            "event_object_id",
            "target_content_type",
            "target_object_id",
            "impact",
            "tags",
        )
        self.assertEqual(fields, expected_fields, f"ImpactForm.Meta.fields = {fields}, expected {expected_fields}")

    def test_impact_form_has_content_type_fields(self):
        """Test that ImpactForm defines event_content_type and target_content_type fields"""
        tree = self._get_forms_file_ast()
        impact_form = self._find_class(tree, "ImpactForm")
        self.assertIsNotNone(impact_form)

        # Look for field assignments in the class body
        field_names = []
        for item in impact_form.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        field_names.append(target.id)

        self.assertIn("event_content_type", field_names, "event_content_type field not defined in ImpactForm")
        self.assertIn("target_content_type", field_names, "target_content_type field not defined in ImpactForm")

    def test_impact_form_uses_content_type_choice_field(self):
        """Test that ImpactForm uses ContentTypeChoiceField for content type fields"""
        tree = self._get_forms_file_ast()
        impact_form = self._find_class(tree, "ImpactForm")
        self.assertIsNotNone(impact_form)

        # Check that ContentTypeChoiceField is used
        found_content_type_field = False
        for item in impact_form.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and target.id in ["event_content_type", "target_content_type"]:
                        # Check if value is a Call to ContentTypeChoiceField
                        if isinstance(item.value, ast.Call):
                            if isinstance(item.value.func, ast.Name):
                                if item.value.func.id == "ContentTypeChoiceField":
                                    found_content_type_field = True

        self.assertTrue(found_content_type_field, "ImpactForm does not use ContentTypeChoiceField")

    def test_impact_form_has_init_method(self):
        """Test that ImpactForm has an __init__ method (for filtering allowed types)"""
        tree = self._get_forms_file_ast()
        impact_form = self._find_class(tree, "ImpactForm")
        self.assertIsNotNone(impact_form)

        # Look for __init__ method
        has_init = False
        for item in impact_form.body:
            if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                has_init = True
                break

        self.assertTrue(has_init, "ImpactForm does not have __init__ method for filtering content types")

    def test_forms_imports_utils(self):
        """Test that forms.py imports get_allowed_content_types from utils"""
        tree = self._get_forms_file_ast()

        # Check for import (relative import .utils shows as just "utils" in AST)
        found_import = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "utils":
                    for alias in node.names:
                        if alias.name == "get_allowed_content_types":
                            found_import = True

        self.assertTrue(found_import, "forms.py does not import get_allowed_content_types from utils")


class TestEventNotificationFormStructure(unittest.TestCase):
    """Test the EventNotificationForm class structure"""

    def _get_forms_file_ast(self):
        """Parse the forms.py file and return AST"""
        forms_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "vendor_notification",
            "forms.py",
        )
        with open(forms_path, "r") as f:
            return ast.parse(f.read())

    def _find_class(self, tree, class_name):
        """Find a class definition in the AST"""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                return node
        return None

    def test_event_notification_form_exists(self):
        """Test that EventNotificationForm class is defined"""
        tree = self._get_forms_file_ast()
        form = self._find_class(tree, "EventNotificationForm")
        self.assertIsNotNone(form, "EventNotificationForm class not found in forms.py")

    def test_event_notification_form_has_event_content_type(self):
        """Test that EventNotificationForm has event_content_type field"""
        tree = self._get_forms_file_ast()
        form = self._find_class(tree, "EventNotificationForm")
        self.assertIsNotNone(form)

        # Look for field assignments
        field_names = []
        for item in form.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        field_names.append(target.id)

        self.assertIn(
            "event_content_type", field_names, "event_content_type field not defined in EventNotificationForm"
        )


if __name__ == "__main__":
    unittest.main()
