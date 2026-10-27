"""
Django system checks for the notices plugin.

- W001: every entry in ``allowed_content_types`` has a Site resolver registered.
  Without one, impacts targeting that content type silently have an empty
  ``sites`` cache and won't appear in site/region/location filters -- a class
  of bug worth catching at startup rather than at query time.
- W002: every ``parent_fields`` entry names an installed model and a parent
  field the object dropdown can show; invalid entries are ignored at runtime.
"""

from django.core.checks import Warning, register

from .resolvers import SITE_RESOLVERS
from .utils import get_allowed_content_types, parse_parent_fields


@register()
def check_resolver_coverage(app_configs, **kwargs):
    """W001: warn for allowed content types missing a Site resolver."""
    warnings = []
    registered = {k.lower() for k in SITE_RESOLVERS}
    for ct_string in get_allowed_content_types():
        if ct_string.lower() not in registered:
            warnings.append(
                Warning(
                    f"No site resolver registered for allowed content type {ct_string!r}.",
                    hint=(
                        "Impacts targeting this type will have empty Impact.sites and won't appear "
                        "in site/region/location filters. Register one via "
                        "notices.resolvers.register_site_resolver, and add a matching signal "
                        "handler in notices.signals so the cache stays fresh when the target's "
                        "site changes."
                    ),
                    id="notices.W001",
                )
            )
    return warnings


@register()
def check_parent_fields(app_configs, **kwargs):
    """W002: warn for a malformed `parent_fields` setting or entries the runtime ignores."""
    hint = (
        "parent_fields must be a dict of installed 'app_label.ModelName' (any case) -> name of a ForeignKey "
        "on that model that its brief REST serializer includes."
    )
    return [
        Warning(
            f"Ignoring parent_fields: {reason}."
            if key is None
            else f"Ignoring parent_fields entry {key!r}: {name!r} ({reason}).",
            hint=hint,
            id="notices.W002",
        )
        for key, name, reason in parse_parent_fields()[1]
    ]
