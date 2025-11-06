"""
Tests for CircuitOutage API ViewSet.
These tests validate the ViewSet structure by reading the source file directly.
This approach works without requiring NetBox installation.
"""

import ast
import os
import unittest


class TestCircuitOutageViewSetStructure(unittest.TestCase):
    """Test the CircuitOutageViewSet class structure"""

    def _get_views_file_ast(self):
        """Parse the views.py file and return AST"""
        views_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "vendor_notification",
            "api",
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

    def _find_class_attr(self, class_node, attr_name):
        """Find a class attribute assignment"""
        for node in class_node.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == attr_name:
                        return node
        return None

    def _get_attr_value_name(self, node):
        """Get the name from an attribute value"""
        if isinstance(node.value, ast.Attribute):
            return node.value.attr
        elif isinstance(node.value, ast.Name):
            return node.value.id
        return None

    def test_circuit_outage_viewset_exists(self):
        """Test that CircuitOutageViewSet class exists"""
        tree = self._get_views_file_ast()
        viewset_class = self._find_class(tree, "CircuitOutageViewSet")
        self.assertIsNotNone(viewset_class, "CircuitOutageViewSet class should exist")

    def test_circuit_outage_viewset_inherits_from_netbox_model_viewset(self):
        """Test that CircuitOutageViewSet inherits from NetBoxModelViewSet"""
        tree = self._get_views_file_ast()
        viewset_class = self._find_class(tree, "CircuitOutageViewSet")
        self.assertIsNotNone(viewset_class)

        # Check base classes
        base_names = [base.id for base in viewset_class.bases if hasattr(base, "id")]
        self.assertIn(
            "NetBoxModelViewSet",
            base_names,
            "CircuitOutageViewSet should inherit from NetBoxModelViewSet",
        )

    def test_circuit_outage_viewset_has_queryset(self):
        """Test that CircuitOutageViewSet has queryset attribute"""
        tree = self._get_views_file_ast()
        viewset_class = self._find_class(tree, "CircuitOutageViewSet")
        self.assertIsNotNone(viewset_class)

        # Look for queryset attribute
        queryset_attr = self._find_class_attr(viewset_class, "queryset")
        self.assertIsNotNone(
            queryset_attr, "CircuitOutageViewSet should have a queryset attribute"
        )

    def test_circuit_outage_viewset_has_serializer_class(self):
        """Test that CircuitOutageViewSet has serializer_class attribute"""
        tree = self._get_views_file_ast()
        viewset_class = self._find_class(tree, "CircuitOutageViewSet")
        self.assertIsNotNone(viewset_class)

        # Look for serializer_class attribute
        serializer_attr = self._find_class_attr(viewset_class, "serializer_class")
        self.assertIsNotNone(
            serializer_attr,
            "CircuitOutageViewSet should have a serializer_class attribute",
        )

        # Check that it's set to CircuitOutageSerializer
        serializer_name = self._get_attr_value_name(serializer_attr)
        self.assertEqual(
            serializer_name,
            "CircuitOutageSerializer",
            "serializer_class should be CircuitOutageSerializer",
        )


class TestCircuitOutageURLRouting(unittest.TestCase):
    """Test that CircuitOutage URL routing is configured"""

    def _get_urls_file_content(self):
        """Read the urls.py file"""
        urls_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "vendor_notification",
            "api",
            "urls.py",
        )
        with open(urls_path, "r") as f:
            return f.read()

    def test_circuit_outage_router_registration_exists(self):
        """Test that circuitoutage router registration exists"""
        content = self._get_urls_file_content()
        self.assertIn(
            "circuitoutage",
            content,
            "urls.py should contain 'circuitoutage' router registration",
        )

    def test_circuit_outage_viewset_registered(self):
        """Test that CircuitOutageViewSet is registered in router"""
        content = self._get_urls_file_content()
        # Check for the router.register call
        self.assertIn(
            "CircuitOutageViewSet",
            content,
            "urls.py should register CircuitOutageViewSet",
        )


if __name__ == "__main__":
    unittest.main()
