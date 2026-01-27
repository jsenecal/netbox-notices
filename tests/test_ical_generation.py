# tests/test_ical_generation.py
"""Tests for iCal Generation Service."""

from unittest.mock import Mock

import pytest

from notices.services.ical_generation import (
    DEFAULT_BCOP_ICAL_TEMPLATE,
    ICalGenerationService,
    generate_ical,
)
from notices.services.template_renderer import TemplateRenderError

# Simple template for testing (avoids complexity of full BCOP template)
SIMPLE_TEST_TEMPLATE = "UID:{{ maintenance.pk }}@netbox"


class MockTemplate:
    """Mock MessageTemplate for testing."""

    def __init__(
        self,
        name="Test Template",
        include_ical=True,
        ical_template=None,
    ):
        self.name = name
        self.include_ical = include_ical
        # Use simple template by default for tests, unless explicitly set
        if ical_template is None:
            self.ical_template = SIMPLE_TEST_TEMPLATE
        else:
            self.ical_template = ical_template


class MockMaintenance:
    """Mock Maintenance event for testing."""

    def __init__(
        self,
        pk=1,
        name="MAINT-001",
        summary="Test maintenance",
        status="CONFIRMED",
        internal_ticket="TKT-123",
    ):
        from datetime import datetime
        from datetime import timezone as dt_tz

        self.pk = pk
        self.name = name
        self.summary = summary
        self.status = status
        self.internal_ticket = internal_ticket
        self.start = datetime(2026, 1, 22, 10, 0, 0, tzinfo=dt_tz.utc)
        self.end = datetime(2026, 1, 22, 14, 0, 0, tzinfo=dt_tz.utc)
        self.provider = Mock()
        self.provider.name = "Test Provider"
        self.provider.slug = "test-provider"


class MockOutage:
    """Mock Outage event for testing."""

    def __init__(self, pk=1, name="OUT-001"):
        from datetime import datetime
        from datetime import timezone as dt_tz

        self.pk = pk
        self.name = name
        self.status = "REPORTED"
        self.start = datetime(2026, 1, 22, 10, 0, 0, tzinfo=dt_tz.utc)
        self.provider = Mock()
        self.provider.name = "Test Provider"


class MockTenant:
    """Mock Tenant for testing."""

    def __init__(self, pk=1, name="Test Tenant"):
        self.pk = pk
        self.name = name


class MockImpact:
    """Mock Impact for testing."""

    def __init__(self, impact="OUTAGE", target=None, tenant=None):
        self.impact = impact
        self.target = target or Mock()
        self.target.cid = "CID-001"
        if tenant:
            self.target.tenant = tenant


class TestICalGenerationServiceShouldGenerate:
    """Tests for should_generate() method."""

    def test_returns_true_for_valid_maintenance_and_template(self):
        """should_generate() returns True for valid Maintenance + template."""
        template = MockTemplate(include_ical=True)
        maintenance = MockMaintenance()

        service = ICalGenerationService(template, maintenance)

        assert service.should_generate() is True

    def test_returns_false_for_outage_events(self):
        """should_generate() returns False for Outage events."""
        template = MockTemplate(include_ical=True)
        outage = MockOutage()

        service = ICalGenerationService(template, outage)

        assert service.should_generate() is False

    def test_returns_false_when_include_ical_is_false(self):
        """should_generate() returns False when include_ical=False."""
        template = MockTemplate(include_ical=False)
        maintenance = MockMaintenance()

        service = ICalGenerationService(template, maintenance)

        assert service.should_generate() is False

    def test_returns_false_when_ical_template_is_empty(self):
        """should_generate() returns False when ical_template is empty."""
        template = MockTemplate(include_ical=True, ical_template="")
        maintenance = MockMaintenance()

        service = ICalGenerationService(template, maintenance)

        assert service.should_generate() is False

    def test_returns_false_when_ical_template_is_none(self):
        """should_generate() returns False when ical_template is None."""
        template = MockTemplate(include_ical=True)
        template.ical_template = None
        maintenance = MockMaintenance()

        service = ICalGenerationService(template, maintenance)

        assert service.should_generate() is False

    def test_returns_false_when_event_is_none(self):
        """should_generate() returns False when event is None."""
        template = MockTemplate(include_ical=True)

        service = ICalGenerationService(template, None)

        assert service.should_generate() is False

    def test_handles_missing_include_ical_attribute(self):
        """should_generate() handles template without include_ical attribute."""
        template = Mock()
        del template.include_ical
        maintenance = MockMaintenance()

        service = ICalGenerationService(template, maintenance)

        assert service.should_generate() is False


