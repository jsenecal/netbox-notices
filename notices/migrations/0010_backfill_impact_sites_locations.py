"""
Data migration: populate Impact.sites / Impact.locations for existing rows.

Runs the resolver registry against every existing Impact, exactly as a normal
post_save would. Reverse migration clears the M2Ms (cheap; the rows themselves
are removed by the schema migration's reverse step).
"""

from django.db import migrations


def _resolve_for_impact(impact, content_type):
    """
    Run the live resolver registry against a single Impact row. ``content_type``
    must be a live ContentType (not the historical proxy) so ``.model_class()``
    is available to fetch a fresh target instance from its own app.
    """
    from notices.resolvers import resolve_locations_for, resolve_sites_for

    target_model = content_type.model_class()
    if target_model is None:
        return set(), set()
    target = target_model.objects.filter(pk=impact.target_object_id).first()
    if target is None:
        return set(), set()
    return (
        resolve_sites_for(content_type, target),
        resolve_locations_for(content_type, target),
    )


def backfill(apps, schema_editor):
    # Use the live ContentType class so .model_class() is available.
    # The historical proxy from apps.get_model("contenttypes", "ContentType")
    # does not expose model_class(), which the resolver path needs.
    from django.contrib.contenttypes.models import ContentType

    Impact = apps.get_model("notices", "Impact")

    ct_cache: dict[int, ContentType] = {}

    for impact in Impact.objects.all().iterator():
        ct = ct_cache.get(impact.target_content_type_id)
        if ct is None:
            ct = ContentType.objects.get(pk=impact.target_content_type_id)
            ct_cache[impact.target_content_type_id] = ct

        site_pks, location_pks = _resolve_for_impact(impact, ct)
        if site_pks:
            impact.sites.set(site_pks)
        if location_pks:
            impact.locations.set(location_pks)


def clear(apps, schema_editor):
    Impact = apps.get_model("notices", "Impact")
    for impact in Impact.objects.all().iterator():
        impact.sites.clear()
        impact.locations.clear()


class Migration(migrations.Migration):
    dependencies = [
        ("notices", "0009_add_impact_sites_locations"),
    ]

    operations = [
        migrations.RunPython(backfill, reverse_code=clear),
    ]
