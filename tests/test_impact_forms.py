"""
Tests for Impact forms with GenericForeignKey support.
"""

import pytest
from django.test import override_settings


@pytest.mark.django_db
class TestImpactForm:
    """Test ImpactForm GenericForeignKey handling"""

    @pytest.fixture
    def provider(self):
        """Create a test provider"""
        from circuits.models import Provider

        return Provider.objects.create(name="Test Provider", slug="test-provider")

    @pytest.fixture
    def maintenance(self, provider):
        """Create a test maintenance event"""
        from django.utils import timezone

        from notices.choices import MaintenanceTypeChoices
        from notices.models import Maintenance

        return Maintenance.objects.create(
            name="MAINT-001",
            summary="Test maintenance",
            provider=provider,
            status="CONFIRMED",
            start=timezone.now(),
            end=timezone.now() + timezone.timedelta(hours=2),
        )

    @pytest.fixture
    def circuit(self, provider):
        """Create a test circuit"""
        from circuits.models import Circuit, CircuitType

        circuit_type = CircuitType.objects.create(name="Test Type", slug="test-type")
        return Circuit.objects.create(
            cid="CID-001",
            provider=provider,
            type=circuit_type,
        )

    @pytest.fixture
    def site(self):
        """Create a test site"""
        from dcim.models import Site

        return Site.objects.create(
            name="Test Site",
            slug="test-site",
        )

    @pytest.fixture
    def device(self, site):
        """Create a test device"""
        from dcim.models import Device, DeviceRole, DeviceType, Manufacturer

        manufacturer = Manufacturer.objects.create(
            name="Test Manufacturer", slug="test-manufacturer"
        )
        device_type = DeviceType.objects.create(
            manufacturer=manufacturer, model="Test Model", slug="test-model"
        )
        device_role = DeviceRole.objects.create(name="Test Role", slug="test-role")
        return Device.objects.create(
            name="test-device-001",
            site=site,
            device_type=device_type,
            role=device_role,
        )

    def test_form_exists(self):
        """Test that ImpactForm is defined"""
        from notices.forms import ImpactForm

        assert ImpactForm is not None

    def test_form_model(self):
        """Test that form targets Impact model"""
        from notices.forms import ImpactForm
        from notices.models import Impact

        assert ImpactForm.Meta.model == Impact

    def test_form_fields(self):
        """Test that form includes all required fields"""
        from notices.forms import ImpactForm

        expected_fields = (
            "event_content_type",
            "event_object_id",
            "target_content_type",
            "target_object_id",
            "impact",
            "tags",
        )
        assert ImpactForm.Meta.fields == expected_fields

    def test_form_event_content_type_queryset(self):
        """Test that event_content_type is limited to Maintenance and Outage"""
        from notices.forms import ImpactForm

        form = ImpactForm()
        event_ct_field = form.fields["event_content_type"]

        # Get the queryset
        queryset = event_ct_field.queryset

        # Should only include notices Maintenance and Outage
        assert queryset.count() == 2
        models = list(queryset.values_list("model", flat=True))
        assert "maintenance" in models
        assert "outage" in models

    def test_form_target_content_type_default_allowed(self):
        """Test that target_content_type uses default allowed types"""
        from notices.forms import ImpactForm

        form = ImpactForm()
        target_ct_field = form.fields["target_content_type"]

        # Get the queryset
        queryset = target_ct_field.queryset

        # Should include default allowed types (Circuit, PowerFeed, Site)
        # At minimum should include Circuit and Site
        models = list(queryset.values_list("app_label", "model"))

        # Convert to app_label.model format
        model_strings = [f"{app}.{model}" for app, model in models]

        # Check for expected defaults
        assert "circuits.circuit" in model_strings
        assert "dcim.site" in model_strings

    @override_settings(
        PLUGINS_CONFIG={
            "notices": {
                "allowed_content_types": [
                    "circuits.Circuit",
                    "dcim.Device",
                    "dcim.Site",
                ]
            }
        }
    )
    def test_form_target_content_type_custom_allowed(self):
        """Test that target_content_type respects plugin configuration"""
        from notices.forms import ImpactForm

        form = ImpactForm()
        target_ct_field = form.fields["target_content_type"]

        # Get the queryset
        queryset = target_ct_field.queryset

        # Convert to app_label.model format
        models = list(queryset.values_list("app_label", "model"))
        model_strings = [f"{app}.{model}" for app, model in models]

        # Should include configured types
        assert "circuits.circuit" in model_strings
        assert "dcim.device" in model_strings
        assert "dcim.site" in model_strings

    @override_settings(
        PLUGINS_CONFIG={
            "notices": {
                "allowed_content_types": [
                    "circuits.Circuit",
                ]
            }
        }
    )
    def test_form_target_content_type_limited(self):
        """Test that target_content_type can be limited via configuration"""
        from notices.forms import ImpactForm

        form = ImpactForm()
        target_ct_field = form.fields["target_content_type"]

        # Get the queryset
        queryset = target_ct_field.queryset

        # Should only include Circuit
        assert queryset.count() == 1
        models = list(queryset.values_list("app_label", "model"))
        assert models[0] == ("circuits", "circuit")

    def test_form_creates_valid_impact_circuit(self, maintenance, circuit):
        """Test that form can create a valid Impact for a Circuit"""
        from circuits.models import Circuit
        from django.contrib.contenttypes.models import ContentType

        from notices.choices import ImpactTypeChoices
        from notices.forms import ImpactForm
        from notices.models import Maintenance

        maintenance_ct = ContentType.objects.get_for_model(Maintenance)
        circuit_ct = ContentType.objects.get_for_model(Circuit)

        form_data = {
            "event_content_type": maintenance_ct.pk,
            "event_choice": maintenance.pk,
            "target_content_type": circuit_ct.pk,
            "target_choice": circuit.pk,
            "impact": "OUTAGE",
        }

        form = ImpactForm(data=form_data)
        assert form.is_valid(), f"Form errors: {form.errors}"

        impact = form.save()
        assert impact.event == maintenance
        assert impact.target == circuit
        assert impact.impact == "OUTAGE"

    @override_settings(
        PLUGINS_CONFIG={
            "notices": {
                "allowed_content_types": [
                    "dcim.Device",
                    "dcim.Site",
                ]
            }
        }
    )
    def test_form_creates_valid_impact_device(self, maintenance, device):
        """Test that form can create a valid Impact for a Device"""
        from dcim.models import Device
        from django.contrib.contenttypes.models import ContentType

        from notices.choices import ImpactTypeChoices
        from notices.forms import ImpactForm
        from notices.models import Maintenance

        maintenance_ct = ContentType.objects.get_for_model(Maintenance)
        device_ct = ContentType.objects.get_for_model(Device)

        form_data = {
            "event_content_type": maintenance_ct.pk,
            "event_choice": maintenance.pk,
            "target_content_type": device_ct.pk,
            "target_choice": device.pk,
            "impact": "DEGRADED",
        }

        form = ImpactForm(data=form_data)
        assert form.is_valid(), f"Form errors: {form.errors}"

        impact = form.save()
        assert impact.event == maintenance
        assert impact.target == device
        assert impact.impact == "DEGRADED"

    def test_form_field_labels(self):
        """Test that form fields have appropriate labels"""
        from notices.forms import ImpactForm

        form = ImpactForm()

        assert form.fields["event_content_type"].label == "Event Type"
        assert form.fields["event_object_id"].label == "Event"
        assert form.fields["target_content_type"].label == "Target Type"
        assert form.fields["target_object_id"].label == "Target Object"

    def test_form_field_help_text(self):
        """Test that form fields have appropriate help text"""
        from notices.forms import ImpactForm

        form = ImpactForm()

        assert "Maintenance or Outage" in form.fields["event_content_type"].help_text
        assert "maintenance or outage event" in form.fields["event_object_id"].help_text
        assert "Type of affected object" == form.fields["target_content_type"].help_text
        assert "Select the specific object affected by this event" == form.fields["target_object_id"].help_text