class TestICalGenerationServiceGenerate:
    """Tests for generate() method."""

    def test_renders_template_with_correct_context(self):
        """generate() renders template with correct context."""
        simple_template = "UID:{{ maintenance.pk }}@netbox"
        template = MockTemplate(include_ical=True, ical_template=simple_template)
        maintenance = MockMaintenance(pk=42)

        service = ICalGenerationService(template, maintenance)
        result = service.generate()

        assert result == "UID:42@netbox"

    def test_includes_message_sequence_in_context(self):
        """generate() includes message_sequence in context."""
        simple_template = "SEQUENCE:{{ message_sequence }}"
        template = MockTemplate(include_ical=True, ical_template=simple_template)
        maintenance = MockMaintenance()

        service = ICalGenerationService(template, maintenance)
        result = service.generate(message_sequence=5)

        assert result == "SEQUENCE:5"

    def test_includes_tenant_in_context(self):
        """generate() includes tenant in context when provided."""
        simple_template = "ACCOUNT:{{ tenant.name }}"
        template = MockTemplate(include_ical=True, ical_template=simple_template)
        maintenance = MockMaintenance()
        tenant = MockTenant(name="Acme Corp")

        service = ICalGenerationService(template, maintenance, tenant=tenant)
        result = service.generate()

        assert result == "ACCOUNT:Acme Corp"

    def test_includes_impacts_in_context(self):
        """generate() includes impacts in context when provided."""
        simple_template = "{% for impact in impacts %}{{ impact.impact }}{% endfor %}"
        template = MockTemplate(include_ical=True, ical_template=simple_template)
        maintenance = MockMaintenance()
        impacts = [MockImpact(impact="OUTAGE"), MockImpact(impact="DEGRADED")]

        service = ICalGenerationService(template, maintenance, impacts=impacts)
        result = service.generate()

        assert "OUTAGE" in result
        assert "DEGRADED" in result

    def test_calculates_highest_impact(self):
        """generate() calculates and includes highest_impact in context."""
        simple_template = "IMPACT:{{ highest_impact }}"
        template = MockTemplate(include_ical=True, ical_template=simple_template)
        maintenance = MockMaintenance()
        impacts = [
            MockImpact(impact="NO-IMPACT"),
            MockImpact(impact="DEGRADED"),
            MockImpact(impact="REDUCED-REDUNDANCY"),
        ]

        service = ICalGenerationService(template, maintenance, impacts=impacts)
        result = service.generate()

        assert result == "IMPACT:DEGRADED"

    def test_raises_value_error_when_not_applicable(self):
        """generate() raises ValueError when should_generate() is False."""
        template = MockTemplate(include_ical=False)
        maintenance = MockMaintenance()

        service = ICalGenerationService(template, maintenance)

        with pytest.raises(ValueError, match="iCal generation not applicable"):
            service.generate()

    def test_raises_template_render_error_on_invalid_syntax(self):
        """generate() raises TemplateRenderError on invalid template syntax."""
        invalid_template = "{{ invalid syntax }}"
        template = MockTemplate(include_ical=True, ical_template=invalid_template)
        maintenance = MockMaintenance()

        service = ICalGenerationService(template, maintenance)

        with pytest.raises(TemplateRenderError):
            service.generate()

    def test_default_message_sequence_is_one(self):
        """generate() uses message_sequence=1 by default."""
        simple_template = "SEQUENCE:{{ message_sequence }}"
        template = MockTemplate(include_ical=True, ical_template=simple_template)
        maintenance = MockMaintenance()

        service = ICalGenerationService(template, maintenance)
        result = service.generate()

        assert result == "SEQUENCE:1"


