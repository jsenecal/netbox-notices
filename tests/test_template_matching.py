# tests/test_template_matching.py
"""Tests for the template matching service."""

import pytest
from django.contrib.contenttypes.models import ContentType

from notices.choices import (
    BodyFormatChoices,
    MessageEventTypeChoices,
    MessageGranularityChoices,
)
from notices.models import NotificationTemplate, TemplateScope
from notices.services.template_matching import (
    TemplateMatchingService,
    kinds_for_event,
    merge_templates,
    resolve_chain,
)


@pytest.fixture
def contact_role():
    """Create a test contact role."""
    from tenancy.models import ContactRole

    return ContactRole.objects.create(
        name="Network Operations",
        slug="network-operations",
    )


@pytest.fixture
def contact_role_secondary():
    """Create a secondary test contact role."""
    from tenancy.models import ContactRole

    return ContactRole.objects.create(
        name="Technical Support",
        slug="technical-support",
    )


@pytest.fixture
def tenant_secondary():
    """Create a secondary tenant."""
    from tenancy.models import Tenant

    return Tenant.objects.create(
        name="Secondary Tenant",
        slug="secondary-tenant",
    )


@pytest.fixture
def provider_secondary():
    """Create a secondary provider."""
    from circuits.models import Provider

    return Provider.objects.create(
        name="Secondary Provider",
        slug="secondary-provider",
    )


@pytest.fixture
def outage(provider):
    """Create a test outage event."""
    from django.utils import timezone

    from notices.models import Outage

    return Outage.objects.create(
        name="OUTAGE-001",
        summary="Test outage event",
        provider=provider,
        status="REPORTED",
        start=timezone.now(),
    )


@pytest.fixture
def maintenance_template():
    """Create a basic maintenance template."""
    return NotificationTemplate.objects.create(
        name="Maintenance Template",
        slug="maintenance-template",
        event_type=MessageEventTypeChoices.MAINTENANCE,
        granularity=MessageGranularityChoices.PER_TENANT,
        subject_template="Maintenance: {{ maintenance.name }}",
        body_template="Maintenance scheduled: {{ maintenance.summary }}",
        weight=1000,
    )


@pytest.fixture
def high_weight_template():
    """Create a high-weight template for testing priority."""
    return NotificationTemplate.objects.create(
        name="High Weight Template",
        slug="high-weight-template",
        event_type=MessageEventTypeChoices.MAINTENANCE,
        granularity=MessageGranularityChoices.PER_TENANT,
        subject_template="HIGH PRIORITY: {{ maintenance.name }}",
        body_template="High priority maintenance",
        weight=2000,
    )


@pytest.fixture
def template_with_css():
    """Create a template with CSS."""
    return NotificationTemplate.objects.create(
        name="Styled Template",
        slug="styled-template",
        event_type=MessageEventTypeChoices.MAINTENANCE,
        granularity=MessageGranularityChoices.PER_TENANT,
        subject_template="Styled Subject",
        body_template="Styled body",
        css_template="body { color: red; }",
        weight=1500,
    )


@pytest.fixture
def template_with_ical():
    """Create a template with iCal."""
    return NotificationTemplate.objects.create(
        name="iCal Template",
        slug="ical-template",
        event_type=MessageEventTypeChoices.MAINTENANCE,
        granularity=MessageGranularityChoices.PER_TENANT,
        subject_template="iCal Subject",
        body_template="iCal body",
        include_ical=True,
        ical_template="BEGIN:VCALENDAR\nEND:VCALENDAR",
        weight=1200,
    )


@pytest.fixture
def template_with_headers():
    """Create a template with headers."""
    return NotificationTemplate.objects.create(
        name="Headers Template",
        slug="headers-template",
        event_type=MessageEventTypeChoices.MAINTENANCE,
        granularity=MessageGranularityChoices.PER_TENANT,
        subject_template="Headers Subject",
        body_template="Headers body",
        headers_template={"X-Priority": "1", "X-Custom": "value"},
        weight=1100,
    )


