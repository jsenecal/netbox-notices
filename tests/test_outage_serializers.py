"""
Tests for API serializers (Maintenance, Outage, Impact, EventNotification).
These tests validate the serializer structure by reading the source file directly.
This approach works without requiring NetBox installation.
"""

import ast
import os
import unittest


class TestOutageSerializerStructure(unittest.TestCase):
    """Test the OutageSerializer class structure"""

    def _get_serializers_file_ast(self):
        """Parse the serializers.py file and return AST"""
        serializers_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "vendor_notification",
            "api",
            "serializers.py",
        )
        with open(serializers_path, "r") as f:
            return ast.parse(f.read())

    def _find_class(self, tree, class_name):
        """Find a class definition in the AST"""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                return node
        return None

    def _find_class_attr(self, class_node, attr_name):
        """Find a class attribute assignment"""
        for node in class_node.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == attr_name:
                        return node
        return None

    def _find_meta_class(self, class_node):
        """Find the Meta inner class"""
        for node in class_node.body:
            if isinstance(node, ast.ClassDef) and node.name == "Meta":
                return node
        return None

    def _get_meta_attribute(self, meta_node, attr_name):
        """Get a Meta class attribute value"""
        for node in meta_node.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == attr_name:
                        return node.value
        return None

    def _get_tuple_elements(self, node):
        """Extract string elements from a tuple"""
        if isinstance(node, ast.Tuple):
            return [elt.value for elt in node.elts if isinstance(elt, ast.Constant)]
        return []

    def test_outage_serializer_exists(self):
        """Test that OutageSerializer class exists"""
        tree = self._get_serializers_file_ast()
        serializer_class = self._find_class(tree, "OutageSerializer")
        self.assertIsNotNone(serializer_class, "OutageSerializer class should exist")

    def test_outage_serializer_inherits_from_netbox_model_serializer(self):
        """Test that OutageSerializer inherits from NetBoxModelSerializer"""
        tree = self._get_serializers_file_ast()
        serializer_class = self._find_class(tree, "OutageSerializer")
        self.assertIsNotNone(serializer_class)

        # Check base classes
        base_names = [base.id for base in serializer_class.bases if hasattr(base, "id")]
        self.assertIn(
            "NetBoxModelSerializer",
            base_names,
            "OutageSerializer should inherit from NetBoxModelSerializer",
        )

    def test_outage_serializer_has_url_field(self):
        """Test that OutageSerializer has url field"""
        tree = self._get_serializers_file_ast()
        serializer_class = self._find_class(tree, "OutageSerializer")
        self.assertIsNotNone(serializer_class)

        # Look for url field assignment
        url_field = self._find_class_attr(serializer_class, "url")
        self.assertIsNotNone(url_field, "OutageSerializer should have a url field")

    def test_outage_serializer_has_provider_field(self):
        """Test that OutageSerializer has provider field"""
        tree = self._get_serializers_file_ast()
        serializer_class = self._find_class(tree, "OutageSerializer")
        self.assertIsNotNone(serializer_class)

        # Look for provider field assignment
        provider_field = self._find_class_attr(serializer_class, "provider")
        self.assertIsNotNone(provider_field, "OutageSerializer should have a provider field")

    def test_outage_serializer_has_meta_class(self):
        """Test that OutageSerializer has Meta class"""
        tree = self._get_serializers_file_ast()
        serializer_class = self._find_class(tree, "OutageSerializer")
        self.assertIsNotNone(serializer_class)

        meta_class = self._find_meta_class(serializer_class)
        self.assertIsNotNone(meta_class, "OutageSerializer should have a Meta class")

    def test_outage_serializer_meta_has_model(self):
        """Test that Meta class specifies model"""
        tree = self._get_serializers_file_ast()
        serializer_class = self._find_class(tree, "OutageSerializer")
        self.assertIsNotNone(serializer_class)

        meta_class = self._find_meta_class(serializer_class)
        self.assertIsNotNone(meta_class)

        model_attr = self._get_meta_attribute(meta_class, "model")
        self.assertIsNotNone(model_attr, "Meta class should specify model attribute")

    def test_outage_serializer_meta_has_fields(self):
        """Test that Meta class specifies fields tuple"""
        tree = self._get_serializers_file_ast()
        serializer_class = self._find_class(tree, "OutageSerializer")
        self.assertIsNotNone(serializer_class)

        meta_class = self._find_meta_class(serializer_class)
        self.assertIsNotNone(meta_class)

        fields_attr = self._get_meta_attribute(meta_class, "fields")
        self.assertIsNotNone(fields_attr, "Meta class should specify fields attribute")

    def test_outage_serializer_has_required_fields(self):
        """Test that OutageSerializer includes all required fields"""
        tree = self._get_serializers_file_ast()
        serializer_class = self._find_class(tree, "OutageSerializer")
        self.assertIsNotNone(serializer_class)

        meta_class = self._find_meta_class(serializer_class)
        self.assertIsNotNone(meta_class)

        fields_attr = self._get_meta_attribute(meta_class, "fields")
        self.assertIsNotNone(fields_attr)

        # Extract field names from tuple
        field_names = self._get_tuple_elements(fields_attr)

        # Required fields based on design spec
        required_fields = {
            "id",
            "url",
            "display",
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
            "impacts",
            "notifications",
            "comments",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        }

        # Check that all required fields are present
        for field in required_fields:
            self.assertIn(
                field,
                field_names,
                f"Field '{field}' should be in OutageSerializer.Meta.fields",
            )


