"""
Tests for URL patterns after model renaming.
These tests validate the code structure by reading the source file directly.
This approach works without requiring NetBox installation.
"""

import os
import re
import unittest


class TestURLPatterns(unittest.TestCase):
    """Test the URL patterns for all models"""

    def _get_urls_file_content(self):
        """Read the urls.py file and return content"""
        urls_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "vendor_notification",
            "urls.py",
        )
        with open(urls_path, "r") as f:
            return f.read()

    def test_maintenance_urls_defined(self):
        """Test that maintenance URL patterns exist with correct naming"""
        content = self._get_urls_file_content()

        # Check for maintenance-related URL patterns
        maintenance_url_patterns = [
            r"path\(\s*['\"]maintenance/['\"]",  # List view
            r"path\(\s*['\"]maintenance/add/['\"]",  # Add view
            r"path\(\s*['\"]maintenance/<int:pk>/['\"]",  # Detail view
            r"path\(\s*['\"]maintenance/<int:pk>/edit/['\"]",  # Edit view
            r"path\(\s*['\"]maintenance/<int:pk>/delete/['\"]",  # Delete view
            r"path\(\s*['\"]maintenance/<int:pk>/changelog/['\"]",  # Changelog view
        ]

        for pattern in maintenance_url_patterns:
            self.assertIsNotNone(
                re.search(pattern, content, re.DOTALL),
                f"Maintenance URL pattern not found: {pattern}",
            )

    def test_maintenance_url_names(self):
        """Test that maintenance URL names are correct"""
        content = self._get_urls_file_content()

        # Check for correct URL names
        url_names = [
            r'name=["\']maintenance_list["\']',
            r'name=["\']maintenance_add["\']',
            r'name=["\']maintenance["\']',
            r'name=["\']maintenance_edit["\']',
            r'name=["\']maintenance_delete["\']',
            r'name=["\']maintenance_changelog["\']',
        ]

        for name_pattern in url_names:
            self.assertIsNotNone(
                re.search(name_pattern, content),
                f"Maintenance URL name not found: {name_pattern}",
            )

    def test_outage_urls_defined(self):
        """Test that outage URL patterns exist with correct naming"""
        content = self._get_urls_file_content()

        # Check for outage-related URL patterns
        outage_url_patterns = [
            r"path\(['\"]outages/['\"]",  # List view
            r"path\(\s*['\"]outages/add/['\"]",  # Add view
            r"path\(['\"]outages/<int:pk>/['\"]",  # Detail view
            r"path\(\s*['\"]outages/<int:pk>/edit/['\"]",  # Edit view
            r"path\(\s*['\"]outages/<int:pk>/delete/['\"]",  # Delete view
            r"path\(\s*['\"]outages/<int:pk>/changelog/['\"]",  # Changelog view
        ]

        for pattern in outage_url_patterns:
            self.assertIsNotNone(
                re.search(pattern, content, re.DOTALL),
                f"Outage URL pattern not found: {pattern}",
            )

    def test_outage_url_names(self):
        """Test that outage URL names are correct"""
        content = self._get_urls_file_content()

        # Check for correct URL names
        url_names = [
            r'name=["\']outage_list["\']',
            r'name=["\']outage_add["\']',
            r'name=["\']outage["\']',
            r'name=["\']outage_edit["\']',
            r'name=["\']outage_delete["\']',
            r'name=["\']outage_changelog["\']',
        ]

        for name_pattern in url_names:
            self.assertIsNotNone(
                re.search(name_pattern, content),
                f"Outage URL name not found: {name_pattern}",
            )

    def test_impact_urls_defined(self):
        """Test that impact URL patterns exist with correct naming"""
        content = self._get_urls_file_content()

        # Check for impact-related URL patterns
        impact_url_patterns = [
            r"path\(\s*['\"]impact/add/['\"]",  # Add view
            r"path\(\s*['\"]impact/<int:pk>/edit/['\"]",  # Edit view
            r"path\(\s*['\"]impact/<int:pk>/delete/['\"]",  # Delete view
            r"path\(\s*['\"]impact/<int:pk>/changelog/['\"]",  # Changelog view
        ]

        for pattern in impact_url_patterns:
            self.assertIsNotNone(
                re.search(pattern, content, re.DOTALL),
                f"Impact URL pattern not found: {pattern}",
            )

    def test_impact_url_names(self):
        """Test that impact URL names are correct"""
        content = self._get_urls_file_content()

        # Check for correct URL names
        url_names = [
            r'name=["\']impact_add["\']',
            r'name=["\']impact_edit["\']',
            r'name=["\']impact_delete["\']',
            r'name=["\']impact_changelog["\']',
        ]

        for name_pattern in url_names:
            self.assertIsNotNone(
                re.search(name_pattern, content),
                f"Impact URL name not found: {name_pattern}",
            )

    def test_eventnotification_urls_defined(self):
        """Test that event notification URL patterns exist with correct naming"""
        content = self._get_urls_file_content()

        # Check for notification-related URL patterns
        notification_url_patterns = [
            r"path\(\s*['\"]notification/add/['\"]",  # Add view
            r"path\(\s*['\"]notification/<int:pk>/['\"]",  # Detail view
            r"path\(\s*['\"]notification/<int:pk>/delete/['\"]",  # Delete view
        ]

        for pattern in notification_url_patterns:
            self.assertIsNotNone(
                re.search(pattern, content, re.DOTALL),
                f"EventNotification URL pattern not found: {pattern}",
            )

    def test_eventnotification_url_names(self):
        """Test that event notification URL names are correct"""
        content = self._get_urls_file_content()

        # Check for correct URL names
        url_names = [
            r'name=["\']eventnotification_add["\']',
            r'name=["\']eventnotification["\']',
            r'name=["\']eventnotification_delete["\']',
        ]

        for name_pattern in url_names:
            self.assertIsNotNone(
                re.search(name_pattern, content),
                f"EventNotification URL name not found: {name_pattern}",
            )

    def test_maintenance_view_references(self):
        """Test that maintenance views are referenced correctly"""
        content = self._get_urls_file_content()

        # Check for references to new view names
        view_references = [
            "MaintenanceListView",
            "MaintenanceView",
            "MaintenanceEditView",
            "MaintenanceDeleteView",
        ]

        for view_ref in view_references:
            self.assertIn(
                view_ref, content, f"Maintenance view reference not found: {view_ref}"
            )

    def test_outage_view_references(self):
        """Test that outage views are referenced correctly"""
        content = self._get_urls_file_content()

        # Check for references to new view names
        view_references = [
            "OutageListView",
            "OutageView",
            "OutageEditView",
            "OutageDeleteView",
        ]

        for view_ref in view_references:
            self.assertIn(
                view_ref, content, f"Outage view reference not found: {view_ref}"
            )

    def test_impact_view_references(self):
        """Test that impact views are referenced correctly"""
        content = self._get_urls_file_content()

        # Check for references to new view names
        view_references = [
            "ImpactEditView",
            "ImpactDeleteView",
        ]

        for view_ref in view_references:
            self.assertIn(
                view_ref, content, f"Impact view reference not found: {view_ref}"
            )

    def test_eventnotification_view_references(self):
        """Test that event notification views are referenced correctly"""
        content = self._get_urls_file_content()

        # Check for references to new view names
        view_references = [
            "EventNotificationEditView",
            "EventNotificationView",
            "EventNotificationDeleteView",
        ]

        for view_ref in view_references:
            self.assertIn(
                view_ref,
                content,
                f"EventNotification view reference not found: {view_ref}",
            )

    def test_model_references(self):
        """Test that model references in kwargs are correct"""
        content = self._get_urls_file_content()

        # Check for correct model references in changelog URLs
        model_references = [
            r'kwargs=\{["\']model["\']: models\.Maintenance\}',
            r'kwargs=\{["\']model["\']: models\.Outage\}',
            r'kwargs=\{["\']model["\']: models\.Impact\}',
        ]

        for model_ref in model_references:
            self.assertIsNotNone(
                re.search(model_ref, content),
                f"Model reference not found: {model_ref}",
            )

    def test_no_old_model_names(self):
        """Test that old model names are not present"""
        content = self._get_urls_file_content()

        # These old names should NOT appear in the file
        old_names = [
            "CircuitMaintenance",
            "CircuitOutage",
            "CircuitMaintenanceImpact",
            "CircuitMaintenanceNotifications",
            "circuitmaintenance",
            "circuitoutage",
            "circuitimpact",
            "circuitnotification",
        ]

        for old_name in old_names:
            # Allow 'circuitoutage' only in comments or if it's part of 'outage'
            if old_name == "circuitoutage":
                # Check that it's not used as a standalone URL pattern or view name
                pattern = rf"\b{old_name}\b"
                matches = re.findall(pattern, content)
                # Filter out matches in comments
                non_comment_matches = [
                    m for m in matches if not re.search(r"#.*" + old_name, content)
                ]
                self.assertEqual(
                    len(non_comment_matches),
                    0,
                    f"Old model name '{old_name}' found in non-comment context",
                )
            elif old_name in [
                "circuitmaintenance",
                "circuitimpact",
                "circuitnotification",
            ]:
                # These should definitely not appear
                self.assertNotIn(
                    old_name,
                    content,
                    f"Old model name '{old_name}' still present in URLs",
                )

    def test_imports(self):
        """Test that imports are correct"""
        content = self._get_urls_file_content()

        # Check for required imports
        self.assertIn("from django.urls import path", content)
        self.assertIn("from netbox.views.generic import ObjectChangeLogView", content)
        self.assertIn("from . import models, views", content)

    def test_maintenance_schedule_url(self):
        """Test that maintenance schedule URL exists"""
        content = self._get_urls_file_content()

        # Check for maintenance schedule URL
        self.assertIsNotNone(
            re.search(r"path\(\s*['\"]maintenanceschedule/['\"]", content),
            "Maintenance schedule URL pattern not found",
        )
        self.assertIsNotNone(
            re.search(r'name=["\']maintenanceschedule["\']', content),
            "Maintenance schedule URL name not found",
        )


if __name__ == "__main__":
    unittest.main()