class TestICalGenerationServiceValidateTemplate:
    """Tests for validate_template() method."""

    def test_validates_valid_template_syntax(self):
        """validate_template() returns True for valid template."""
        template = MockTemplate(include_ical=True, ical_template="{{ maintenance.name }}")
        maintenance = MockMaintenance()

        service = ICalGenerationService(template, maintenance)

        assert service.validate_template() is True

    def test_raises_on_invalid_template_syntax(self):
        """validate_template() raises TemplateRenderError for invalid syntax."""
        template = MockTemplate(include_ical=True, ical_template="{% if unclosed")
        maintenance = MockMaintenance()

        service = ICalGenerationService(template, maintenance)

        with pytest.raises(TemplateRenderError, match="Invalid template syntax"):
            service.validate_template()

    def test_returns_true_when_no_ical_template(self):
        """validate_template() returns True when ical_template is empty."""
        template = MockTemplate(include_ical=True, ical_template="")
        maintenance = MockMaintenance()

        service = ICalGenerationService(template, maintenance)

        assert service.validate_template() is True


class TestICalGenerationServiceCalculateHighestImpact:
    """Tests for _calculate_highest_impact() method."""

    def test_returns_no_impact_when_no_impacts(self):
        """_calculate_highest_impact() returns NO-IMPACT when no impacts."""
        template = MockTemplate()
        maintenance = MockMaintenance()

        service = ICalGenerationService(template, maintenance, impacts=[])

        assert service._calculate_highest_impact() == "NO-IMPACT"

    def test_returns_outage_as_highest(self):
        """_calculate_highest_impact() returns OUTAGE as highest severity."""
        template = MockTemplate()
        maintenance = MockMaintenance()
        impacts = [
            MockImpact(impact="NO-IMPACT"),
            MockImpact(impact="OUTAGE"),
            MockImpact(impact="DEGRADED"),
        ]

        service = ICalGenerationService(template, maintenance, impacts=impacts)

        assert service._calculate_highest_impact() == "OUTAGE"

    def test_returns_degraded_when_no_outage(self):
        """_calculate_highest_impact() returns DEGRADED when no OUTAGE."""
        template = MockTemplate()
        maintenance = MockMaintenance()
        impacts = [
            MockImpact(impact="NO-IMPACT"),
            MockImpact(impact="DEGRADED"),
            MockImpact(impact="REDUCED-REDUNDANCY"),
        ]

        service = ICalGenerationService(template, maintenance, impacts=impacts)

        assert service._calculate_highest_impact() == "DEGRADED"

    def test_handles_none_impact_values(self):
        """_calculate_highest_impact() handles None impact values."""
        template = MockTemplate()
        maintenance = MockMaintenance()
        impact = MockImpact()
        impact.impact = None

        service = ICalGenerationService(template, maintenance, impacts=[impact])

        assert service._calculate_highest_impact() == "NO-IMPACT"