class TestNestedOutageSerializer(unittest.TestCase):
    """Test the NestedOutageSerializer class structure"""

    def _get_serializers_file_ast(self):
        """Parse the serializers.py file and return AST"""
        serializers_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "vendor_notification",
            "api",
            "serializers.py",
        )
        with open(serializers_path, "r") as f:
            return ast.parse(f.read())

    def _find_class(self, tree, class_name):
        """Find a class definition in the AST"""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                return node
        return None

    def test_nested_outage_serializer_exists(self):
        """Test that NestedOutageSerializer class exists"""
        tree = self._get_serializers_file_ast()
        serializer_class = self._find_class(tree, "NestedOutageSerializer")
        self.assertIsNotNone(serializer_class, "NestedOutageSerializer class should exist")

    def test_nested_outage_serializer_inherits_from_writable_nested_serializer(
        self,
    ):
        """Test that NestedOutageSerializer inherits from WritableNestedSerializer"""
        tree = self._get_serializers_file_ast()
        serializer_class = self._find_class(tree, "NestedOutageSerializer")
        self.assertIsNotNone(serializer_class)

        # Check base classes
        base_names = [base.id for base in serializer_class.bases if hasattr(base, "id")]
        self.assertIn(
            "WritableNestedSerializer",
            base_names,
            "NestedOutageSerializer should inherit from WritableNestedSerializer",
        )


class TestImpactSerializer(unittest.TestCase):
    """Test the ImpactSerializer class structure"""

    def _get_serializers_file_ast(self):
        """Parse the serializers.py file and return AST"""
        serializers_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "vendor_notification",
            "api",
            "serializers.py",
        )
        with open(serializers_path, "r") as f:
            return ast.parse(f.read())

    def _find_class(self, tree, class_name):
        """Find a class definition in the AST"""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                return node
        return None

    def _find_class_attr(self, class_node, attr_name):
        """Find a class attribute assignment"""
        for node in class_node.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == attr_name:
                        return node
        return None

    def _find_meta_class(self, class_node):
        """Find the Meta inner class"""
        for node in class_node.body:
            if isinstance(node, ast.ClassDef) and node.name == "Meta":
                return node
        return None

    def _get_meta_attribute(self, meta_node, attr_name):
        """Get a Meta class attribute value"""
        for node in meta_node.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == attr_name:
                        return node.value
        return None

    def _get_tuple_elements(self, node):
        """Extract string elements from a tuple"""
        if isinstance(node, ast.Tuple):
            return [elt.value for elt in node.elts if isinstance(elt, ast.Constant)]
        return []

    def test_impact_serializer_exists(self):
        """Test that ImpactSerializer class exists"""
        tree = self._get_serializers_file_ast()
        serializer_class = self._find_class(tree, "ImpactSerializer")
        self.assertIsNotNone(serializer_class, "ImpactSerializer class should exist")

    def test_impact_serializer_inherits_from_netbox_model_serializer(self):
        """Test that ImpactSerializer inherits from NetBoxModelSerializer"""
        tree = self._get_serializers_file_ast()
        serializer_class = self._find_class(tree, "ImpactSerializer")
        self.assertIsNotNone(serializer_class)

        # Check base classes
        base_names = [base.id for base in serializer_class.bases if hasattr(base, "id")]
        self.assertIn(
            "NetBoxModelSerializer",
            base_names,
            "ImpactSerializer should inherit from NetBoxModelSerializer",
        )

    def test_impact_serializer_has_generic_fk_fields(self):
        """Test that ImpactSerializer has GenericForeignKey fields"""
        tree = self._get_serializers_file_ast()
        serializer_class = self._find_class(tree, "ImpactSerializer")
        self.assertIsNotNone(serializer_class)

        # Check for event GenericForeignKey fields
        event_ct = self._find_class_attr(serializer_class, "event_content_type")
        self.assertIsNotNone(event_ct, "Should have event_content_type field")

        event_id = self._find_class_attr(serializer_class, "event_object_id")
        self.assertIsNotNone(event_id, "Should have event_object_id field")

        # Check for target GenericForeignKey fields
        target_ct = self._find_class_attr(serializer_class, "target_content_type")
        self.assertIsNotNone(target_ct, "Should have target_content_type field")

        target_id = self._find_class_attr(serializer_class, "target_object_id")
        self.assertIsNotNone(target_id, "Should have target_object_id field")

    def test_impact_serializer_has_required_fields(self):
        """Test that ImpactSerializer includes all required fields"""
        tree = self._get_serializers_file_ast()
        serializer_class = self._find_class(tree, "ImpactSerializer")
        self.assertIsNotNone(serializer_class)

        meta_class = self._find_meta_class(serializer_class)
        self.assertIsNotNone(meta_class)

        fields_attr = self._get_meta_attribute(meta_class, "fields")
        self.assertIsNotNone(fields_attr)

        field_names = self._get_tuple_elements(fields_attr)

        # Required fields for Impact
        required_fields = {
            "id",
            "url",
            "display",
            "event_content_type",
            "event_object_id",
            "event",
            "target_content_type",
            "target_object_id",
            "target",
            "impact",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        }

        for field in required_fields:
            self.assertIn(
                field,
                field_names,
                f"Field '{field}' should be in ImpactSerializer.Meta.fields",
            )


