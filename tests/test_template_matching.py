# tests/test_template_matching.py
"""Tests for the template matching service."""

import pytest
from django.contrib.contenttypes.models import ContentType

from notices.choices import (
    BodyFormatChoices,
    MessageEventTypeChoices,
    MessageGranularityChoices,
)
from notices.models import MessageTemplate, TemplateScope
from notices.services.template_matching import (
    TemplateMatchingService,
    find_matching_templates,
    merge_templates,
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
    return MessageTemplate.objects.create(
        name="Maintenance Template",
        slug="maintenance-template",
        event_type=MessageEventTypeChoices.MAINTENANCE,
        granularity=MessageGranularityChoices.PER_TENANT,
        subject_template="Maintenance: {{ maintenance.name }}",
        body_template="Maintenance scheduled: {{ maintenance.summary }}",
        weight=1000,
    )


@pytest.fixture
def outage_template():
    """Create a basic outage template."""
    return MessageTemplate.objects.create(
        name="Outage Template",
        slug="outage-template",
        event_type=MessageEventTypeChoices.OUTAGE,
        granularity=MessageGranularityChoices.PER_TENANT,
        subject_template="Outage: {{ outage.name }}",
        body_template="Outage reported: {{ outage.summary }}",
        weight=1000,
    )


@pytest.fixture
def both_template():
    """Create a template for both event types."""
    return MessageTemplate.objects.create(
        name="Both Template",
        slug="both-template",
        event_type=MessageEventTypeChoices.BOTH,
        granularity=MessageGranularityChoices.PER_TENANT,
        subject_template="Event: {{ maintenance.name if maintenance else outage.name }}",
        body_template="Event details here",
        weight=500,
    )


@pytest.fixture
def standalone_template():
    """Create a standalone template (no event type)."""
    return MessageTemplate.objects.create(
        name="Standalone Template",
        slug="standalone-template",
        event_type=MessageEventTypeChoices.NONE,
        granularity=MessageGranularityChoices.PER_TENANT,
        subject_template="Notification",
        body_template="General notification",
        weight=1000,
    )


@pytest.fixture
def high_weight_template():
    """Create a high-weight template for testing priority."""
    return MessageTemplate.objects.create(
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
    return MessageTemplate.objects.create(
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
    return MessageTemplate.objects.create(
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
    return MessageTemplate.objects.create(
        name="Headers Template",
        slug="headers-template",
        event_type=MessageEventTypeChoices.MAINTENANCE,
        granularity=MessageGranularityChoices.PER_TENANT,
        subject_template="Headers Subject",
        body_template="Headers body",
        headers_template={"X-Priority": "1", "X-Custom": "value"},
        weight=1100,
    )


# ============================================================================
# Event Type Filtering Tests
# ============================================================================


@pytest.mark.django_db
class TestEventTypeFiltering:
    """Tests for event type filtering."""

    def test_maintenance_event_finds_maintenance_templates(self, maintenance, maintenance_template):
        """Test that maintenance events match maintenance templates."""
        service = TemplateMatchingService(event=maintenance)
        templates = service.find_templates()

        template_names = [t.name for t, _ in templates]
        assert "Maintenance Template" in template_names

    def test_maintenance_event_finds_both_templates(self, maintenance, maintenance_template, both_template):
        """Test that maintenance events also match 'both' templates."""
        service = TemplateMatchingService(event=maintenance)
        templates = service.find_templates()

        template_names = [t.name for t, _ in templates]
        assert "Maintenance Template" in template_names
        assert "Both Template" in template_names

    def test_maintenance_event_excludes_outage_templates(self, maintenance, outage_template):
        """Test that maintenance events don't match outage-only templates."""
        service = TemplateMatchingService(event=maintenance)
        templates = service.find_templates()

        template_names = [t.name for t, _ in templates]
        assert "Outage Template" not in template_names

    def test_outage_event_finds_outage_templates(self, outage, outage_template):
        """Test that outage events match outage templates."""
        service = TemplateMatchingService(event=outage)
        templates = service.find_templates()

        template_names = [t.name for t, _ in templates]
        assert "Outage Template" in template_names

    def test_outage_event_finds_both_templates(self, outage, outage_template, both_template):
        """Test that outage events also match 'both' templates."""
        service = TemplateMatchingService(event=outage)
        templates = service.find_templates()

        template_names = [t.name for t, _ in templates]
        assert "Outage Template" in template_names
        assert "Both Template" in template_names

    def test_outage_event_excludes_maintenance_templates(self, outage, maintenance_template):
        """Test that outage events don't match maintenance-only templates."""
        service = TemplateMatchingService(event=outage)
        templates = service.find_templates()

        template_names = [t.name for t, _ in templates]
        assert "Maintenance Template" not in template_names

    def test_standalone_no_event(self, standalone_template):
        """Test that no event finds standalone templates."""
        service = TemplateMatchingService(event=None)
        templates = service.find_templates()

        template_names = [t.name for t, _ in templates]
        assert "Standalone Template" in template_names

    def test_standalone_excludes_event_templates(self, maintenance_template, outage_template, standalone_template):
        """Test that no event excludes event-specific templates."""
        service = TemplateMatchingService(event=None)
        templates = service.find_templates()

        template_names = [t.name for t, _ in templates]
        assert "Maintenance Template" not in template_names
        assert "Outage Template" not in template_names


# ============================================================================
# Scope Matching Tests
# ============================================================================


@pytest.mark.django_db
class TestScopeMatching:
    """Tests for scope matching logic."""

    def test_scope_specific_object_matches(self, maintenance, maintenance_template, tenant):
        """Test that scope with specific object matches."""
        tenant_ct = ContentType.objects.get_for_model(tenant)
        TemplateScope.objects.create(
            template=maintenance_template,
            content_type=tenant_ct,
            object_id=tenant.pk,
            weight=500,
        )

        service = TemplateMatchingService(event=maintenance, tenant=tenant)
        templates = service.find_templates()

        assert len(templates) > 0
        # Check the template was found
        template_names = [t.name for t, _ in templates]
        assert "Maintenance Template" in template_names

    def test_scope_specific_object_no_match_different_object(
        self, maintenance, maintenance_template, tenant, tenant_secondary
    ):
        """Test that scope with specific object doesn't match different object."""
        tenant_ct = ContentType.objects.get_for_model(tenant)
        TemplateScope.objects.create(
            template=maintenance_template,
            content_type=tenant_ct,
            object_id=tenant.pk,  # Scope for original tenant
            weight=500,
        )

        # Use secondary tenant
        service = TemplateMatchingService(event=maintenance, tenant=tenant_secondary)
        templates = service.find_templates()

        # Template should NOT match because scope is for different tenant
        template_names = [t.name for t, _ in templates]
        assert "Maintenance Template" not in template_names

    def test_scope_wildcard_matches_any_object(self, maintenance, maintenance_template, tenant, tenant_secondary):
        """Test that wildcard scope (object_id=None) matches any object."""
        tenant_ct = ContentType.objects.get_for_model(tenant)
        TemplateScope.objects.create(
            template=maintenance_template,
            content_type=tenant_ct,
            object_id=None,  # Wildcard - all tenants
            weight=500,
        )

        # Should match with any tenant
        service = TemplateMatchingService(event=maintenance, tenant=tenant)
        templates = service.find_templates()
        template_names = [t.name for t, _ in templates]
        assert "Maintenance Template" in template_names

        service2 = TemplateMatchingService(event=maintenance, tenant=tenant_secondary)
        templates2 = service2.find_templates()
        template_names2 = [t.name for t, _ in templates2]
        assert "Maintenance Template" in template_names2

    def test_scope_provider_matches(self, maintenance, maintenance_template, provider):
        """Test that provider scope matches."""
        provider_ct = ContentType.objects.get_for_model(provider)
        TemplateScope.objects.create(
            template=maintenance_template,
            content_type=provider_ct,
            object_id=provider.pk,
            weight=500,
        )

        service = TemplateMatchingService(event=maintenance, provider=provider)
        templates = service.find_templates()

        template_names = [t.name for t, _ in templates]
        assert "Maintenance Template" in template_names

    def test_scope_provider_no_match_different_provider(
        self, maintenance, maintenance_template, provider, provider_secondary
    ):
        """Test that provider scope doesn't match different provider."""
        provider_ct = ContentType.objects.get_for_model(provider)
        TemplateScope.objects.create(
            template=maintenance_template,
            content_type=provider_ct,
            object_id=provider.pk,
            weight=500,
        )

        # Use secondary provider
        service = TemplateMatchingService(event=maintenance, provider=provider_secondary)
        templates = service.find_templates()

        template_names = [t.name for t, _ in templates]
        assert "Maintenance Template" not in template_names

    def test_global_template_no_scopes_always_matches(self, maintenance, maintenance_template):
        """Test that template with no scopes (global) always matches."""
        # No scopes added
        service = TemplateMatchingService(event=maintenance)
        templates = service.find_templates()

        template_names = [t.name for t, _ in templates]
        assert "Maintenance Template" in template_names


# ============================================================================
# Event Status Filtering Tests
# ============================================================================


@pytest.mark.django_db
class TestEventStatusFiltering:
    """Tests for event status filtering."""

    def test_scope_event_status_matches(self, maintenance, maintenance_template, tenant):
        """Test that scope with matching event status matches."""
        tenant_ct = ContentType.objects.get_for_model(tenant)
        TemplateScope.objects.create(
            template=maintenance_template,
            content_type=tenant_ct,
            object_id=tenant.pk,
            event_status="CONFIRMED",  # Matches maintenance.status
            weight=500,
        )

        service = TemplateMatchingService(event=maintenance, tenant=tenant)
        templates = service.find_templates()

        template_names = [t.name for t, _ in templates]
        assert "Maintenance Template" in template_names

    def test_scope_event_status_no_match(self, maintenance, maintenance_template, tenant):
        """Test that scope with different event status doesn't match."""
        tenant_ct = ContentType.objects.get_for_model(tenant)
        TemplateScope.objects.create(
            template=maintenance_template,
            content_type=tenant_ct,
            object_id=tenant.pk,
            event_status="CANCELLED",  # Different from CONFIRMED
            weight=500,
        )

        service = TemplateMatchingService(event=maintenance, tenant=tenant)
        templates = service.find_templates()

        template_names = [t.name for t, _ in templates]
        assert "Maintenance Template" not in template_names

    def test_scope_no_event_status_filter_matches_any(self, maintenance, maintenance_template, tenant):
        """Test that scope without event_status matches any status."""
        tenant_ct = ContentType.objects.get_for_model(tenant)
        TemplateScope.objects.create(
            template=maintenance_template,
            content_type=tenant_ct,
            object_id=tenant.pk,
            event_status="",  # No filter
            weight=500,
        )

        service = TemplateMatchingService(event=maintenance, tenant=tenant)
        templates = service.find_templates()

        template_names = [t.name for t, _ in templates]
        assert "Maintenance Template" in template_names


# ============================================================================
# Score Calculation Tests
# ============================================================================


@pytest.mark.django_db
class TestScoreCalculation:
    """Tests for score calculation."""

    def test_base_weight_used_for_global_template(self, maintenance, maintenance_template):
        """Test that base weight is used for templates without scopes."""
        service = TemplateMatchingService(event=maintenance)
        templates = service.find_templates()

        for template, score in templates:
            if template.name == "Maintenance Template":
                assert score == 1000  # Base weight

    def test_scope_weight_added_to_score(self, maintenance, maintenance_template, tenant):
        """Test that scope weight is added to base weight."""
        tenant_ct = ContentType.objects.get_for_model(tenant)
        TemplateScope.objects.create(
            template=maintenance_template,
            content_type=tenant_ct,
            object_id=tenant.pk,
            weight=500,
        )

        service = TemplateMatchingService(event=maintenance, tenant=tenant)
        templates = service.find_templates()

        for template, score in templates:
            if template.name == "Maintenance Template":
                assert score == 1500  # 1000 base + 500 scope

    def test_multiple_matching_scopes_add_weights(self, maintenance, maintenance_template, tenant, provider):
        """Test that multiple matching scopes add their weights."""
        tenant_ct = ContentType.objects.get_for_model(tenant)
        provider_ct = ContentType.objects.get_for_model(provider)

        TemplateScope.objects.create(
            template=maintenance_template,
            content_type=tenant_ct,
            object_id=tenant.pk,
            weight=500,
        )
        TemplateScope.objects.create(
            template=maintenance_template,
            content_type=provider_ct,
            object_id=provider.pk,
            weight=300,
        )

        service = TemplateMatchingService(event=maintenance, tenant=tenant, provider=provider)
        templates = service.find_templates()

        for template, score in templates:
            if template.name == "Maintenance Template":
                assert score == 1800  # 1000 base + 500 + 300

    def test_higher_weight_template_sorted_first(self, maintenance, maintenance_template, high_weight_template):
        """Test that templates are sorted by score descending."""
        service = TemplateMatchingService(event=maintenance)
        templates = service.find_templates()

        # High weight should be first
        assert templates[0][0].name == "High Weight Template"
        assert templates[0][1] == 2000
        assert templates[1][0].name == "Maintenance Template"
        assert templates[1][1] == 1000


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
        template1 = MessageTemplate.objects.create(
            name="Template 1",
            slug="template-1",
            event_type=MessageEventTypeChoices.MAINTENANCE,
            subject_template="S1",
            body_template="B1",
            weight=2000,
        )
        template1.contact_roles.add(contact_role)

        template2 = MessageTemplate.objects.create(
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
        template1 = MessageTemplate.objects.create(
            name="Template Priorities 1",
            slug="template-priorities-1",
            event_type=MessageEventTypeChoices.MAINTENANCE,
            subject_template="S1",
            body_template="B1",
            weight=2000,
            contact_priorities=["primary"],
        )

        template2 = MessageTemplate.objects.create(
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


# ============================================================================
# Template Inheritance Tests
# ============================================================================


@pytest.mark.django_db
class TestTemplateInheritance:
    """Tests for template inheritance (extends)."""

    def test_merge_extends_first_nonempty_wins(self):
        """Test that first non-null extends wins."""
        base = MessageTemplate.objects.create(
            name="Base Template",
            slug="base-template-inherit",
            event_type=MessageEventTypeChoices.MAINTENANCE,
            subject_template="Base Subject",
            body_template="{% block content %}{% endblock %}",
            is_base_template=True,
        )

        child = MessageTemplate.objects.create(
            name="Child Template",
            slug="child-template-inherit",
            event_type=MessageEventTypeChoices.MAINTENANCE,
            subject_template="Child Subject",
            body_template="{% block content %}Child{% endblock %}",
            extends=base,
            weight=1500,
        )

        template_no_extends = MessageTemplate.objects.create(
            name="No Extends",
            slug="no-extends-template",
            event_type=MessageEventTypeChoices.MAINTENANCE,
            subject_template="No Extends Subject",
            body_template="Body",
            weight=2000,
        )

        # Order: no_extends (2000), child (1500)
        config = merge_templates([template_no_extends, child])

        # Child has extends, but no_extends is first with no extends
        # First non-null wins, so child's extends should be picked
        # Actually, no_extends has None, so child's extends wins
        assert config["extends"] == base


# ============================================================================
# Global Templates Tests
# ============================================================================


@pytest.mark.django_db
class TestGlobalTemplates:
    """Tests for global templates (no scopes)."""

    def test_global_template_matches_without_context(self, maintenance, maintenance_template):
        """Test that global template matches without any context objects."""
        service = TemplateMatchingService(event=maintenance)
        templates = service.find_templates()

        template_names = [t.name for t, _ in templates]
        assert "Maintenance Template" in template_names

    def test_global_template_matches_with_any_context(self, maintenance, maintenance_template, tenant, provider):
        """Test that global template still matches with any context."""
        service = TemplateMatchingService(event=maintenance, tenant=tenant, provider=provider)
        templates = service.find_templates()

        template_names = [t.name for t, _ in templates]
        assert "Maintenance Template" in template_names


# ============================================================================
# Helper Function Tests
# ============================================================================


@pytest.mark.django_db
class TestFindMatchingTemplates:
    """Tests for find_matching_templates convenience function."""

    def test_find_matching_templates_with_event(self, maintenance, maintenance_template):
        """Test convenience function with event."""
        templates = find_matching_templates(event=maintenance)

        template_names = [t.name for t, _ in templates]
        assert "Maintenance Template" in template_names

    def test_find_matching_templates_with_tenant(self, maintenance, maintenance_template, tenant):
        """Test convenience function with tenant."""
        tenant_ct = ContentType.objects.get_for_model(tenant)
        TemplateScope.objects.create(
            template=maintenance_template,
            content_type=tenant_ct,
            object_id=tenant.pk,
            weight=500,
        )

        templates = find_matching_templates(event=maintenance, tenant=tenant)

        template_names = [t.name for t, _ in templates]
        assert "Maintenance Template" in template_names

    def test_find_matching_templates_with_provider(self, maintenance, maintenance_template, provider):
        """Test convenience function with provider."""
        templates = find_matching_templates(event=maintenance, provider=provider)

        template_names = [t.name for t, _ in templates]
        assert "Maintenance Template" in template_names

    def test_find_matching_templates_no_matches(self, maintenance, outage_template):
        """Test convenience function with no matching templates."""
        templates = find_matching_templates(event=maintenance)

        # outage_template shouldn't match maintenance event
        template_names = [t.name for t, _ in templates]
        assert "Outage Template" not in template_names


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


@pytest.mark.django_db
class TestGetBestTemplate:
    """Tests for get_best_template method."""

    def test_get_best_template_returns_highest_score(self, maintenance, maintenance_template, high_weight_template):
        """Test that get_best_template returns highest scoring template."""
        service = TemplateMatchingService(event=maintenance)
        best = service.get_best_template()

        assert best.name == "High Weight Template"

    def test_get_best_template_no_matches(self, maintenance, outage_template):
        """Test that get_best_template returns None when no matches."""
        service = TemplateMatchingService(event=maintenance)
        best = service.get_best_template()

        # Only outage template exists, won't match maintenance
        # But if no templates match at all, should return None
        # Actually outage_template doesn't match, so this should be None
        # Let's verify: outage_template has event_type=OUTAGE, maintenance service looks for MAINTENANCE
        assert best is None


@pytest.mark.django_db
class TestGetMergedConfig:
    """Tests for get_merged_config method."""

    def test_get_merged_config_returns_dict(self, maintenance, maintenance_template, template_with_css):
        """Test that get_merged_config returns merged dict."""
        service = TemplateMatchingService(event=maintenance)
        config = service.get_merged_config()

        assert isinstance(config, dict)
        assert "subject_template" in config
        assert "body_template" in config
        assert "css_template" in config

    def test_get_merged_config_no_matches(self, maintenance, outage_template):
        """Test that get_merged_config returns None when no matches."""
        service = TemplateMatchingService(event=maintenance)
        config = service.get_merged_config()

        assert config is None


# ============================================================================
# Event Provider Resolution Tests
# ============================================================================


@pytest.mark.django_db
class TestEventProviderResolution:
    """Tests for resolving provider from event."""

    def test_provider_resolved_from_event(self, maintenance, maintenance_template, provider):
        """Test that provider is resolved from event.provider."""
        provider_ct = ContentType.objects.get_for_model(provider)
        TemplateScope.objects.create(
            template=maintenance_template,
            content_type=provider_ct,
            object_id=provider.pk,
            weight=500,
        )

        # Don't pass provider explicitly - should be resolved from event
        service = TemplateMatchingService(event=maintenance)
        templates = service.find_templates()

        # Template should match because maintenance.provider == provider
        template_names = [t.name for t, _ in templates]
        assert "Maintenance Template" in template_names

    def test_explicit_provider_overrides_event_provider(
        self, maintenance, maintenance_template, provider, provider_secondary
    ):
        """Test that explicit provider takes precedence."""
        provider_ct = ContentType.objects.get_for_model(provider)
        TemplateScope.objects.create(
            template=maintenance_template,
            content_type=provider_ct,
            object_id=provider_secondary.pk,  # Scope for secondary provider
            weight=500,
        )

        # Pass secondary provider explicitly (different from maintenance.provider)
        service = TemplateMatchingService(event=maintenance, provider=provider_secondary)
        templates = service.find_templates()

        # Template should match because we explicitly passed provider_secondary
        template_names = [t.name for t, _ in templates]
        assert "Maintenance Template" in template_names