def _tpl(slug, **kw):
    defaults = {
        "name": slug,
        "slug": slug,
        "event_type": "maintenance",
        "granularity": "per_tenant",
        "subject_template": "",
        "body_template": "",
        "weight": 1000,
    }
    defaults.update(kw)
    return NotificationTemplate.objects.create(**defaults)


def _scope(template, obj, weight=1000, **kw):
    return TemplateScope.objects.create(
        template=template,
        content_type=ContentType.objects.get_for_model(obj),
        object_id=obj.pk,
        weight=weight,
        **kw,
    )


def _score(template, **ctx):
    return TemplateMatchingService(**ctx).score(template)


@pytest.mark.django_db
class TestKinds:
    def test_base_templates_and_overrides_are_not_kinds(self, maintenance):
        base = _tpl("layout", is_base_template=True)
        kind = _tpl("customer", extends=base)
        _tpl("customer-acme", extends=kind)
        _tpl("outage-only", event_type="outage")
        both = _tpl("both", event_type="both")
        assert set(kinds_for_event(maintenance)) == {kind, both}

    def test_outage_event_gets_outage_and_both_kinds(self, outage):
        _tpl("m")
        o = _tpl("o", event_type="outage")
        both = _tpl("both", event_type="both")
        assert set(kinds_for_event(outage)) == {o, both}


@pytest.mark.django_db
class TestScore:
    def test_unscoped_template_applies_with_base_weight(self, maintenance):
        t = _tpl("t", weight=10)
        assert _score(t, event=maintenance) == 10

    def test_tenant_scope_applies_only_to_that_tenant(self, maintenance, tenant, tenant_secondary):
        t = _tpl("t", weight=10)
        _scope(t, tenant, weight=5)
        assert _score(t, event=maintenance, tenant=tenant) == 15
        assert _score(t, event=maintenance, tenant=tenant_secondary) is None
        assert _score(t, event=maintenance) is None

    def test_wildcard_scope_matches_any_tenant(self, maintenance, tenant, tenant_secondary):
        t = _tpl("t")
        TemplateScope.objects.create(
            template=t, content_type=ContentType.objects.get_for_model(tenant), object_id=None, weight=500
        )
        assert _score(t, event=maintenance, tenant=tenant) == 1500
        assert _score(t, event=maintenance, tenant=tenant_secondary) == 1500

    def test_event_status_filter(self, maintenance, tenant):
        match = _tpl("match")
        _scope(match, tenant, event_status="CONFIRMED")
        miss = _tpl("miss")
        _scope(miss, tenant, event_status="CANCELLED")
        assert _score(match, event=maintenance, tenant=tenant) == 2000
        assert _score(miss, event=maintenance, tenant=tenant) is None

    def test_multiple_matching_scopes_add_weights(self, maintenance, tenant, provider):
        t = _tpl("t")
        _scope(t, tenant, weight=500)
        _scope(t, provider, weight=300)
        assert _score(t, event=maintenance, tenant=tenant, provider=provider) == 1800

    def test_provider_scope_resolved_from_event(self, maintenance, provider, provider_secondary):
        t = _tpl("t")
        _scope(t, provider)
        assert _score(t, event=maintenance) == 2000
        assert _score(t, event=maintenance, provider=provider_secondary) is None

    def test_explicit_provider_overrides_event_provider(self, maintenance, provider_secondary):
        t = _tpl("t")
        _scope(t, provider_secondary)
        assert _score(t, event=maintenance) is None
        assert _score(t, event=maintenance, provider=provider_secondary) == 2000


