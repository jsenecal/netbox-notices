"""
Tests for the Impact.sites / Impact.locations resolver registry, cache
refresh, signal-driven invalidation, and site-scoped filtering on
Maintenance / Outage / Impact filtersets.
"""

from datetime import timedelta

import pytest
from circuits.models import Circuit, CircuitTermination, CircuitType, Provider
from dcim.models import (
    Device,
    DeviceRole,
    DeviceType,
    Location,
    Manufacturer,
    PowerFeed,
    PowerPanel,
    Site,
)
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone

from notices.filtersets import (
    ImpactFilterSet,
    MaintenanceFilterSet,
    OutageFilterSet,
)
from notices.models import Impact, Maintenance, Outage
from notices.resolvers import (
    SITE_RESOLVERS,
    register_site_resolver,
    resolve_locations_for,
    resolve_sites_for,
    unregister_resolvers,
)


@pytest.mark.django_db
class TestResolverRegistry(TestCase):
    """The registry itself: registration, lookup, dedupe, double-register guard."""

    def test_default_resolvers_registered(self):
        for ct in (
            "circuits.circuit",
            "dcim.device",
            "dcim.location",
            "dcim.powerfeed",
            "dcim.powerpanel",
            "dcim.site",
        ):
            self.assertIn(ct, SITE_RESOLVERS, f"missing default site resolver for {ct}")

    def test_double_registration_raises(self):
        with self.assertRaises(ValueError):

            @register_site_resolver("dcim.site")
            def _another(target):  # pragma: no cover
                return ()

    def test_resolve_returns_set_with_falsy_stripped(self):
        # Resolver that returns garbage (None and 0) — caller should filter.
        unregister_resolvers("test.fake")
        try:
            SITE_RESOLVERS["test.fake"] = lambda t: (0, None, 7, 7)
            ct = ContentType(app_label="test", model="fake")
            result = resolve_sites_for(ct, object())
            self.assertEqual(result, {7})
        finally:
            unregister_resolvers("test.fake")

    def test_resolve_with_no_resolver_returns_empty(self):
        ct = ContentType(app_label="nonexistent", model="thing")
        self.assertEqual(resolve_sites_for(ct, object()), set())
        self.assertEqual(resolve_locations_for(ct, object()), set())

    def test_resolve_handles_none_target(self):
        ct = ContentType.objects.get(app_label="dcim", model="device")
        self.assertEqual(resolve_sites_for(ct, None), set())

    def test_location_and_powerpanel_have_no_w001(self):
        from notices.checks import check_resolver_coverage

        with self.settings(PLUGINS_CONFIG={"notices": {"allowed_content_types": ["dcim.Location", "dcim.PowerPanel"]}}):
            self.assertEqual(check_resolver_coverage(None), [])