class TestEventNotificationSerializer(unittest.TestCase):
    """Test the EventNotificationSerializer class structure"""

    def _get_serializers_file_ast(self):
        """Parse the serializers.py file and return AST"""
        serializers_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "vendor_notification",
            "api",
            "serializers.py",
        )
        with open(serializers_path, "r") as f:
            return ast.parse(f.read())

    def _find_class(self, tree, class_name):
        """Find a class definition in the AST"""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                return node
        return None

    def _find_class_attr(self, class_node, attr_name):
        """Find a class attribute assignment"""
        for node in class_node.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == attr_name:
                        return node
        return None

    def _find_meta_class(self, class_node):
        """Find the Meta inner class"""
        for node in class_node.body:
            if isinstance(node, ast.ClassDef) and node.name == "Meta":
                return node
        return None

    def _get_meta_attribute(self, meta_node, attr_name):
        """Get a Meta class attribute value"""
        for node in meta_node.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == attr_name:
                        return node.value
        return None

    def _get_tuple_elements(self, node):
        """Extract string elements from a tuple"""
        if isinstance(node, ast.Tuple):
            return [elt.value for elt in node.elts if isinstance(elt, ast.Constant)]
        return []

    def test_event_notification_serializer_exists(self):
        """Test that EventNotificationSerializer class exists"""
        tree = self._get_serializers_file_ast()
        serializer_class = self._find_class(tree, "EventNotificationSerializer")
        self.assertIsNotNone(serializer_class, "EventNotificationSerializer class should exist")

    def test_event_notification_serializer_inherits_from_netbox_model_serializer(self):
        """Test that EventNotificationSerializer inherits from NetBoxModelSerializer"""
        tree = self._get_serializers_file_ast()
        serializer_class = self._find_class(tree, "EventNotificationSerializer")
        self.assertIsNotNone(serializer_class)

        # Check base classes
        base_names = [base.id for base in serializer_class.bases if hasattr(base, "id")]
        self.assertIn(
            "NetBoxModelSerializer",
            base_names,
            "EventNotificationSerializer should inherit from NetBoxModelSerializer",
        )

    def test_event_notification_serializer_has_generic_fk_fields(self):
        """Test that EventNotificationSerializer has GenericForeignKey fields"""
        tree = self._get_serializers_file_ast()
        serializer_class = self._find_class(tree, "EventNotificationSerializer")
        self.assertIsNotNone(serializer_class)

        # Check for event GenericForeignKey fields
        event_ct = self._find_class_attr(serializer_class, "event_content_type")
        self.assertIsNotNone(event_ct, "Should have event_content_type field")

        event_id = self._find_class_attr(serializer_class, "event_object_id")
        self.assertIsNotNone(event_id, "Should have event_object_id field")

    def test_event_notification_serializer_has_required_fields(self):
        """Test that EventNotificationSerializer includes all required fields"""
        tree = self._get_serializers_file_ast()
        serializer_class = self._find_class(tree, "EventNotificationSerializer")
        self.assertIsNotNone(serializer_class)

        meta_class = self._find_meta_class(serializer_class)
        self.assertIsNotNone(meta_class)

        fields_attr = self._get_meta_attribute(meta_class, "fields")
        self.assertIsNotNone(fields_attr)

        field_names = self._get_tuple_elements(fields_attr)

        # Required fields for EventNotification
        required_fields = {
            "id",
            "url",
            "display",
            "event_content_type",
            "event_object_id",
            "event",
            "email_body",
            "subject",
            "email_from",
            "email_received",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        }

        for field in required_fields:
            self.assertIn(
                field,
                field_names,
                f"Field '{field}' should be in EventNotificationSerializer.Meta.fields",
            )


if __name__ == "__main__":
    unittest.main()
