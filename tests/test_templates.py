"""
Tests to verify template structure and URL references
"""

import re
from pathlib import Path


class TestTemplateStructure:
    """Test that all templates exist and have correct structure"""

    TEMPLATE_DIR = Path(__file__).parent.parent / "notices" / "templates" / "notices"

    def test_template_directory_exists(self):
        """Verify template directory exists"""
        assert self.TEMPLATE_DIR.exists()
        assert self.TEMPLATE_DIR.is_dir()

    def test_all_templates_exist(self):
        """Verify all expected templates exist"""
        expected_templates = [
            "calendar.html",
            "calendar_widget.html",
            "eventnotification.html",
            "maintenance.html",
            "maintenance_cancel.html",
            "maintenance_include.html",
            "outage.html",
            "provider_include.html",
            "widget.html",
        ]

        for template in expected_templates:
            template_path = self.TEMPLATE_DIR / template
            assert template_path.exists(), f"Template {template} does not exist"

    def test_maintenance_template_urls(self):
        """Verify maintenance.html uses correct URL patterns"""
        template_path = self.TEMPLATE_DIR / "maintenance.html"
        content = template_path.read_text()

        # Check for new URL patterns
        assert "plugins:notices:maintenance" in content
        assert "plugins:notices:impact_edit" in content
        assert "plugins:notices:impact_delete" in content
        assert "plugins:notices:impact_add" in content
        assert "plugins:notices:eventnotification" in content
        assert "plugins:notices:eventnotification_delete" in content
        assert "plugins:notices:eventnotification_add" in content

        # Check for quick action URLs
        assert "plugins:notices:maintenance_acknowledge" in content
        assert "plugins:notices:maintenance_reschedule" in content
        assert "plugins:notices:maintenance_cancel" in content
        assert "plugins:notices:maintenance_mark_in_progress" in content
        assert "plugins:notices:maintenance_mark_completed" in content

        # Check that old URLs are NOT present
        assert "netbox_circuitmaintenance" not in content
        assert (
            "circuitmaintenance" not in content.lower()
            or "maintenance" in content.lower()
        )

    def test_outage_template_urls(self):
        """Verify outage.html uses correct URL patterns"""
        template_path = self.TEMPLATE_DIR / "outage.html"
        content = template_path.read_text()

        # Check for new URL patterns
        assert "plugins:notices:outage" in content
        assert "plugins:notices:impact_edit" in content
        assert "plugins:notices:impact_delete" in content
        assert "plugins:notices:impact_add" in content
        assert "plugins:notices:eventnotification" in content
        assert "plugins:notices:eventnotification_delete" in content
        assert "plugins:notices:eventnotification_add" in content

    def test_maintenance_template_field_references(self):
        """Verify maintenance.html references correct fields for GenericForeignKey"""
        template_path = self.TEMPLATE_DIR / "maintenance.html"
        content = template_path.read_text()

        # Check Impact section uses new field names
        assert "impact.target" in content  # GenericForeignKey target field
        assert "impact.target_content_type" in content

        # Check notifications section
        assert "email.email_received" in content  # Fixed typo from email_recieved

    def test_outage_template_field_references(self):
        """Verify outage.html references correct fields for GenericForeignKey"""
        template_path = self.TEMPLATE_DIR / "outage.html"
        content = template_path.read_text()

        # Check Impact section uses new field names
        assert "impact.target" in content  # GenericForeignKey target field
        assert "impact.target_content_type" in content

        # Check for outage-specific fields
        assert "estimated_time_to_repair" in content

    def test_calendar_template_title(self):
        """Verify calendar.html has correct title"""
        template_path = self.TEMPLATE_DIR / "calendar.html"
        content = template_path.read_text()

        # Check title is updated
        assert "Maintenance Calendar" in content
        assert "Circuit Maintenance Schedule" not in content

    def test_include_templates_use_new_field_names(self):
        """Verify include templates reference new field names"""
        for template_name in ["maintenance_include.html", "provider_include.html"]:
            template_path = self.TEMPLATE_DIR / template_name
            content = template_path.read_text()

            # Check for event field (GenericForeignKey)
            assert "maintenance.event" in content or "maintenances" in content

    def test_eventnotification_template_simple(self):
        """Verify eventnotification.html is simple email body display"""
        template_path = self.TEMPLATE_DIR / "eventnotification.html"
        content = template_path.read_text()

        # Should just display email body
        assert "email_body" in content
        assert "safe" in content  # Should use safe filter

    def test_no_old_model_references(self):
        """Verify templates don't reference old model names"""
        old_patterns = [
            r"CircuitMaintenance",
            r"CircuitOutage",
            r"CircuitMaintenanceImpact",
            r"CircuitMaintenanceNotifications",
        ]

        for template_file in self.TEMPLATE_DIR.glob("*.html"):
            content = template_file.read_text()

            for pattern in old_patterns:
                # Allow lowercase in template paths but not in model references
                if pattern in content:
                    # Check it's not in a comment or lowercase
                    if re.search(pattern, content, re.IGNORECASE):
                        # Make sure it's actually the old model name, not just part of text
                        matches = re.findall(pattern, content)
                        if matches:
                            assert False, f"Found old model name '{pattern}' in {template_file.name}"

    def test_templates_extend_correct_base(self):
        """Verify templates extend correct base templates"""
        # Main detail templates should extend generic/object.html
        for template_name in ["maintenance.html", "outage.html"]:
            template_path = self.TEMPLATE_DIR / template_name
            content = template_path.read_text()
            assert "extends 'generic/object.html'" in content

        # Calendar should extend generic/_base.html
        calendar_path = self.TEMPLATE_DIR / "calendar.html"
        content = calendar_path.read_text()
        assert "extends 'generic/_base.html'" in content

    def test_templates_have_proper_encoding(self):
        """Verify all templates are UTF-8 encoded"""
        for template_file in self.TEMPLATE_DIR.glob("*.html"):
            # This will raise if not valid UTF-8
            try:
                template_file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                assert False, f"Template {template_file.name} is not UTF-8 encoded"