@pytest.mark.django_db
class TestResolveChain:
    def test_matching_override_wins_over_root(self, maintenance, tenant):
        root = _tpl("root")
        acme = _tpl("acme", extends=root)
        _scope(acme, tenant)
        matcher = TemplateMatchingService(event=maintenance, tenant=tenant)
        assert resolve_chain(root, matcher) == [acme, root]

    def test_non_matching_override_is_ignored(self, maintenance, tenant, tenant_secondary):
        root = _tpl("root")
        acme = _tpl("acme", extends=root)
        _scope(acme, tenant)
        matcher = TemplateMatchingService(event=maintenance, tenant=tenant_secondary)
        assert resolve_chain(root, matcher) == [root]

    def test_override_for_other_event_type_is_ignored(self, maintenance, tenant):
        root = _tpl("root", event_type="both")
        outage_only = _tpl("outage-only", extends=root, event_type="outage")
        both = _tpl("both", extends=root, event_type="both", weight=1)
        _scope(outage_only, tenant)
        _scope(both, tenant)
        matcher = TemplateMatchingService(event=maintenance, tenant=tenant)
        assert resolve_chain(root, matcher) == [both, root]

    def test_highest_scoring_override_wins(self, maintenance, tenant):
        root = _tpl("root")
        low = _tpl("low", extends=root, weight=1)
        high = _tpl("high", extends=root, weight=2000)
        _scope(low, tenant)
        _scope(high, tenant)
        matcher = TemplateMatchingService(event=maintenance, tenant=tenant)
        assert resolve_chain(root, matcher)[0] == high

    def test_base_ancestors_are_appended(self, maintenance):
        layout = _tpl("layout", is_base_template=True)
        root = _tpl("root", extends=layout)
        assert resolve_chain(root, TemplateMatchingService(event=maintenance)) == [root, layout]

    def test_nested_overrides(self, maintenance, tenant):
        root = _tpl("root")
        mid = _tpl("mid", extends=root)
        leaf = _tpl("leaf", extends=mid)
        _scope(leaf, tenant)
        matcher = TemplateMatchingService(event=maintenance, tenant=tenant)
        assert resolve_chain(root, matcher) == [leaf, mid, root]


@pytest.mark.django_db
class TestChainMerge:
    def test_empty_fields_fall_back_to_parent(self):
        root = _tpl("root", subject_template="S-root", body_template="B-root", css_template="c")
        acme = _tpl("acme", extends=root, subject_template="S-acme")
        merged = merge_templates([acme, root])
        assert merged["subject_template"] == "S-acme"
        assert merged["body_template"] == "B-root"
        assert merged["css_template"] == "c"
        assert merged["granularity"] == "per_tenant"
        assert "extends" not in merged

    def test_granularity_comes_from_root_kind_not_base_layout(self):
        layout = _tpl("layout", is_base_template=True, granularity="per_tenant")
        root = _tpl("root", extends=layout, granularity="per_event")
        assert merge_templates([root, layout])["granularity"] == "per_event"


# ============================================================================
# Field-Level Merge Tests
# ============================================================================


