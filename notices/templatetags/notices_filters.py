import nh3
from django import template
from django.utils.safestring import mark_safe
from netbox.config import get_config
from utilities.constants import HTML_ALLOWED_ATTRIBUTES, HTML_ALLOWED_TAGS

register = template.Library()

# NetBox's allow-list keeps `class` on `div`, which is safe on the pages it was written for --
# operator-authored comment fields. Email bodies are different: they arrive from a provider,
# and they render inside a page that has already loaded Tabler, so a borrowed utility class
# ("position-fixed w-100 h-100") floats the email over the surrounding UI as a clickable
# overlay. Dropping the attribute costs the email nothing, since mail clients never see this
# page's stylesheet. Derived from NetBox's own mapping so upstream additions carry over.
EMAIL_ALLOWED_ATTRIBUTES = {tag: attributes - {"class"} for tag, attributes in HTML_ALLOWED_ATTRIBUTES.items()}


@register.filter(name="sanitize_html")
def sanitize_html(value):
    """Sanitize email HTML with NetBox's nh3 allow-list, minus the styling hooks."""
    if not value:
        return value
    return mark_safe(
        nh3.clean(
            str(value),
            tags=HTML_ALLOWED_TAGS,
            attributes=EMAIL_ALLOWED_ATTRIBUTES,
            url_schemes=set(get_config().ALLOWED_URL_SCHEMES),
        )
    )
