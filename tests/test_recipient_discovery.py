# tests/test_recipient_discovery.py
"""Tests for the recipient discovery service."""

import pytest
from django.contrib.contenttypes.models import ContentType

from notices.choices import MessageEventTypeChoices, MessageGranularityChoices
from notices.models import Impact, NotificationTemplate
from notices.services.recipient_discovery import RecipientDiscoveryService, discover_recipients


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
def contact_with_assignment(tenant, contact_role):
    """Create a contact with an assignment to a tenant."""
    from tenancy.models import Contact, ContactAssignment

    contact = Contact.objects.create(
        name="Network Admin",
        email="network-admin@example.com",
    )
    tenant_ct = ContentType.objects.get_for_model(tenant)
    ContactAssignment.objects.create(
        contact=contact,
        object_type=tenant_ct,
        object_id=tenant.pk,
        role=contact_role,
        priority="primary",
    )
    return contact


@pytest.fixture
def contact_secondary(tenant, contact_role):
    """Create a secondary contact with assignment."""
    from tenancy.models import Contact, ContactAssignment

    contact = Contact.objects.create(
        name="Secondary Contact",
        email="secondary@example.com",
    )
    tenant_ct = ContentType.objects.get_for_model(tenant)
    ContactAssignment.objects.create(
        contact=contact,
        object_type=tenant_ct,
        object_id=tenant.pk,
        role=contact_role,
        priority="secondary",
    )
    return contact


@pytest.fixture
def contact_inactive(tenant, contact_role):
    """Create an inactive contact with assignment."""
    from tenancy.models import Contact, ContactAssignment

    contact = Contact.objects.create(
        name="Inactive Contact",
        email="inactive@example.com",
    )
    tenant_ct = ContentType.objects.get_for_model(tenant)
    ContactAssignment.objects.create(
        contact=contact,
        object_type=tenant_ct,
        object_id=tenant.pk,
        role=contact_role,
        priority="inactive",
    )
    return contact


@pytest.fixture
def contact_different_role(tenant, contact_role_secondary):
    """Create a contact with a different role."""
    from tenancy.models import Contact, ContactAssignment

    contact = Contact.objects.create(
        name="Support Contact",
        email="support@example.com",
    )
    tenant_ct = ContentType.objects.get_for_model(tenant)
    ContactAssignment.objects.create(
        contact=contact,
        object_type=tenant_ct,
        object_id=tenant.pk,
        role=contact_role_secondary,
        priority="primary",
    )
    return contact


@pytest.fixture
def tenant_secondary():
    """Create a secondary tenant."""
    from tenancy.models import Tenant

    return Tenant.objects.create(
        name="Secondary Tenant",
        slug="secondary-tenant",
    )


@pytest.fixture
def contact_secondary_tenant(tenant_secondary, contact_role):
    """Create a contact assigned to the secondary tenant."""
    from tenancy.models import Contact, ContactAssignment

    contact = Contact.objects.create(
        name="Secondary Tenant Contact",
        email="secondary-tenant@example.com",
    )
    tenant_ct = ContentType.objects.get_for_model(tenant_secondary)
    ContactAssignment.objects.create(
        contact=contact,
        object_type=tenant_ct,
        object_id=tenant_secondary.pk,
        role=contact_role,
        priority="primary",
    )
    return contact


@pytest.fixture
def circuit(provider, tenant):
    """Create a test circuit with tenant."""
    from circuits.models import Circuit, CircuitType

    circuit_type = CircuitType.objects.create(
        name="Test Circuit Type",
        slug="test-circuit-type",
    )
    return Circuit.objects.create(
        cid="TEST-CIRCUIT-001",
        provider=provider,
        type=circuit_type,
        tenant=tenant,
    )


@pytest.fixture
def circuit_secondary(provider, tenant_secondary):
    """Create a circuit with secondary tenant."""
    from circuits.models import Circuit, CircuitType

    circuit_type, _ = CircuitType.objects.get_or_create(
        name="Test Circuit Type",
        slug="test-circuit-type",
    )
    return Circuit.objects.create(
        cid="TEST-CIRCUIT-002",
        provider=provider,
        type=circuit_type,
        tenant=tenant_secondary,
    )


