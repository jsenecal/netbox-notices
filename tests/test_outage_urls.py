"""
Tests for CircuitOutage URL patterns.
These tests validate the code structure by reading the source file directly.
This approach works without requiring NetBox installation.
"""

import ast
import os
import re
import unittest


class TestCircuitOutageURLs(unittest.TestCase):
    """Test the CircuitOutage URL patterns"""

    def _get_urls_file_content(self):
        """Read the urls.py file and return content"""
        urls_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "netbox_circuitmaintenance",
            "urls.py",
        )
        with open(urls_path, "r") as f:
            return f.read()

    def test_outage_urls_defined(self):
        """Test that outage URL patterns exist"""
        content = self._get_urls_file_content()

        # Check for outage-related URL patterns
        # Look for path() calls with 'outage' in them
        # Use DOTALL flag to handle multi-line formatting from black
        outage_url_patterns = [
            r"path\(['\"]outages/['\"]",  # List view
            r"path\(\s*['\"]outages/add/['\"]",  # Add view (allow whitespace)
            r"path\(['\"]outages/<int:pk>/['\"]",  # Detail view
            r"path\(\s*['\"]outages/<int:pk>/edit/['\"]",  # Edit view (allow whitespace)
            r"path\(\s*['\"]outages/<int:pk>/delete/['\"]",  # Delete view (allow whitespace)
        ]

        for pattern in outage_url_patterns:
            self.assertIsNotNone(
                re.search(pattern, content, re.DOTALL),
                f"URL pattern not found: {pattern}",
            )

    def test_outage_view_imports(self):
        """Test that outage views are imported"""
        content = self._get_urls_file_content()

        # Check for imports of outage views
        view_imports = [
            "CircuitOutageListView",
            "CircuitOutageView",
            "CircuitOutageEditView",
            "CircuitOutageDeleteView",
        ]

        for view_import in view_imports:
            self.assertIn(view_import, content, f"View import not found: {view_import}")
