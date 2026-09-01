# Site and Location Resolvers

`Impact` points at its target with a `GenericForeignKey`, which SQL cannot join against. To make "show me every maintenance affecting anything in site X" a real query, `Impact` caches the target's site and location membership on two M2M fields, `sites` and `locations`. The resolver registry in `notices/resolvers.py` is where those values come from.

A resolver is a small function that answers one question for one content type: given an instance of this model, which `Site` (or `Location`) primary keys does it belong to?

## When you need one

You need to register a resolver whenever you add a content type to `allowed_content_types`:

```python
PLUGINS_CONFIG = {
    "notices": {
        "allowed_content_types": [
            "circuits.Circuit",
            "dcim.Device",
            "dcim.PowerFeed",
            "dcim.Site",
            "virtualization.VirtualMachine",  # needs a resolver
        ],
    },
}
```

Without one, impacts targeting that type still save and still display. They just have empty `sites` and `locations`, so they never appear in the `site_id`, `region_id`, `site_group_id` or `location_id` filters. Nothing errors; the rows are simply invisible to site-scoped queries.

The plugin emits a startup warning for this case. `notices.checks.check_resolver_coverage` compares `allowed_content_types` against the registered site resolvers and raises `notices.W001` for each type with no resolver:

```
System check identified some issues:

WARNINGS:
?: (notices.W001) No site resolver registered for allowed content type
'virtualization.VirtualMachine'.
    HINT: Impacts targeting this type will have empty Impact.sites and won't
    appear in site/region/location filters. Register one via
    notices.resolvers.register_site_resolver, and add a matching signal handler
    in notices.signals so the cache stays fresh when the target's site changes.
```

The check covers site resolvers only. A missing location resolver is silent, which is intentional: plenty of models have no meaningful location.

## Built-in resolvers

The four types in `DEFAULT_ALLOWED_CONTENT_TYPES` ship with resolvers.

| Content type | Sites | Locations |
|---|---|---|
| `dcim.site` | The site itself | None. Locations live underneath sites. |
| `dcim.device` | `device.site_id` | `device.location_id` if set |
| `dcim.powerfeed` | `feed.power_panel.site_id` | The panel's `location_id` if set |
| `circuits.circuit` | `_site_id` of each termination | `_location_id` of each termination |

The circuit resolver is the one worth reading. A circuit can span two sites, one per termination, and a termination may resolve to a Site, Location, Region, SiteGroup or ProviderNetwork. NetBox 4.5 and later denormalise the result onto `CircuitTermination._site_id` and `._location_id`, so the resolver reads those rather than walking the generic termination FK itself.

## Registering a resolver

Use the decorators. The key is a dotted `app_label.modelname` string, matched case-insensitively.

```python
from notices.resolvers import register_location_resolver, register_site_resolver


@register_site_resolver("virtualization.virtualmachine")
def _vm_sites(vm):
    if vm.site_id:
        return (vm.site_id,)
    if vm.cluster_id and vm.cluster.site_id:
        return (vm.cluster.site_id,)
    return ()


@register_location_resolver("virtualization.virtualmachine")
def _vm_locations(vm):
    return (vm.location_id,) if vm.location_id else ()
```

The contract is forgiving. A resolver receives the target instance and returns an iterable of PKs. Returning `None`, an empty iterable, or an iterable containing `None` or `0` is all fine, because the caller deduplicates and drops falsy values. That means the common case can be a one-liner:

```python
@register_site_resolver("dcim.device")
def _device_sites(device):
    return (device.site_id,)
```

Registering twice for the same key raises `ValueError` rather than overwriting. Silent overrides caused by import ordering are harder to debug than a loud failure. `unregister_resolvers("app.model")` removes both resolvers for a key and is mainly there for tests.

### Where to put the registration

The module has to be imported for the decorators to run. From another plugin, the `ready()` hook of your `PluginConfig` is the right place:

```python
class MyPluginConfig(PluginConfig):
    def ready(self):
        super().ready()
        from . import notices_resolvers  # noqa: F401
```

Registration happens at import time, so a NetBox restart is needed for a new resolver to take effect.

### Performance

Resolvers run inside `Impact.refresh_sites()`, which is called from signal handlers. On a bulk import that is once per impact row, so a resolver that issues queries multiplies quickly.

Prefer the `*_id` attribute over the related object. `device.site_id` is an attribute read; `device.site.pk` is a database round trip. Where you have to traverse a relation, as the power feed resolver does through its panel, accept the one query and stop there rather than chaining further.

## Keeping the cache fresh

Registering a resolver is half the job. The cache also has to be invalidated when something upstream changes, and that is what `notices/signals.py` does.

`Impact.refresh_sites()` runs on:

1. Any `Impact` save, via `post_save`.
2. A change to a target object, via `post_save` handlers on `Site`, `Device`, `PowerFeed`, `Circuit`.
3. A change to a model *between* the target and its site. `PowerPanel` and `CircuitTermination` both have handlers for this reason: a panel moving to a new site changes the site of every feed on it, and that is invisible to a handler watching only `PowerFeed`.
4. An explicit run of `manage.py refresh_impact_sites`.

So a new resolver needs matching signal handlers for every model whose change would alter the answer:

```python
from django.db.models.signals import post_save
from django.dispatch import receiver
from virtualization.models import VirtualMachine

from notices.signals import _refresh_impacts_for


@receiver(post_save, sender=VirtualMachine)
def _vm_changed(sender, instance, **kwargs):
    _refresh_impacts_for(instance)
```

If the resolver falls back to `vm.cluster.site_id`, a handler on `Cluster` is needed too, following the `PowerPanel` pattern: find the affected VMs, then refresh the impacts pointing at them.

Nothing detects a missing signal handler. `notices.W001` checks that a resolver exists, not that the cache stays correct. A cache that drifts is quiet, and shows up as a maintenance that stops appearing under a site filter after the device moved.

## Rebuilding the cache

`refresh_impact_sites` recomputes `sites` and `locations` for every impact:

```bash
python manage.py refresh_impact_sites
```

Limit it to specific rows with a repeatable `--impact-id`:

```bash
python manage.py refresh_impact_sites --impact-id 42 --impact-id 43
```

Run it after a bulk import or a script that bypassed signals, after adding a resolver where you want prior impacts backfilled, or when you suspect drift. It reports progress every hundred rows and is safe to re-run; `refresh_sites()` uses `.set()`, so membership is replaced rather than appended to.

## Calling the registry directly

Both lookups are available as functions, which is useful in a shell when working out why a filter is empty:

```python
from django.contrib.contenttypes.models import ContentType

from notices.resolvers import resolve_locations_for, resolve_sites_for

ct = ContentType.objects.get(app_label="dcim", model="device")
device = Device.objects.get(name="edge-01")

resolve_sites_for(ct, device)      # {12}
resolve_locations_for(ct, device)  # set()
```

Both return a deduplicated set of non-falsy PKs, and both return an empty set for an unregistered content type rather than raising. That is the behaviour that makes a missing resolver quiet, and the reason the system check exists.

## See also

- [Impact Tracking](../events/impact.md) for the model and its validation rules
- [Configuration](../configuration.md) for `allowed_content_types`
- [Architecture](architecture.md) for how the registry fits into the plugin