@pytest.fixture
def circuit_no_tenant(provider):
    """Create a circuit without tenant."""
    from circuits.models import Circuit, CircuitType

    circuit_type, _ = CircuitType.objects.get_or_create(
        name="Test Circuit Type",
        slug="test-circuit-type",
    )
    return Circuit.objects.create(
        cid="TEST-CIRCUIT-003",
        provider=provider,
        type=circuit_type,
        tenant=None,
    )


@pytest.fixture
def impact(maintenance, circuit):
    """Create an impact linking maintenance to circuit."""
    event_ct = ContentType.objects.get_for_model(maintenance)
    target_ct = ContentType.objects.get_for_model(circuit)
    return Impact.objects.create(
        event_content_type=event_ct,
        event_object_id=maintenance.pk,
        target_content_type=target_ct,
        target_object_id=circuit.pk,
        impact="OUTAGE",
    )


@pytest.fixture
def impact_secondary(maintenance, circuit_secondary):
    """Create an impact linking maintenance to secondary circuit."""
    event_ct = ContentType.objects.get_for_model(maintenance)
    target_ct = ContentType.objects.get_for_model(circuit_secondary)
    return Impact.objects.create(
        event_content_type=event_ct,
        event_object_id=maintenance.pk,
        target_content_type=target_ct,
        target_object_id=circuit_secondary.pk,
        impact="DEGRADED",
    )


@pytest.fixture
def impact_no_tenant(maintenance, circuit_no_tenant):
    """Create an impact for a circuit without tenant."""
    event_ct = ContentType.objects.get_for_model(maintenance)
    target_ct = ContentType.objects.get_for_model(circuit_no_tenant)
    return Impact.objects.create(
        event_content_type=event_ct,
        event_object_id=maintenance.pk,
        target_content_type=target_ct,
        target_object_id=circuit_no_tenant.pk,
        impact="NO-IMPACT",
    )


@pytest.fixture
def template_with_roles(contact_role):
    """Create a template with contact role filtering."""
    template = NotificationTemplate.objects.create(
        name="Test Template",
        slug="test-template",
        event_type=MessageEventTypeChoices.MAINTENANCE,
        granularity=MessageGranularityChoices.PER_TENANT,
        subject_template="Test Subject",
        body_template="Test Body",
        contact_priorities=["primary", "secondary"],
    )
    template.contact_roles.add(contact_role)
    return template


@pytest.fixture
def template_all_priorities(contact_role):
    """Create a template that accepts all priorities."""
    template = NotificationTemplate.objects.create(
        name="All Priorities Template",
        slug="all-priorities-template",
        event_type=MessageEventTypeChoices.MAINTENANCE,
        granularity=MessageGranularityChoices.PER_TENANT,
        subject_template="Test Subject",
        body_template="Test Body",
        contact_priorities=[],  # Empty = all priorities except inactive
    )
    template.contact_roles.add(contact_role)
    return template


@pytest.fixture
def template_primary_only(contact_role):
    """Create a template that only accepts primary contacts."""
    template = NotificationTemplate.objects.create(
        name="Primary Only Template",
        slug="primary-only-template",
        event_type=MessageEventTypeChoices.MAINTENANCE,
        granularity=MessageGranularityChoices.PER_EVENT,
        subject_template="Test Subject",
        body_template="Test Body",
        contact_priorities=["primary"],
    )
    template.contact_roles.add(contact_role)
    return template


