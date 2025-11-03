"""
Unit tests for Impact model with GenericForeignKey support.
Tests that the Impact model structure is correct by parsing the source code.
This approach works without requiring full NetBox/Django setup.
"""

import ast
import os
import unittest


class TestImpactModelStructure(unittest.TestCase):
    """AST-based tests for Impact model structure (works without Django/NetBox)"""

    def _get_models_file_ast(self):
        """Parse the models.py file and return AST"""
        models_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "vendor_notification",
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

    def _get_meta_attributes(self, class_node):
        """Extract Meta class attributes"""
        meta_attrs = {}
        for item in class_node.body:
            if isinstance(item, ast.ClassDef) and item.name == "Meta":
                for meta_item in item.body:
                    if isinstance(meta_item, ast.Assign):
                        for target in meta_item.targets:
                            if isinstance(target, ast.Name):
                                meta_attrs[target.id] = meta_item.value
        return meta_attrs

    def test_impact_model_exists(self):
        """Test that Impact class exists"""
        tree = self._get_models_file_ast()
        class_node = self._find_class(tree, "Impact")
        self.assertIsNotNone(
            class_node, "Impact class not found in models.py"
        )

    def test_impact_inherits_from_netbox_model(self):
        """Test that Impact inherits from NetBoxModel"""
        tree = self._get_models_file_ast()
        class_node = self._find_class(tree, "Impact")
        self.assertIsNotNone(class_node)

        base_class = self._get_base_class_name(class_node)
        self.assertEqual(
            base_class,
            "NetBoxModel",
            f"Impact should inherit from NetBoxModel, got {base_class}",
        )

    def test_impact_has_event_content_type_field(self):
        """Test that Impact has event_content_type field for GenericForeignKey"""
        tree = self._get_models_file_ast()
        class_node = self._find_class(tree, "Impact")
        self.assertIsNotNone(class_node)

        fields = self._get_field_names(class_node)
        self.assertIn("event_content_type", fields,
                      "Impact should define 'event_content_type' field")

    def test_impact_has_event_object_id_field(self):
        """Test that Impact has event_object_id field for GenericForeignKey"""
        tree = self._get_models_file_ast()
        class_node = self._find_class(tree, "Impact")
        self.assertIsNotNone(class_node)

        fields = self._get_field_names(class_node)
        self.assertIn("event_object_id", fields,
                      "Impact should define 'event_object_id' field")

    def test_impact_has_event_generic_foreign_key(self):
        """Test that Impact has event GenericForeignKey"""
        tree = self._get_models_file_ast()
        class_node = self._find_class(tree, "Impact")
        self.assertIsNotNone(class_node)

        fields = self._get_field_names(class_node)
        self.assertIn("event", fields,
                      "Impact should define 'event' GenericForeignKey")

    def test_impact_has_target_content_type_field(self):
        """Test that Impact has target_content_type field for GenericForeignKey"""
        tree = self._get_models_file_ast()
        class_node = self._find_class(tree, "Impact")
        self.assertIsNotNone(class_node)

        fields = self._get_field_names(class_node)
        self.assertIn("target_content_type", fields,
                      "Impact should define 'target_content_type' field")

    def test_impact_has_target_object_id_field(self):
        """Test that Impact has target_object_id field for GenericForeignKey"""
        tree = self._get_models_file_ast()
        class_node = self._find_class(tree, "Impact")
        self.assertIsNotNone(class_node)

        fields = self._get_field_names(class_node)
        self.assertIn("target_object_id", fields,
                      "Impact should define 'target_object_id' field")

    def test_impact_has_target_generic_foreign_key(self):
        """Test that Impact has target GenericForeignKey"""
        tree = self._get_models_file_ast()
        class_node = self._find_class(tree, "Impact")
        self.assertIsNotNone(class_node)

        fields = self._get_field_names(class_node)
        self.assertIn("target", fields,
                      "Impact should define 'target' GenericForeignKey")

    def test_impact_has_impact_field(self):
        """Test that Impact has impact field"""
        tree = self._get_models_file_ast()
        class_node = self._find_class(tree, "Impact")
        self.assertIsNotNone(class_node)

        fields = self._get_field_names(class_node)
        self.assertIn("impact", fields, "Impact should define 'impact' field")

    def test_impact_has_clean_method(self):
        """Test that Impact has clean method for validation"""
        tree = self._get_models_file_ast()
        class_node = self._find_class(tree, "Impact")
        self.assertIsNotNone(class_node)

        self.assertTrue(
            self._has_method(class_node, "clean"),
            "Impact should define clean() method for validation",
        )

    def test_impact_has_get_absolute_url_method(self):
        """Test that Impact has get_absolute_url method"""
        tree = self._get_models_file_ast()
        class_node = self._find_class(tree, "Impact")
        self.assertIsNotNone(class_node)

        self.assertTrue(
            self._has_method(class_node, "get_absolute_url"),
            "Impact should define get_absolute_url() method",
        )

    def test_impact_has_get_impact_color_method(self):
        """Test that Impact has get_impact_color method"""
        tree = self._get_models_file_ast()
        class_node = self._find_class(tree, "Impact")
        self.assertIsNotNone(class_node)

        self.assertTrue(
            self._has_method(class_node, "get_impact_color"),
            "Impact should define get_impact_color() method",
        )

    def test_impact_has_unique_together_in_meta(self):
        """Test that Impact has unique_together constraint in Meta"""
        tree = self._get_models_file_ast()
        class_node = self._find_class(tree, "Impact")
        self.assertIsNotNone(class_node)

        meta_attrs = self._get_meta_attributes(class_node)
        self.assertIn("unique_together", meta_attrs,
                      "Impact Meta should define 'unique_together' constraint")

    def test_circuit_maintenance_impact_removed(self):
        """Test that old CircuitMaintenanceImpact class is removed"""
        tree = self._get_models_file_ast()
        class_node = self._find_class(tree, "CircuitMaintenanceImpact")
        self.assertIsNone(
            class_node,
            "CircuitMaintenanceImpact should be removed (replaced by Impact)"
        )

    def test_impact_clean_validates_allowed_content_types(self):
        """Test that Impact.clean() validates target_content_type against allowed types"""
        tree = self._get_models_file_ast()
        class_node = self._find_class(tree, "Impact")
        self.assertIsNotNone(class_node)

        # Find the clean method
        clean_method = None
        for item in class_node.body:
            if isinstance(item, ast.FunctionDef) and item.name == "clean":
                clean_method = item
                break

        self.assertIsNotNone(clean_method, "Impact should have clean() method")

        # Convert clean method to source code string for validation
        method_source = ast.unparse(clean_method)

        # Check that clean() imports/calls get_allowed_content_types
        self.assertIn(
            "get_allowed_content_types",
            method_source,
            "Impact.clean() should call get_allowed_content_types() to validate target"
        )

        # Check that clean() validates target_content_type
        self.assertIn(
            "target_content_type",
            method_source,
            "Impact.clean() should validate target_content_type"
        )

        # Check that clean() raises ValidationError for disallowed types
        self.assertIn(
            "ValidationError",
            method_source,
            "Impact.clean() should raise ValidationError for disallowed content types"
        )

        # Check that the validation compares against allowed_types
        self.assertIn(
            "not in",
            method_source,
            "Impact.clean() should check if type is not in allowed_types"
        )