@pytest.mark.django_db
class TestDefaultResolvers(TestCase):
    """The built-in resolvers, each tested against real NetBox objects."""

    @classmethod
    def setUpTestData(cls):
        cls.site_a = Site.objects.create(name="A", slug="a")
        cls.site_b = Site.objects.create(name="B", slug="b")
        cls.location_a = Location.objects.create(name="LocA", slug="loc-a", site=cls.site_a)

        cls.role = DeviceRole.objects.create(name="r", slug="r")
        cls.mfr = Manufacturer.objects.create(name="m", slug="m")
        cls.dt = DeviceType.objects.create(manufacturer=cls.mfr, model="M", slug="m")

    def test_site_resolver(self):
        ct = ContentType.objects.get_for_model(Site)
        self.assertEqual(resolve_sites_for(ct, self.site_a), {self.site_a.pk})
        self.assertEqual(resolve_locations_for(ct, self.site_a), set())

    def test_device_resolver(self):
        device = Device.objects.create(
            name="d1", site=self.site_a, location=self.location_a, role=self.role, device_type=self.dt
        )
        ct = ContentType.objects.get_for_model(Device)
        self.assertEqual(resolve_sites_for(ct, device), {self.site_a.pk})
        self.assertEqual(resolve_locations_for(ct, device), {self.location_a.pk})

    def test_device_resolver_no_location(self):
        device = Device.objects.create(name="d2", site=self.site_a, role=self.role, device_type=self.dt)
        ct = ContentType.objects.get_for_model(Device)
        self.assertEqual(resolve_locations_for(ct, device), set())

    def test_powerfeed_resolver(self):
        panel = PowerPanel.objects.create(name="p", site=self.site_a, location=self.location_a)
        feed = PowerFeed.objects.create(name="f", power_panel=panel)
        ct = ContentType.objects.get_for_model(PowerFeed)
        self.assertEqual(resolve_sites_for(ct, feed), {self.site_a.pk})
        self.assertEqual(resolve_locations_for(ct, feed), {self.location_a.pk})

    def test_location_resolver(self):
        ct = ContentType.objects.get_for_model(Location)
        self.assertEqual(resolve_sites_for(ct, self.location_a), {self.site_a.pk})
        self.assertEqual(resolve_locations_for(ct, self.location_a), {self.location_a.pk})

    def test_powerpanel_resolver(self):
        ct = ContentType.objects.get_for_model(PowerPanel)
        panel = PowerPanel.objects.create(name="p-loc", site=self.site_a, location=self.location_a)
        self.assertEqual(resolve_sites_for(ct, panel), {self.site_a.pk})
        self.assertEqual(resolve_locations_for(ct, panel), {self.location_a.pk})

    def test_powerpanel_resolver_no_location(self):
        ct = ContentType.objects.get_for_model(PowerPanel)
        panel = PowerPanel.objects.create(name="p-noloc", site=self.site_a)
        self.assertEqual(resolve_sites_for(ct, panel), {self.site_a.pk})
        self.assertEqual(resolve_locations_for(ct, panel), set())

    def test_circuit_resolver_two_sites(self):
        provider = Provider.objects.create(name="P", slug="p")
        ctype = CircuitType.objects.create(name="t", slug="t")
        circuit = Circuit.objects.create(cid="C1", provider=provider, type=ctype)
        # Generic terminations land their site in the denormalized _site_id.
        site_ct = ContentType.objects.get_for_model(Site)
        CircuitTermination.objects.create(
            circuit=circuit,
            term_side="A",
            termination_type=site_ct,
            termination_id=self.site_a.pk,
        )
        CircuitTermination.objects.create(
            circuit=circuit,
            term_side="Z",
            termination_type=site_ct,
            termination_id=self.site_b.pk,
        )
        circuit.refresh_from_db()
        ct = ContentType.objects.get_for_model(Circuit)
        self.assertEqual(resolve_sites_for(ct, circuit), {self.site_a.pk, self.site_b.pk})


@pytest.mark.django_db
class TestImpactRefreshAndSignals(TestCase):
    """Cache lifecycle: created on save, kept fresh by signals on upstream changes."""

    @classmethod
    def setUpTestData(cls):
        cls.site_a = Site.objects.create(name="A", slug="a-sig")
        cls.site_b = Site.objects.create(name="B", slug="b-sig")
        cls.role = DeviceRole.objects.create(name="r-sig", slug="r-sig")
        cls.mfr = Manufacturer.objects.create(name="m-sig", slug="m-sig")
        cls.dt = DeviceType.objects.create(manufacturer=cls.mfr, model="M-sig", slug="m-sig")
        cls.provider = Provider.objects.create(name="prov-sig", slug="prov-sig")
        now = timezone.now()
        cls.maintenance = Maintenance.objects.create(
            name="MAINT-SIG",
            summary="x",
            provider=cls.provider,
            status="CONFIRMED",
            start=now,
            end=now + timedelta(hours=1),
        )

    def _make_impact(self, target):
        return Impact.objects.create(event=self.maintenance, target=target, impact="OUTAGE")

    def _cached(self, impact):
        """The impact's cached (site pks, location pks), re-read from the database."""
        impact.refresh_from_db()
        return set(impact.sites.values_list("pk", flat=True)), set(impact.locations.values_list("pk", flat=True))

    def test_save_populates_sites(self):
        device = Device.objects.create(name="d-s", site=self.site_a, role=self.role, device_type=self.dt)
        impact = self._make_impact(device)
        self.assertEqual(self._cached(impact), ({self.site_a.pk}, set()))

    def test_device_site_change_refreshes_cache(self):
        device = Device.objects.create(name="d-mv", site=self.site_a, role=self.role, device_type=self.dt)
        impact = self._make_impact(device)
        self.assertEqual(self._cached(impact), ({self.site_a.pk}, set()))

        device.site = self.site_b
        device.save()

        self.assertEqual(self._cached(impact), ({self.site_b.pk}, set()))

    def test_powerpanel_move_refreshes_panel_and_feed_impacts(self):
        loc_a = Location.objects.create(name="L-pa", slug="l-pa", site=self.site_a)
        loc_b = Location.objects.create(name="L-pb", slug="l-pb", site=self.site_b)
        panel = PowerPanel.objects.create(name="pp-mv", site=self.site_a, location=loc_a)
        feed = PowerFeed.objects.create(name="ff-mv", power_panel=panel)
        panel_impact = self._make_impact(panel)
        feed_impact = self._make_impact(feed)
        self.assertEqual(self._cached(panel_impact), ({self.site_a.pk}, {loc_a.pk}))

        panel.site = self.site_b
        panel.location = loc_b
        panel.save()

        self.assertEqual(self._cached(panel_impact), ({self.site_b.pk}, {loc_b.pk}))
        self.assertEqual(self._cached(feed_impact), ({self.site_b.pk}, {loc_b.pk}))

    def test_location_site_change_refreshes_cache(self):
        location = Location.objects.create(name="L-mv", slug="l-mv", site=self.site_a)
        impact = self._make_impact(location)
        self.assertEqual(self._cached(impact), ({self.site_a.pk}, {location.pk}))

        location.site = self.site_b
        location.save()

        self.assertEqual(self._cached(impact), ({self.site_b.pk}, {location.pk}))

    def test_circuit_termination_change_refreshes_circuit_impact(self):
        ctype = CircuitType.objects.create(name="t-sig", slug="t-sig")
        circuit = Circuit.objects.create(cid="C-SIG", provider=self.provider, type=ctype)
        site_ct = ContentType.objects.get_for_model(Site)
        term = CircuitTermination.objects.create(
            circuit=circuit, term_side="A", termination_type=site_ct, termination_id=self.site_a.pk
        )
        circuit.refresh_from_db()
        impact = self._make_impact(circuit)
        self.assertEqual(self._cached(impact), ({self.site_a.pk}, set()))

        term.termination_id = self.site_b.pk
        term.save()

        self.assertEqual(self._cached(impact), ({self.site_b.pk}, set()))

    def test_refresh_sites_noop_on_unsaved_instance(self):
        # Should not raise — just silently no-op.
        impact = Impact(event=self.maintenance, target=self.site_a, impact="OUTAGE")
        impact.refresh_sites()