@pytest.mark.django_db
class TestFieldLevelMerge:
    """Tests for field-level merging."""

    def test_merge_subject_first_wins(self, maintenance_template, high_weight_template):
        """Test that first (highest) template's subject wins."""
        # Order by weight: high_weight (2000), maintenance (1000)
        config = merge_templates([high_weight_template, maintenance_template])

        assert config["subject_template"] == "HIGH PRIORITY: {{ maintenance.name }}"

    def test_merge_body_first_wins(self, maintenance_template, high_weight_template):
        """Test that first template's body and format win."""
        config = merge_templates([high_weight_template, maintenance_template])

        assert config["body_template"] == "High priority maintenance"
        assert config["body_format"] == BodyFormatChoices.MARKDOWN

    def test_merge_css_first_nonempty_wins(self, maintenance_template, template_with_css):
        """Test that first non-empty CSS wins."""
        # maintenance has no CSS, template_with_css has CSS
        # Order: template_with_css (1500), maintenance (1000)
        config = merge_templates([template_with_css, maintenance_template])

        assert config["css_template"] == "body { color: red; }"

    def test_merge_ical_first_nonempty_wins(self, maintenance_template, template_with_ical):
        """Test that first non-empty iCal wins."""
        config = merge_templates([template_with_ical, maintenance_template])

        assert config["ical_template"] == "BEGIN:VCALENDAR\nEND:VCALENDAR"

    def test_merge_include_ical_or_logic(self, maintenance_template, template_with_ical):
        """Test that include_ical uses OR logic."""
        # maintenance has include_ical=False, template_with_ical has True
        config = merge_templates([maintenance_template, template_with_ical])

        assert config["include_ical"] is True

    def test_merge_headers_dict_merge(self, maintenance_template, template_with_headers):
        """Test that headers are merged (first wins per key)."""
        # Add headers to maintenance template too
        maintenance_template.headers_template = {"X-Priority": "5", "X-Other": "other"}
        maintenance_template.save()

        # template_with_headers has higher weight (1100 vs 1000)
        config = merge_templates([template_with_headers, maintenance_template])

        # X-Priority from template_with_headers wins (first)
        assert config["headers_template"]["X-Priority"] == "1"
        # X-Custom only in template_with_headers
        assert config["headers_template"]["X-Custom"] == "value"
        # X-Other only in maintenance_template (merged in)
        assert config["headers_template"]["X-Other"] == "other"


@pytest.mark.django_db
class TestContactRolesUnion:
    """Tests for contact roles union."""

    def test_merge_contact_roles_union(self, contact_role, contact_role_secondary):
        """Test that contact roles are unioned."""
        template1 = NotificationTemplate.objects.create(
            name="Template 1",
            slug="template-1",
            event_type=MessageEventTypeChoices.MAINTENANCE,
            subject_template="S1",
            body_template="B1",
            weight=2000,
        )
        template1.contact_roles.add(contact_role)

        template2 = NotificationTemplate.objects.create(
            name="Template 2",
            slug="template-2",
            event_type=MessageEventTypeChoices.MAINTENANCE,
            subject_template="S2",
            body_template="B2",
            weight=1000,
        )
        template2.contact_roles.add(contact_role_secondary)

        config = merge_templates([template1, template2])

        # Both roles should be included
        assert contact_role in config["contact_roles"]
        assert contact_role_secondary in config["contact_roles"]

    def test_merge_contact_priorities_union(self):
        """Test that contact priorities are unioned."""
        template1 = NotificationTemplate.objects.create(
            name="Template Priorities 1",
            slug="template-priorities-1",
            event_type=MessageEventTypeChoices.MAINTENANCE,
            subject_template="S1",
            body_template="B1",
            weight=2000,
            contact_priorities=["primary"],
        )

        template2 = NotificationTemplate.objects.create(
            name="Template Priorities 2",
            slug="template-priorities-2",
            event_type=MessageEventTypeChoices.MAINTENANCE,
            subject_template="S2",
            body_template="B2",
            weight=1000,
            contact_priorities=["secondary", "tertiary"],
        )

        config = merge_templates([template1, template2])

        assert "primary" in config["contact_priorities"]
        assert "secondary" in config["contact_priorities"]
        assert "tertiary" in config["contact_priorities"]


@pytest.mark.django_db
class TestMergeTemplatesEdgeCases:
    """Tests for merge_templates edge cases."""

    def test_merge_empty_list(self):
        """Test merging empty list returns None."""
        result = merge_templates([])
        assert result is None

    def test_merge_none_returns_none(self):
        """Test merging None returns None."""
        result = merge_templates(None)
        assert result is None

    def test_merge_single_template(self, maintenance_template):
        """Test merging single template."""
        config = merge_templates([maintenance_template])

        assert config["subject_template"] == "Maintenance: {{ maintenance.name }}"
        assert config["body_template"] == "Maintenance scheduled: {{ maintenance.summary }}"
        assert config["include_ical"] is False