class TestGenerateIcalConvenienceFunction:
    """Tests for generate_ical() convenience function."""

    def test_returns_none_when_not_applicable(self):
        """generate_ical() returns None when iCal generation not applicable."""
        template = MockTemplate(include_ical=False)
        maintenance = MockMaintenance()

        result = generate_ical(template, maintenance)

        assert result is None

    def test_returns_none_for_outage_events(self):
        """generate_ical() returns None for Outage events."""
        template = MockTemplate(include_ical=True)
        outage = MockOutage()

        result = generate_ical(template, outage)

        assert result is None

    def test_returns_ical_content_for_valid_maintenance(self):
        """generate_ical() returns iCal content for valid Maintenance."""
        simple_template = "UID:{{ maintenance.pk }}@netbox"
        template = MockTemplate(include_ical=True, ical_template=simple_template)
        maintenance = MockMaintenance(pk=99)

        result = generate_ical(template, maintenance)

        assert result == "UID:99@netbox"

    def test_passes_tenant_to_service(self):
        """generate_ical() passes tenant to service."""
        simple_template = "TENANT:{{ tenant.name }}"
        template = MockTemplate(include_ical=True, ical_template=simple_template)
        maintenance = MockMaintenance()
        tenant = MockTenant(name="Test Tenant")

        result = generate_ical(template, maintenance, tenant=tenant)

        assert result == "TENANT:Test Tenant"

    def test_passes_impacts_to_service(self):
        """generate_ical() passes impacts to service."""
        simple_template = "IMPACT:{{ highest_impact }}"
        template = MockTemplate(include_ical=True, ical_template=simple_template)
        maintenance = MockMaintenance()
        impacts = [MockImpact(impact="OUTAGE")]

        result = generate_ical(template, maintenance, impacts=impacts)

        assert result == "IMPACT:OUTAGE"

    def test_passes_message_sequence_to_service(self):
        """generate_ical() passes message_sequence to service."""
        simple_template = "SEQUENCE:{{ message_sequence }}"
        template = MockTemplate(include_ical=True, ical_template=simple_template)
        maintenance = MockMaintenance()

        result = generate_ical(template, maintenance, message_sequence=7)

        assert result == "SEQUENCE:7"


class TestDefaultBcopIcalTemplate:
    """Tests for DEFAULT_BCOP_ICAL_TEMPLATE constant."""

    def test_template_contains_vcalendar(self):
        """Default template contains VCALENDAR structure."""
        assert "BEGIN:VCALENDAR" in DEFAULT_BCOP_ICAL_TEMPLATE
        assert "END:VCALENDAR" in DEFAULT_BCOP_ICAL_TEMPLATE

    def test_template_contains_vevent(self):
        """Default template contains VEVENT structure."""
        assert "BEGIN:VEVENT" in DEFAULT_BCOP_ICAL_TEMPLATE
        assert "END:VEVENT" in DEFAULT_BCOP_ICAL_TEMPLATE

    def test_template_contains_maintnote_properties(self):
        """Default template contains X-MAINTNOTE properties."""
        assert "X-MAINTNOTE-PROVIDER" in DEFAULT_BCOP_ICAL_TEMPLATE
        assert "X-MAINTNOTE-ACCOUNT" in DEFAULT_BCOP_ICAL_TEMPLATE
        assert "X-MAINTNOTE-MAINTENANCE-ID" in DEFAULT_BCOP_ICAL_TEMPLATE
        assert "X-MAINTNOTE-OBJECT-ID" in DEFAULT_BCOP_ICAL_TEMPLATE
        assert "X-MAINTNOTE-IMPACT" in DEFAULT_BCOP_ICAL_TEMPLATE
        assert "X-MAINTNOTE-STATUS" in DEFAULT_BCOP_ICAL_TEMPLATE
        assert "X-MAINTNOTE-PRECEDENCE=PRIMARY" in DEFAULT_BCOP_ICAL_TEMPLATE

    def test_template_renders_with_maintenance_context(self):
        """Default template renders with maintenance context."""
        from notices.services.template_renderer import TemplateRenderer

        renderer = TemplateRenderer()
        maintenance = MockMaintenance(pk=123, name="TEST-MAINT-001")

        context = {
            "now": maintenance.start,
            "maintenance": maintenance,
            "tenant": None,
            "tenant_impacts": [],
            "impacts": [],
            "highest_impact": "NO-IMPACT",
            "message_sequence": 1,
            "netbox_url": "https://netbox.example.com",
        }

        result = renderer.render(DEFAULT_BCOP_ICAL_TEMPLATE, context)

        assert "UID:123@netbox" in result
        assert "X-MAINTNOTE-PROVIDER:test-provider" in result
        assert "X-MAINTNOTE-MAINTENANCE-ID;X-MAINTNOTE-PRECEDENCE=PRIMARY:TEST-MAINT-001" in result
        assert "X-MAINTNOTE-STATUS:CONFIRMED" in result

    def test_template_renders_with_tenant_context(self):
        """Default template renders with tenant context."""
        from notices.services.template_renderer import TemplateRenderer

        renderer = TemplateRenderer()
        maintenance = MockMaintenance(pk=456)
        tenant = MockTenant(pk=789, name="Acme Corp")

        context = {
            "now": maintenance.start,
            "maintenance": maintenance,
            "tenant": tenant,
            "tenant_impacts": [],
            "impacts": [],
            "highest_impact": "NO-IMPACT",
            "message_sequence": 2,
            "netbox_url": "https://netbox.example.com",
        }

        result = renderer.render(DEFAULT_BCOP_ICAL_TEMPLATE, context)

        assert "UID:456-789@netbox" in result
        assert "X-MAINTNOTE-ACCOUNT:Acme Corp" in result
        assert "SEQUENCE:2" in result