@pytest.mark.django_db
class TestRecipientDiscoveryService:
    """Tests for RecipientDiscoveryService class."""

    def test_init_with_template(self, template_with_roles, contact_role):
        """Test service initialization with template."""
        service = RecipientDiscoveryService(template_with_roles)
        assert service.template == template_with_roles
        assert contact_role in service.roles
        assert service.priorities == ["primary", "secondary"]

    def test_discover_for_tenant(self, template_with_roles, tenant, contact_with_assignment):
        """Test discovering contacts for a specific tenant."""
        service = RecipientDiscoveryService(template_with_roles)
        contacts = service.discover_for_tenant(tenant)
        assert contact_with_assignment in contacts

    def test_discover_for_tenant_filters_by_role(
        self, template_with_roles, tenant, contact_with_assignment, contact_different_role
    ):
        """Test that role filtering works correctly."""
        service = RecipientDiscoveryService(template_with_roles)
        contacts = service.discover_for_tenant(tenant)
        # Should include contact with matching role
        assert contact_with_assignment in contacts
        # Should NOT include contact with different role
        assert contact_different_role not in contacts

    def test_discover_for_tenant_filters_by_priority(
        self, template_primary_only, tenant, contact_with_assignment, contact_secondary
    ):
        """Test that priority filtering works correctly."""
        service = RecipientDiscoveryService(template_primary_only)
        contacts = service.discover_for_tenant(tenant)
        # Should include primary contact
        assert contact_with_assignment in contacts
        # Should NOT include secondary contact
        assert contact_secondary not in contacts

    def test_discover_for_tenant_excludes_inactive(
        self, template_all_priorities, tenant, contact_with_assignment, contact_inactive
    ):
        """Test that inactive contacts are always excluded."""
        service = RecipientDiscoveryService(template_all_priorities)
        contacts = service.discover_for_tenant(tenant)
        # Should include active contact
        assert contact_with_assignment in contacts
        # Should NOT include inactive contact
        assert contact_inactive not in contacts

    def test_discover_for_tenant_returns_empty_for_none(self, template_with_roles):
        """Test that None tenant returns empty list."""
        service = RecipientDiscoveryService(template_with_roles)
        contacts = service.discover_for_tenant(None)
        assert contacts == []


@pytest.mark.django_db
class TestRecipientDiscoveryPerEvent:
    """Tests for per-event granularity."""

    def test_per_event_returns_flat_list(
        self,
        template_with_roles,
        maintenance,
        impact,
        impact_secondary,
        contact_with_assignment,
        contact_secondary_tenant,
    ):
        """Test that per_event returns a flat list of all contacts."""
        template_with_roles.granularity = MessageGranularityChoices.PER_EVENT
        template_with_roles.save()

        service = RecipientDiscoveryService(template_with_roles)
        result = service.discover_for_event(maintenance)

        assert isinstance(result, list)
        assert contact_with_assignment in result
        assert contact_secondary_tenant in result

    def test_per_event_deduplicates_contacts(self, template_with_roles, maintenance, impact, contact_with_assignment):
        """Test that contacts are deduplicated."""
        template_with_roles.granularity = MessageGranularityChoices.PER_EVENT
        template_with_roles.save()

        service = RecipientDiscoveryService(template_with_roles)
        result = service.discover_for_event(maintenance)

        # Should only appear once even if multiple impacts point to same tenant
        assert result.count(contact_with_assignment) == 1

    def test_per_event_empty_for_no_impacts(self, template_with_roles, maintenance):
        """Test that empty list is returned when no impacts exist."""
        template_with_roles.granularity = MessageGranularityChoices.PER_EVENT
        template_with_roles.save()

        service = RecipientDiscoveryService(template_with_roles)
        result = service.discover_for_event(maintenance)

        assert result == []


@pytest.mark.django_db
class TestRecipientDiscoveryPerTenant:
    """Tests for per-tenant granularity."""

    def test_per_tenant_returns_dict(
        self,
        template_with_roles,
        maintenance,
        impact,
        impact_secondary,
        tenant,
        tenant_secondary,
        contact_with_assignment,
        contact_secondary_tenant,
    ):
        """Test that per_tenant returns a dict keyed by tenant."""
        template_with_roles.granularity = MessageGranularityChoices.PER_TENANT
        template_with_roles.save()

        service = RecipientDiscoveryService(template_with_roles)
        result = service.discover_for_event(maintenance)

        assert isinstance(result, dict)
        assert tenant in result
        assert tenant_secondary in result
        assert contact_with_assignment in result[tenant]
        assert contact_secondary_tenant in result[tenant_secondary]

    def test_per_tenant_groups_by_tenant(
        self,
        template_with_roles,
        maintenance,
        impact,
        tenant,
        contact_with_assignment,
        contact_secondary,
    ):
        """Test that contacts are grouped by their tenant."""
        template_with_roles.granularity = MessageGranularityChoices.PER_TENANT
        template_with_roles.save()

        service = RecipientDiscoveryService(template_with_roles)
        result = service.discover_for_event(maintenance)

        assert tenant in result
        # Both contacts assigned to same tenant should appear
        assert contact_with_assignment in result[tenant]
        assert contact_secondary in result[tenant]