# Functional tests using Django TestCase
# These tests require Django/NetBox to be available and properly configured
# NOTE: These tests require a full NetBox environment (e.g., DevContainer or runserver)
# to run successfully. They will fail in basic pytest environments.
try:
    import pytest
    from django.test import TestCase, override_settings

    @pytest.mark.django_db
    class TestImpactValidation(TestCase):
        """Functional tests for Impact validation (requires full NetBox environment)"""

        @classmethod
        def setUpTestData(cls):
            from django.utils import timezone
            from datetime import timedelta
            from circuits.models import Provider, Circuit, CircuitType
            from dcim.models import Site
            from vendor_notification.models import Maintenance

            cls.provider = Provider.objects.create(name="Test Provider", slug="test-provider")
            cls.circuit_type = CircuitType.objects.create(name="Test Type", slug="test-type")
            cls.circuit = Circuit.objects.create(cid="TEST-001", provider=cls.provider, type=cls.circuit_type)
            cls.site = Site.objects.create(name="Test Site", slug="test-site")
            cls.maintenance = Maintenance.objects.create(
                name="MAINT-001",
                summary="Test",
                provider=cls.provider,
                start=timezone.now(),
                end=timezone.now() + timedelta(hours=4),
                status="CONFIRMED"
            )

        @override_settings(
            PLUGINS_CONFIG={
                'vendor_notification': {
                    'allowed_content_types': ['circuits.Circuit']
                }
            }
        )
        def test_validation_disallowed_content_type(self):
            """Test that non-configured content types are rejected"""
            from django.core.exceptions import ValidationError
            from vendor_notification.models import Impact

            impact = Impact(
                event=self.maintenance,
                target=self.site,
                impact="OUTAGE"
            )

            with self.assertRaises(ValidationError) as cm:
                impact.full_clean()

            self.assertIn('target_content_type', cm.exception.message_dict)
            self.assertIn('not allowed', str(cm.exception))

except ImportError:
    # Django/NetBox not available - skip functional tests
    pass
