# Template Extensions

The plugin injects panels into pages that belong to NetBox core, so a maintenance shows up where an engineer is already looking rather than only under the Notices menu. All of it lives in `notices/template_content.py`, using NetBox's `PluginTemplateExtension` API.

Three things get injected:

- An event history panel on every object type in `allowed_content_types`.
- An events panel on the Provider detail page.
- A dashboard widget listing upcoming maintenances.

## Event history panel

Every detail page for an allowed content type gets a card in the right-hand column showing the maintenances and outages that impact that object. The card renders as two tabs with counts, and each tab falls back to "No maintenances in this period" when empty. If there are no events at all in the window, the extension returns an empty string and no card is drawn.

### Generated classes

The interesting part is that these classes do not exist in the source. `allowed_content_types` is a runtime setting, so the extension classes are built from it at import time:

```python
def _create_event_history_extensions():
    allowed_types = get_allowed_content_types()
    extensions = []

    def right_page_method(self):
        return render_event_history(self.context["object"])

    for content_type_str in allowed_types:
        app_label, model = content_type_str.lower().split(".")
        extension_class = type(
            f"{model.capitalize()}EventHistory",
            (PluginTemplateExtension,),
            {"models": [f"{app_label}.{model}"], "right_page": right_page_method},
        )
        extensions.append(extension_class)

    return extensions


template_extensions = _create_event_history_extensions() + [ProviderEventsExtension]
```

Two consequences follow.

Adding a content type to `allowed_content_types` gives it an event history panel with no further work. That is separate from the [resolver](resolvers.md) requirement: the panel works without a resolver, because it queries `Impact` by content type and object ID directly rather than through the site cache. A resolver is only needed for the site-scoped filters.

The classes are built when the module is imported, so a change to `allowed_content_types` needs a NetBox restart before the new panel appears.

### Which events are shown

`render_event_history(obj)` looks up impacts pointing at the object, then keeps an event if any of these hold:

- It starts after the cutoff, which is now minus `event_history_days`.
- It has an `end` in the future.
- It has no `end` at all, which is the open-ended outage case.

The default window is 30 days, configurable per deployment:

```python
PLUGINS_CONFIG = {
    "notices": {
        "event_history_days": 90,
    },
}
```

The setting is read from `netbox.config.get_config()` on every render rather than cached at import, so a change to it takes effect without a restart. This is the opposite of the class generation above, which is why changing `event_history_days` is cheap and changing `allowed_content_types` is not.

Filtering happens in Python, not SQL. `render_event_history` pulls every impact for the object and then walks the list. That is fine for the row counts a single device accumulates, but it is worth knowing before pointing it at something with thousands of impacts.

## Provider events panel

`ProviderEventsExtension` targets `circuits.provider` and is a plain class, since there is only one of it. It shows every maintenance and outage linked to the provider through the `provider` FK, not through impacts, using the same `event_history_days` window expressed as a single ORM filter:

```python
time_filter = Q(start__gte=cutoff_date) | Q(end__gte=timezone.now()) | Q(end__isnull=True)
```

Events are ordered newest first and prefetch their impacts for the count column.

## Dashboard widget

`notices/widgets.py` registers `UpcomingMaintenanceWidget` with NetBox's dashboard. Users add it from the NetBox home page; it is not enabled by default.

The widget lists maintenances in any active status, `TENTATIVE`, `CONFIRMED`, `IN-PROCESS`, `RE-SCHEDULED` or `UNKNOWN`, annotated with an impact count. It has no date bound, so it shows past events that were never closed out as well as upcoming ones. Default size is 8 by 3.

This is separate from the plugin's own [dashboard](../events/dashboard.md), which is a full page under the Notices menu.

## Sanitising provider email

Received notifications store the provider's raw email, and the detail page renders the HTML body. `notices/templatetags/notices_filters.py` provides the `sanitize_html` filter used for that.

It runs `nh3` with NetBox's own allow-lists, with one change: the `class` attribute is stripped.

```python
EMAIL_ALLOWED_ATTRIBUTES = {
    tag: attributes - {"class"} for tag, attributes in HTML_ALLOWED_ATTRIBUTES.items()
}
```

NetBox's allow-list keeps `class` on `div`, which is safe for the operator-authored comment fields it was written for. An email body is different. It arrives from a provider and renders inside a page that has already loaded Tabler, so a borrowed utility class such as `position-fixed w-100 h-100` floats the email over the surrounding UI as a clickable overlay. Dropping the attribute costs the email nothing, because mail clients never see this page's stylesheet.

The mapping is derived from NetBox's, so upstream additions to the allow-list carry over.

## Adding your own extension

If you are extending the plugin from another plugin, use NetBox's normal mechanism and import the render helpers if they are useful:

```python
from netbox.plugins import PluginTemplateExtension

from notices.template_content import render_event_history


class TenantEventHistory(PluginTemplateExtension):
    models = ["tenancy.tenant"]

    def right_page(self):
        return render_event_history(self.context["object"])


template_extensions = [TenantEventHistory]
```

`render_event_history` returns an empty string when there is nothing to show, so it is safe to call unconditionally.

## See also

- [Configuration](../configuration.md) for `allowed_content_types` and `event_history_days`
- [Site and Location Resolvers](resolvers.md) for making a new type filterable
- [Architecture](architecture.md) for the full registry list