@pytest.mark.django_db
class TestRecipientDiscoveryPerImpact:
    """Tests for per-impact granularity."""

    def test_per_impact_returns_dict_keyed_by_impact(
        self,
        template_with_roles,
        maintenance,
        impact,
        impact_secondary,
        contact_with_assignment,
        contact_secondary_tenant,
    ):
        """Test that per_impact returns a dict keyed by impact."""
        template_with_roles.granularity = MessageGranularityChoices.PER_IMPACT
        template_with_roles.save()

        service = RecipientDiscoveryService(template_with_roles)
        result = service.discover_for_event(maintenance)

        assert isinstance(result, dict)
        assert impact in result
        assert impact_secondary in result
        assert contact_with_assignment in result[impact]
        assert contact_secondary_tenant in result[impact_secondary]

    def test_per_impact_includes_impacts_without_tenant(self, template_with_roles, maintenance, impact_no_tenant):
        """Test that impacts without tenant return empty list."""
        template_with_roles.granularity = MessageGranularityChoices.PER_IMPACT
        template_with_roles.save()

        service = RecipientDiscoveryService(template_with_roles)
        result = service.discover_for_event(maintenance)

        assert impact_no_tenant in result
        assert result[impact_no_tenant] == []


@pytest.mark.django_db
class TestGranularityOverride:
    """Tests for granularity override functionality."""

    def test_granularity_override_works(
        self,
        template_with_roles,
        maintenance,
        impact,
        tenant,
        contact_with_assignment,
    ):
        """Test that granularity can be overridden at runtime."""
        # Template defaults to PER_TENANT
        template_with_roles.granularity = MessageGranularityChoices.PER_TENANT
        template_with_roles.save()

        service = RecipientDiscoveryService(template_with_roles)

        # Override to PER_EVENT
        result = service.discover_for_event(maintenance, granularity=MessageGranularityChoices.PER_EVENT)
        assert isinstance(result, list)

        # Override to PER_IMPACT
        result = service.discover_for_event(maintenance, granularity=MessageGranularityChoices.PER_IMPACT)
        assert isinstance(result, dict)
        assert impact in result


@pytest.mark.django_db
class TestDiscoverRecipientsFunction:
    """Tests for the discover_recipients convenience function."""

    def test_discover_recipients_with_event(self, template_with_roles, maintenance, impact, contact_with_assignment):
        """Test discover_recipients with an event."""
        result = discover_recipients(template_with_roles, event=maintenance)
        assert isinstance(result, dict)
        # Should use template's default granularity (PER_TENANT)

    def test_discover_recipients_with_tenant(self, template_with_roles, tenant, contact_with_assignment):
        """Test discover_recipients with a tenant directly."""
        result = discover_recipients(template_with_roles, tenant=tenant)
        assert contact_with_assignment in result

    def test_discover_recipients_with_granularity_override(
        self, template_with_roles, maintenance, impact, contact_with_assignment
    ):
        """Test discover_recipients with granularity override."""
        result = discover_recipients(
            template_with_roles,
            event=maintenance,
            granularity=MessageGranularityChoices.PER_EVENT,
        )
        assert isinstance(result, list)

    def test_discover_recipients_returns_empty_without_event_or_tenant(self, template_with_roles):
        """Test that discover_recipients returns empty list without event or tenant."""
        result = discover_recipients(template_with_roles)
        assert result == []


@pytest.mark.django_db
class TestTenantResolutionFromImpacts:
    """Tests for tenant resolution from impact targets."""

    def test_tenant_from_circuit_impact(
        self, template_with_roles, maintenance, impact, tenant, contact_with_assignment
    ):
        """Test that tenant is correctly resolved from circuit impact."""
        service = RecipientDiscoveryService(template_with_roles)
        result = service.discover_for_event(maintenance)

        # Tenant should be found via circuit.tenant
        assert tenant in result

    def test_no_tenant_returns_empty_contacts(self, template_with_roles, maintenance, impact_no_tenant):
        """Test that impacts without tenant return no contacts."""
        template_with_roles.granularity = MessageGranularityChoices.PER_EVENT
        template_with_roles.save()

        service = RecipientDiscoveryService(template_with_roles)
        result = service.discover_for_event(maintenance)

        # Should return empty since circuit has no tenant
        assert result == []
