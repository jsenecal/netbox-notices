from django import template
from django.utils.safestring import mark_safe
from netbox.config import get_config
from utilities.html import clean_html

register = template.Library()


@register.filter(name="sanitize_html")
def sanitize_html(value):
    """Sanitize HTML using NetBox's nh3-based clean_html utility."""
    if not value:
        return value
    schemes = get_config().ALLOWED_URL_SCHEMES
    return mark_safe(clean_html(str(value), schemes))
