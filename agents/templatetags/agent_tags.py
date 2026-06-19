import json

from django import template

register = template.Library()


@register.filter
def lookup(d, key):
    """{{ my_dict|lookup:key }} — dict key access in templates."""
    if isinstance(d, dict):
        return d.get(key, "")
    return ""


@register.filter
def to_json(value):
    """{{ value|to_json }} — serialize to JSON string safe for inline JS."""
    return json.dumps(value)
