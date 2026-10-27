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

        manufacturer = Manufacturer.objects.create(name="Test Manufacturer", slug="test-manufacturer")
        device_type = DeviceType.objects.create(manufacturer=manufacturer, model="Test Model", slug="test-model")
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


def _picker_config(settings, **notices):
    settings.PLUGINS_CONFIG = {"notices": {"allowed_content_types": ["dcim.Interface"], **notices}}


def _choice_attrs(form_class, model, field="target_choice", ct_field="target_content_type"):
    from django.contrib.contenttypes.models import ContentType

    form = form_class(initial={ct_field: ContentType.objects.get_for_model(model).pk})
    return form.fields[field].widget.attrs


def _w002_messages():
    from notices.checks import check_parent_fields

    warnings = check_parent_fields(None)
    assert {w.id for w in warnings} <= {"notices.W002"}
    return [w.msg for w in warnings]


@pytest.mark.django_db
class TestImpactFormTargetPicker:
    """The target dropdown must give the user device context for Interface targets."""

    def test_interface_target_has_selector_and_parent(self, settings):
        from dcim.models import Interface

        from notices.forms import ImpactForm

        _picker_config(settings, parent_fields={"dcim.Interface": "device"})
        attrs = _choice_attrs(ImpactForm, Interface)

        assert attrs["selector"] == "dcim.interface"
        assert attrs["ts-parent-field"] == "device"
        assert _w002_messages() == []

    def test_no_parent_without_config(self, settings):
        from dcim.models import Interface

        from notices.forms import ImpactForm

        _picker_config(settings)
        attrs = _choice_attrs(ImpactForm, Interface)

        assert attrs["selector"] == "dcim.interface"
        assert "ts-parent-field" not in attrs

    def test_keys_are_case_insensitive_in_check_and_runtime(self, settings):
        """Regression (PR 87 review): W002 resolved keys case-sensitively while the runtime did not."""
        from dcim.models import Interface

        from notices.forms import ImpactForm

        _picker_config(settings, parent_fields={"DCIM.Interface": "device"})

        assert _choice_attrs(ImpactForm, Interface)["ts-parent-field"] == "device"
        assert _w002_messages() == []

    @pytest.mark.parametrize(
        "parent_fields, reported",
        [
            ({"dcim.Interface": "no_such_field"}, ["'dcim.Interface'"]),
            ({"dcim.Interface": "device", "DCIM.interface": "device"}, ["'dcim.Interface'", "'DCIM.interface'"]),
            ([("dcim.Interface", "device")], ["expected a dict, got list"]),
        ],
        ids=["unknown-field", "case-duplicate-keys", "not-a-dict"],
    )
    def test_invalid_interface_entry_is_ignored_and_reported(self, settings, parent_fields, reported):
        from dcim.models import Interface

        from notices.forms import ImpactForm

        _picker_config(settings, parent_fields=parent_fields)

        assert "ts-parent-field" not in _choice_attrs(ImpactForm, Interface)
        messages = _w002_messages()
        assert len(messages) == len(reported)
        assert all(text in msg for text, msg in zip(reported, messages, strict=True))

    def test_invalid_entries_are_reported_with_reason(self, settings):
        _picker_config(
            settings,
            parent_fields={
                "bogus.Model": "x",
                "dcim": "y",
                "dcim.Interface": "",
                "notices.Impact": "target",
                "dcim.Device": "site",
                "auth.Permission": "content_type",
            },
        )

        messages = _w002_messages()

        assert len(messages) == 6
        assert "not an installed" in messages[0] and "'bogus.Model'" in messages[0]
        assert "not an installed" in messages[1]
        assert "must be a field name" in messages[2]
        assert "notices.Impact.target is not a ForeignKey" in messages[3]
        assert "not in the brief REST representation" in messages[4]
        assert "has no REST serializer" in messages[5]

    def test_stale_content_type_and_malformed_allowed_type_are_skipped(self, settings):
        from django.contrib.contenttypes.models import ContentType

        from notices.forms import ImpactForm

        _picker_config(settings, allowed_content_types=["dcim", "dcim.Interface"])
        stale = ContentType.objects.create(app_label="removed_plugin", model="gone")

        form = ImpactForm(initial={"target_content_type": stale.pk})

        assert "target_choice" not in form.fields
        assert [ct.model for ct in form.fields["target_content_type"].queryset] == ["interface"]

    def test_model_without_filter_form_gets_no_selector(self, settings):
        from notices.forms import ImpactForm
        from notices.models import Impact
        from notices.utils import has_filter_form

        _picker_config(settings, allowed_content_types=["notices.Impact"])

        assert has_filter_form(Impact) is False  # notices.forms has no ImpactFilterForm
        assert "selector" not in _choice_attrs(ImpactForm, Impact)

    def test_model_without_restricted_manager_gets_no_selector(self):
        from types import SimpleNamespace

        from notices.utils import has_filter_form

        # dcim.forms.InterfaceFilterForm and dcim.filtersets.InterfaceFilterSet exist, but the
        # selector modal would still fail on `objects.restrict()`.
        plain = type("Interface", (), {"objects": object(), "_meta": SimpleNamespace(app_label="dcim")})

        assert has_filter_form(plain) is False


@pytest.mark.django_db
class TestTemplateScopeFormPicker:
    def test_scope_object_is_optional_and_gets_selector_and_parent(self, settings):
        from dcim.models import Interface
        from django.contrib.contenttypes.models import ContentType

        from notices.forms import TemplateScopeForm

        _picker_config(settings, parent_fields={"dcim.Interface": "device"})
        form = TemplateScopeForm(initial={"content_type": ContentType.objects.get_for_model(Interface).pk})
        field = form.fields["scope_choice"]

        assert field.widget.attrs["selector"] == "dcim.interface"
        assert field.widget.attrs["ts-parent-field"] == "device"
        assert field.required is False
        assert field.label == "Specific Interface (optional)"