@pytest.mark.django_db
class TestSiteScopedFilters(TestCase):
    """Site/region/location filters on Maintenance, Outage, and Impact."""

    @classmethod
    def setUpTestData(cls):
        cls.site_a = Site.objects.create(name="A", slug="a-flt")
        cls.site_b = Site.objects.create(name="B", slug="b-flt")
        cls.role = DeviceRole.objects.create(name="r-flt", slug="r-flt")
        cls.mfr = Manufacturer.objects.create(name="m-flt", slug="m-flt")
        cls.dt = DeviceType.objects.create(manufacturer=cls.mfr, model="M-flt", slug="m-flt")
        cls.provider = Provider.objects.create(name="prov-flt", slug="prov-flt")

        now = timezone.now()
        cls.m_a = Maintenance.objects.create(
            name="M-A",
            summary="x",
            provider=cls.provider,
            status="CONFIRMED",
            start=now,
            end=now + timedelta(hours=1),
        )
        cls.m_b = Maintenance.objects.create(
            name="M-B",
            summary="x",
            provider=cls.provider,
            status="CONFIRMED",
            start=now,
            end=now + timedelta(hours=1),
        )
        cls.o_a = Outage.objects.create(
            name="O-A",
            summary="x",
            provider=cls.provider,
            status="OPEN",
            start=now,
        )

        device_a = Device.objects.create(name="da", site=cls.site_a, role=cls.role, device_type=cls.dt)
        device_b = Device.objects.create(name="db", site=cls.site_b, role=cls.role, device_type=cls.dt)
        Impact.objects.create(event=cls.m_a, target=device_a, impact="OUTAGE")
        Impact.objects.create(event=cls.m_b, target=device_b, impact="OUTAGE")
        Impact.objects.create(event=cls.o_a, target=device_a, impact="OUTAGE")

    def test_maintenance_filter_by_site(self):
        qs = MaintenanceFilterSet({"site_id": [self.site_a.pk]}, queryset=Maintenance.objects.all()).qs
        self.assertEqual({m.pk for m in qs}, {self.m_a.pk})

    def test_outage_filter_by_site(self):
        qs = OutageFilterSet({"site_id": [self.site_a.pk]}, queryset=Outage.objects.all()).qs
        self.assertEqual({o.pk for o in qs}, {self.o_a.pk})

    def test_impact_filter_by_site(self):
        qs = ImpactFilterSet({"site_id": [self.site_b.pk]}, queryset=Impact.objects.all()).qs
        self.assertEqual([i.target_object_id for i in qs], [Device.objects.get(name="db").pk])
