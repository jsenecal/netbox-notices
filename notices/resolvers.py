"""
Site/Location resolver registry for Impact targets.

The :class:`Impact <notices.models.Impact>` model uses a ``GenericForeignKey``
to point at any allowed NetBox object (Circuit, Device, PowerFeed, Site, plus
any operator-added types via the ``allowed_content_types`` plugin setting).
For filtering and aggregation ("which maintenances affect anything in the
sites I'm responsible for?"), Impact also caches the resolved Site and
Location set on M2M fields. This module is the *source of truth* the cache is
populated from.

Two registries live here:

- ``SITE_RESOLVERS``     — maps ``"app_label.modelname"`` → callable returning
  an iterable of ``Site`` PKs for a given target instance.
- ``LOCATION_RESOLVERS`` — same shape, for ``Location`` PKs.

Resolvers are registered with the :func:`register_site_resolver` and
:func:`register_location_resolver` decorators. The four content types in
``DEFAULT_ALLOWED_CONTENT_TYPES`` ship with built-in resolvers below.

Operator extension
------------------

If you add a content type to ``PLUGINS_CONFIG['notices']['allowed_content_types']``,
you must register a resolver for it — otherwise its impacts will silently
have empty ``sites``/``locations`` and won't appear in site-scoped filters.

You also need to wire signals (see :mod:`notices.signals`) so cache entries
stay fresh when the target's site/location changes. The plugin emits a
system check at startup that warns when an allowed content type has no
resolver registered.

Example::

    # In your plugin's apps.py ready() hook, or any module loaded by it:
    from notices.resolvers import register_site_resolver, register_location_resolver

    @register_site_resolver("virtualization.virtualmachine")
    def _vm_sites(vm):
        # Return an iterable of Site PKs for this target.
        # Empty iterable / None / missing attrs are all fine — the caller
        # dedupes and filters falsy values.
        if vm.site_id:
            return (vm.site_id,)
        if vm.cluster_id and vm.cluster.site_id:
            return (vm.cluster.site_id,)
        return ()

    @register_location_resolver("virtualization.virtualmachine")
    def _vm_locations(vm):
        return (vm.location_id,) if vm.location_id else ()
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from django.contrib.contenttypes.models import ContentType
from django.db.models import Model

# Type alias: a resolver takes the target instance and returns an iterable of
# Site/Location PKs. ``None`` and ``0`` PKs are filtered out by the caller, so
# resolvers can return e.g. ``(target.site_id,)`` without checking nullability.
Resolver = Callable[[Model], Iterable[int | None] | None]

SITE_RESOLVERS: dict[str, Resolver] = {}
LOCATION_RESOLVERS: dict[str, Resolver] = {}


def _normalize_key(content_type_string: str) -> str:
    """Normalize ``"app_label.ModelName"`` to lowercase form for lookup."""
    return content_type_string.lower()


def register_site_resolver(content_type_string: str) -> Callable[[Resolver], Resolver]:
    """
    Decorator to register a Site resolver for a given content type.

    Parameters
    ----------
    content_type_string
        Dotted ``"app_label.modelname"`` identifier. Case-insensitive — internally
        normalized to lowercase before lookup. Must match a content type that
        appears in ``PLUGINS_CONFIG['notices']['allowed_content_types']`` (or in
        the plugin default), otherwise the resolver will never be called.

    The decorated function receives the target instance and must return an
    iterable of ``Site`` PKs (``int``). Returning ``None``, an empty iterable,
    or an iterable containing ``None``/``0`` is all valid — the caller dedupes
    and drops falsy values. This means the typical implementation can just be::

        @register_site_resolver("dcim.device")
        def _device_sites(device):
            return (device.site_id,)

    Performance
    -----------

    Resolvers are called from :meth:`Impact.refresh_sites` whenever:

    1. An ``Impact`` is saved (``post_save`` signal).
    2. A *target's* site/location changes (signals on ``Device``, ``PowerFeed``,
       ``Circuit``, ``CircuitTermination``, etc. — see :mod:`notices.signals`).
    3. Operator runs ``manage.py refresh_impact_sites`` to rebuild the cache.

    Prefer ``*_id`` attributes (``device.site_id``) over the related object
    (``device.site.pk``) — the former is a single attribute lookup, the latter
    triggers a database query.

    Raises
    ------
    ValueError
        If a resolver is already registered for ``content_type_string``.
        Re-registration is intentionally rejected to prevent silent overrides
        from misordered imports.

    Examples
    --------

    Single-site target::

        @register_site_resolver("dcim.device")
        def _device_sites(device):
            return (device.site_id,)

    Multi-site target (a Circuit can span two sites)::

        @register_site_resolver("circuits.circuit")
        def _circuit_sites(circuit):
            pks = []
            for term in (circuit.termination_a, circuit.termination_z):
                if term is not None:
                    pks.append(term._site_id)  # denormalized in NetBox 4.5+
            return pks

    Indirect relationship (PowerFeed → PowerPanel → Site)::

        @register_site_resolver("dcim.powerfeed")
        def _powerfeed_sites(feed):
            if feed.power_panel_id is None:
                return ()
            # power_panel is a single FK — accessing it costs one query, but
            # site_id on PowerPanel is denormalized so no further round-trip.
            return (feed.power_panel.site_id,)
    """

    key = _normalize_key(content_type_string)

    def decorator(fn: Resolver) -> Resolver:
        if key in SITE_RESOLVERS:
            raise ValueError(
                f"A site resolver is already registered for {content_type_string!r}. "
                "Refusing to silently override — unregister it first or use a different key."
            )
        SITE_RESOLVERS[key] = fn
        return fn

    return decorator


def register_location_resolver(content_type_string: str) -> Callable[[Resolver], Resolver]:
    """
    Decorator to register a Location resolver for a given content type.

    Mirrors :func:`register_site_resolver` exactly — same calling convention,
    same return-type expectations, same dedupe behavior. Locations are
    optional in NetBox; many targets won't have one. Returning an empty
    iterable is the right answer when the target doesn't model a location.

    Examples
    --------

    ::

        @register_location_resolver("dcim.device")
        def _device_locations(device):
            return (device.location_id,) if device.location_id else ()
    """

    key = _normalize_key(content_type_string)

    def decorator(fn: Resolver) -> Resolver:
        if key in LOCATION_RESOLVERS:
            raise ValueError(
                f"A location resolver is already registered for {content_type_string!r}. "
                "Refusing to silently override — unregister it first or use a different key."
            )
        LOCATION_RESOLVERS[key] = fn
        return fn

    return decorator


def unregister_resolvers(content_type_string: str) -> None:
    """
    Remove both site and location resolvers for ``content_type_string``.

    Primarily useful in tests. Silently no-ops for unknown keys.
    """
    key = _normalize_key(content_type_string)
    SITE_RESOLVERS.pop(key, None)
    LOCATION_RESOLVERS.pop(key, None)


def _resolve(registry: dict[str, Resolver], content_type: ContentType, target: Model | None) -> set[int]:
    """Run the registered resolver and return a deduped set of non-falsy PKs."""
    if target is None or content_type is None:
        return set()
    key = f"{content_type.app_label}.{content_type.model}".lower()
    resolver = registry.get(key)
    if resolver is None:
        return set()
    pks = resolver(target) or ()
    return {pk for pk in pks if pk}


def resolve_sites_for(content_type: ContentType, target: Model | None) -> set[int]:
    """Return the set of Site PKs associated with ``target`` (deduped, falsy-stripped)."""
    return _resolve(SITE_RESOLVERS, content_type, target)


def resolve_locations_for(content_type: ContentType, target: Model | None) -> set[int]:
    """Return the set of Location PKs associated with ``target`` (deduped, falsy-stripped)."""
    return _resolve(LOCATION_RESOLVERS, content_type, target)


# ---------------------------------------------------------------------------
# Default resolvers for DEFAULT_ALLOWED_CONTENT_TYPES.
#
# These are the four content types this plugin allows out of the box. Adding
# a new entry to ``allowed_content_types`` does NOT automatically get a
# resolver — operators must register their own (see module docstring).
# ---------------------------------------------------------------------------


@register_site_resolver("dcim.site")
def _site_sites(site):
    """A Site IS its own site."""
    return (site.pk,)


@register_location_resolver("dcim.site")
def _site_locations(site):
    """Sites have no location of their own (locations live underneath sites)."""
    return ()


@register_site_resolver("dcim.device")
def _device_sites(device):
    return (device.site_id,)


@register_location_resolver("dcim.device")
def _device_locations(device):
    return (device.location_id,) if device.location_id else ()


@register_site_resolver("dcim.powerfeed")
def _powerfeed_sites(feed):
    if feed.power_panel_id is None:
        return ()
    return (feed.power_panel.site_id,)


@register_location_resolver("dcim.powerfeed")
def _powerfeed_locations(feed):
    if feed.power_panel_id is None:
        return ()
    panel = feed.power_panel
    return (panel.location_id,) if panel.location_id else ()


@register_site_resolver("circuits.circuit")
def _circuit_sites(circuit):
    """
    A Circuit can span two sites, one per termination. NetBox 4.5+ stores
    the denormalized site/location on CircuitTermination as ``_site_id`` /
    ``_location_id``, regardless of whether the termination resolves to a
    Site, Location, Region, SiteGroup, or ProviderNetwork — so we use those
    rather than walking the generic ``termination`` FK ourselves.
    """
    pks = []
    for term in (circuit.termination_a, circuit.termination_z):
        if term is not None and getattr(term, "_site_id", None):
            pks.append(term._site_id)
    return pks


@register_location_resolver("circuits.circuit")
def _circuit_locations(circuit):
    pks = []
    for term in (circuit.termination_a, circuit.termination_z):
        if term is not None and getattr(term, "_location_id", None):
            pks.append(term._location_id)
    return pks
