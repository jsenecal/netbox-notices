"""
Tests for Outage forms.
"""

from vendor_notification.forms import OutageFilterForm, OutageForm


def test_outage_form_exists():
    """Test that OutageForm is defined"""
    assert OutageForm is not None


def test_outage_form_model():
    """Test that form targets Outage model"""
    from vendor_notification.models import Outage

    assert OutageForm.Meta.model == Outage


def test_outage_form_fields():
    """Test that form includes all required fields"""
    expected_fields = (
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
        "comments",
        "tags",
    )

    assert OutageForm.Meta.fields == expected_fields


def test_outage_filter_form_exists():
    """Test that OutageFilterForm is defined"""
    assert OutageFilterForm is not None