class TestICalGenerationServiceIsMaintenance:
    """Tests for _is_maintenance() method."""

    def test_returns_true_for_maintenance_model(self):
        """_is_maintenance() returns True for Maintenance model."""
        template = MockTemplate()
        maintenance = MockMaintenance()

        service = ICalGenerationService(template, maintenance)

        assert service._is_maintenance() is True

    def test_returns_false_for_outage_model(self):
        """_is_maintenance() returns False for Outage model."""
        template = MockTemplate()
        outage = MockOutage()

        service = ICalGenerationService(template, outage)

        assert service._is_maintenance() is False

    def test_returns_false_for_none_event(self):
        """_is_maintenance() returns False when event is None."""
        template = MockTemplate()

        service = ICalGenerationService(template, None)

        assert service._is_maintenance() is False

    def test_handles_custom_class_with_maintenance_in_name(self):
        """_is_maintenance() detects 'maintenance' in class name."""

        class CustomMaintenance:
            pass

        template = MockTemplate()
        event = CustomMaintenance()

        service = ICalGenerationService(template, event)

        assert service._is_maintenance() is True


@pytest.mark.django_db
class TestICalGenerationServiceWithRealModels:
    """Integration tests with real Django models."""

    def test_with_real_maintenance_model(self, maintenance):
        """Test with real Maintenance model instance."""
        from notices.choices import MessageEventTypeChoices
        from notices.models import MessageTemplate

        template = MessageTemplate(
            name="Test",
            slug="test-ical",
            event_type=MessageEventTypeChoices.MAINTENANCE,
            subject_template="S",
            body_template="B",
            include_ical=True,
            ical_template="UID:{{ maintenance.pk }}@netbox",
        )

        service = ICalGenerationService(template, maintenance)

        assert service.should_generate() is True
        result = service.generate()
        assert f"UID:{maintenance.pk}@netbox" in result

    def test_with_real_tenant(self, maintenance, tenant):
        """Test with real Tenant model instance."""
        from notices.choices import MessageEventTypeChoices
        from notices.models import MessageTemplate

        template = MessageTemplate(
            name="Test",
            slug="test-ical-tenant",
            event_type=MessageEventTypeChoices.MAINTENANCE,
            subject_template="S",
            body_template="B",
            include_ical=True,
            ical_template="TENANT:{{ tenant.name }}",
        )

        service = ICalGenerationService(template, maintenance, tenant=tenant)
        result = service.generate()

        assert result == f"TENANT:{tenant.name}"

    def test_generate_ical_with_real_models(self, maintenance):
        """Test generate_ical convenience function with real models."""
        from notices.choices import MessageEventTypeChoices
        from notices.models import MessageTemplate

        template = MessageTemplate(
            name="Test",
            slug="test-gen-ical",
            event_type=MessageEventTypeChoices.MAINTENANCE,
            subject_template="S",
            body_template="B",
            include_ical=True,
            ical_template="NAME:{{ maintenance.name }}",
        )

        result = generate_ical(template, maintenance)

        assert result == f"NAME:{maintenance.name}"
