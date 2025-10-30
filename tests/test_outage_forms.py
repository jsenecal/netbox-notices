"""
Tests for CircuitOutage forms.
"""

from netbox_circuitmaintenance.forms import CircuitOutageFilterForm, CircuitOutageForm


def test_circuit_outage_form_exists():
    """Test that CircuitOutageForm is defined"""
    assert CircuitOutageForm is not None


def test_circuit_outage_form_model():
    """Test that form targets CircuitOutage model"""
    from netbox_circuitmaintenance.models import CircuitOutage

    assert CircuitOutageForm.Meta.model == CircuitOutage


def test_circuit_outage_form_fields():
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

    assert CircuitOutageForm.Meta.fields == expected_fields


def test_circuit_outage_filter_form_exists():
    """Test that CircuitOutageFilterForm is defined"""
    assert CircuitOutageFilterForm is not None
