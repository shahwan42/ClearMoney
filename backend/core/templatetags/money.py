"""
Template filters for formatting monetary values, dates, and chart data.

Like Laravel's custom Blade directives or Django's @register.filter.
These are available in all templates after {% load money %}.

Usage:
    {% load money %}
    {{ amount|format_currency:"EGP" }}
"""

import json
from datetime import date, datetime
from typing import Any

from django import template
from django.db.models import QuerySet
from django.utils.formats import date_format
from django.utils.translation import get_language

register = template.Library()


@register.filter
def format_currency(amount: object, currency: object = "EGP") -> str:
    """Format a decimal/float as a currency string (e.g. 1,234.56 EGP)."""
    try:
        val = float(amount) if amount is not None else 0.0
    except (ValueError, TypeError):
        val = 0.0

    curr = str(currency) if currency else "EGP"
    return f"{val:,.2f} {curr}"


@register.filter
def format_egp(amount: object) -> str:
    """Alias for format_currency(amount, 'EGP')."""
    return format_currency(amount, "EGP")


@register.filter
def format_usd(amount: object) -> str:
    """Alias for format_currency(amount, 'USD')."""
    return format_currency(amount, "USD")


@register.filter
def abs_float(value: object) -> float:
    """Return the absolute value of a float/decimal."""
    try:
        return abs(float(value))  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return 0.0


@register.filter
def format_date_short(value: object) -> str:
    """Format date as 'Jan 15' (omits year)."""
    if isinstance(value, date | datetime):
        return date_format(value, "M j")
    return str(value)


@register.filter
def percentage(value: object, total: object) -> float:
    """Calculate percentage (value / total * 100). Returns 0 if total is 0."""
    try:
        v = float(value)  # type: ignore[arg-type]
        t = float(total)  # type: ignore[arg-type]
        if t == 0:
            return 0.0
        return (v / t) * 100
    except (ValueError, TypeError):
        return 0.0


@register.filter
def categories_json(categories: QuerySet) -> str:
    """Serialize category objects for the JS combobox."""
    # Categories are passed as a QuerySet of models with 'name' (JSONB) and 'icon'
    data = []
    lang = (get_language() or "en").split("-")[0]
    for c in categories:
        name_raw = c.name if isinstance(c.name, dict) else {}
        name = name_raw.get(lang) or name_raw.get("en", "Uncategorized")
        data.append(
            {
                "id": str(c.id),
                "name": name,
                "icon": c.icon or "",
            }
        )
    return json.dumps(data)


@register.filter
def format_type(value: str) -> str:
    """Uppercase and replace underscores (e.g. 'credit_card' -> 'Credit Card')."""
    return value.replace("_", " ").title()


# Additional template filters
# ---------------------------------------------------------------------------


@register.filter
def subtract(a: object, b: object) -> float:
    """Subtract b from a.
    Usage: {{ amount|subtract:fee }}
    """
    return float(a) - float(b)  # type: ignore[arg-type]


@register.filter
def split(value: str, arg: str) -> list[str]:
    """Split a string by a delimiter.
    Usage: {{ "a,b,c"|split:"," }}
    """
    return value.split(arg)


@register.filter
def map_attr(value: list[dict[str, Any]], arg: str) -> list[Any]:
    """Extract a specific key from a list of dicts.
    Usage: {{ list_of_dicts|map_attr:"name" }}
    """
    return [d.get(arg) for d in value]


@register.filter
def money_format(amount: object, currency: object = "EGP") -> str:
    """Alias for format_currency.
    Usage: {{ amount|money_format:currency }}
    """
    return format_currency(amount, currency)


@register.filter
def get_item(dictionary: Any, key: Any) -> Any:
    """Get an item from a dictionary.
    Usage: {{ dict|get_item:key }}
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None


@register.filter
def max_float(value: list[float]) -> float:
    """Return the maximum value in a list of floats.
    Usage: {{ list|max_float }}
    """
    if not value:
        return 0.0
    return max(value)


@register.filter
def deref(value: object) -> str:
    """Unwrap a nullable string — returns '' if None."""
    if value is None:
        return ""
    return str(value)


@register.filter
def get_lang_name(raw: Any) -> str:
    """Extract translated string from category/tag name JSONB."""
    if isinstance(raw, dict):
        lang = (get_language() or "en").split("-")[0]
        if lang in raw:
            return str(raw[lang])
        return str(raw.get("en", ""))
    return str(raw) if raw else ""


@register.filter
def is_image_icon(value: object) -> bool:
    """Check if an icon string is a path to an image (e.g. ends with .svg, .png)."""
    s = str(value).lower()
    return s.endswith((".svg", ".png", ".jpg", ".jpeg", ".webp"))


@register.filter
def endswith(value: str, arg: str) -> bool:
    """Check if a string ends with another string."""
    return str(value).lower().endswith(str(arg).lower())
