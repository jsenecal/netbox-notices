"""
Utility functions for vendor notification plugin
"""

import functools
from collections import Counter

from django.apps import apps
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldDoesNotExist
from django.core.signals import setting_changed
from django.db import models
from django.dispatch import receiver
from django.utils.module_loading import import_string
from netbox.api.exceptions import SerializerNotFound
from utilities.api import get_serializer_for_model

from .constants import DEFAULT_ALLOWED_CONTENT_TYPES


def _plugin_setting(name, default):
    return settings.PLUGINS_CONFIG.get("notices", {}).get(name, default)


def get_allowed_content_types():
    """
    Get list of allowed content types from plugin config.

    Returns list from PLUGINS_CONFIG['notices']['allowed_content_types']
    or DEFAULT_ALLOWED_CONTENT_TYPES if not configured.
    """
    return _plugin_setting("allowed_content_types", DEFAULT_ALLOWED_CONTENT_TYPES)


def get_allowed_content_type_pks():
    """ContentType pks of the allowed content types; malformed or unknown entries are skipped."""
    pks = []
    for type_string in get_allowed_content_types():
        try:
            app_label, model = type_string.lower().split(".")
        except (ValueError, AttributeError):
            continue
        if ct := ContentType.objects.filter(app_label=app_label, model=model).first():
            pks.append(ct.pk)
    return pks


@functools.cache
def has_filter_form(model):
    """
    NetBox's object selector modal (ObjectSelectorView) imports `<app>.forms.<Model>FilterForm` and
    `<app>.filtersets.<Model>FilterSet` unguarded and searches `model.objects.restrict(user)`; offer
    the selector only when all three exist.
    """
    if not hasattr(model.objects, "restrict"):
        return False
    app, name = model._meta.app_label, model.__name__
    try:
        import_string(f"{app}.forms.{name}FilterForm")
        import_string(f"{app}.filtersets.{name}FilterSet")
    except ImportError:
        return False
    return True


def parent_field_error(model, name):
    """
    Why `name` cannot be shown as the parent of `model` in an object dropdown, or None if it can.

    The dropdown reads the parent from the brief REST representation (`?brief=1`), so the field must
    be both a ForeignKey on the model and one of its serializer's `brief_fields`.
    """
    if not isinstance(name, str) or not name:
        return "the value must be a field name"
    try:
        field = model._meta.get_field(name)
    except FieldDoesNotExist:
        return f"{model._meta.label} has no field {name!r}"
    if not isinstance(field, models.ForeignKey):
        return f"{model._meta.label}.{name} is not a ForeignKey"
    try:
        brief_fields = get_serializer_for_model(model).Meta.brief_fields
    except (SerializerNotFound, AttributeError):
        return f"{model._meta.label} has no REST serializer with brief_fields"
    if name not in brief_fields:
        return f"{name!r} is not in the brief REST representation of {model._meta.label}"
    return None


@functools.cache
def parse_parent_fields():
    """
    Validate PLUGINS_CONFIG['notices']['parent_fields'] (no built-in default).

    Returns `(fields, errors)`: `fields` maps `Model._meta.label_lower` to the parent field name of each
    valid entry; `errors` lists `(key, value, reason)` for each ignored entry, or a single
    `(None, setting, reason)` when the setting is not a dict. The form fields use `fields`; system check
    W002 reports `errors`. Keys are case-insensitive, so two keys naming the same model are both ignored.
    """
    configured = _plugin_setting("parent_fields", {})
    if not isinstance(configured, dict):
        return {}, [(None, configured, f"expected a dict, got {type(configured).__name__}")]

    models_by_label = {model._meta.label_lower: model for model in apps.get_models()}
    key_counts = Counter(key.lower() for key in configured if isinstance(key, str))
    fields, errors = {}, []
    for key, name in configured.items():
        model = models_by_label.get(key.lower()) if isinstance(key, str) else None
        if model is None:
            reason = "not an installed 'app_label.ModelName'"
        elif key_counts[key.lower()] > 1:
            reason = "another key names the same model (keys are case-insensitive)"
        else:
            reason = parent_field_error(model, name)
        if reason:
            errors.append((key, name, reason))
        else:
            fields[model._meta.label_lower] = name
    return fields, errors


def parent_field_for(model):
    """Name of the configured parent ForeignKey of `model`, or None if unset or invalid."""
    return parse_parent_fields()[0].get(model._meta.label_lower)


@receiver(setting_changed)
def clear_parent_fields_cache(*, setting, **kwargs):
    if setting == "PLUGINS_CONFIG":
        parse_parent_fields.cache_clear()