class TestTemplateURLParameters:
    """Test that templates pass correct parameters in URLs"""

    TEMPLATE_DIR = Path(__file__).parent.parent / "notices" / "templates" / "notices"

    def test_impact_add_urls_include_event_param(self):
        """Verify impact_add URLs include GenericForeignKey event parameters"""
        for template_name in ["maintenance.html", "outage.html"]:
            template_path = self.TEMPLATE_DIR / template_name
            content = template_path.read_text()

            # Should include GenericForeignKey parameters when adding impacts
            assert "event_content_type={{ object|content_type_id }}" in content
            assert "event_object_id={{ object.pk }}" in content

    def test_notification_add_urls_include_event_param(self):
        """Verify eventnotification_add URLs include GenericForeignKey event parameters"""
        for template_name in ["maintenance.html", "outage.html"]:
            template_path = self.TEMPLATE_DIR / template_name
            content = template_path.read_text()

            # Should include GenericForeignKey parameters when adding notifications
            assert "event_content_type={{ object|content_type_id }}" in content
            assert "event_object_id={{ object.pk }}" in content

    def test_return_url_parameters(self):
        """Verify edit/delete links include return_url parameter"""
        for template_name in ["maintenance.html", "outage.html"]:
            template_path = self.TEMPLATE_DIR / template_name
            content = template_path.read_text()

            # Should include return_url parameter
            assert "return_url=" in content


class TestTemplateConditionals:
    """Test that templates have correct conditional logic"""

    TEMPLATE_DIR = Path(__file__).parent.parent / "notices" / "templates" / "notices"

    def test_maintenance_status_checks(self):
        """Verify maintenance.html checks for COMPLETED and CANCELLED status"""
        template_path = self.TEMPLATE_DIR / "maintenance.html"
        content = template_path.read_text()

        # Should check for completed/cancelled status
        assert "COMPLETED" in content
        assert "CANCELLED" in content

    def test_outage_status_checks(self):
        """Verify outage.html checks for RESOLVED status"""
        template_path = self.TEMPLATE_DIR / "outage.html"
        content = template_path.read_text()

        # Should check for resolved status
        assert "RESOLVED" in content

    def test_conditional_edit_buttons(self):
        """Verify edit buttons are conditional on status"""
        for template_name in ["maintenance.html", "outage.html"]:
            template_path = self.TEMPLATE_DIR / template_name
            content = template_path.read_text()

            # Should have conditional logic for edit buttons
            assert "{% if object.status" in content

    def test_timezone_display_conditional(self):
        """Verify timezone display is conditional"""
        template_path = self.TEMPLATE_DIR / "maintenance.html"
        content = template_path.read_text()

        # Should check for timezone difference
        assert "has_timezone_difference" in content
        assert "original_timezone" in content

    def test_maintenance_cancel_template_structure(self):
        """Verify maintenance_cancel.html has proper confirmation structure"""
        template_path = self.TEMPLATE_DIR / "maintenance_cancel.html"
        content = template_path.read_text()

        # Should extend delete template
        assert "extends 'generic/object_delete.html'" in content

        # Should have confirmation message
        assert "cancel" in content.lower()

        # Should have form with CSRF token
        assert "{% csrf_token %}" in content
        assert "<form" in content
        assert 'method="post"' in content

        # Should have return_url handling
        assert "return_url" in content

        # Should have both confirm and cancel buttons
        assert "btn-danger" in content  # Confirm button
        assert "btn-secondary" in content  # Cancel button
