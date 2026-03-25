"""
Template filters for formatting monetary values, dates, and chart data.

Like Laravel's custom Blade directives or Django's @register.filter.
These are available in all templates after {% load money %}.

Usage:
    {% load money %}
    {{ amount|format_egp }}
    {{ amount|format_currency:"USD" }}
    {{ date_val|format_date }}
"""

import json
from datetime import date, datetime
from typing import Any

from django import template
from django.utils.safestring import mark_safe

register = template.Library()

# Chart color palette
CHART_PALETTE = [
    "#0d9488",  # teal-600
    "#dc2626",  # red-600
    "#2563eb",  # blue-600
    "#d97706",  # amber-600
    "#7c3aed",  # violet-600
    "#059669",  # emerald-600
    "#db2777",  # pink-600
    "#4f46e5",  # indigo-600
]


def _format_number(n: float) -> str:
    """Format a number with thousand separators and 2 decimal places."""
    if n == 0:
        n = 0  # Eliminate negative zero
    s = f"{n:,.2f}"
    return s


@register.filter
def format_egp(amount: object) -> str:
    """Format as Egyptian Pounds: 'EGP 1,234.56'."""
    return f"EGP {_format_number(float(amount))}"  # type: ignore[arg-type]


@register.filter
def format_usd(amount: object) -> str:
    """Format as US Dollars: '$1,234.56'."""
    return f"${_format_number(float(amount))}"  # type: ignore[arg-type]


@register.filter
def format_currency(amount: object, currency: object = "EGP") -> str:
    """Format with currency symbol."""
    amt = float(amount)  # type: ignore[arg-type]
    cur = str(currency).upper()
    if cur == "USD":
        return f"${_format_number(amt)}"
    return f"EGP {_format_number(amt)}"


@register.filter
def format_num(amount: object) -> str:
    """Format number with thousand separators, no currency."""
    return _format_number(float(amount))  # type: ignore[arg-type]


@register.filter
def format_date(t: object) -> str:
    """Format as 'Mar 2, 2026'."""
    if isinstance(t, (date, datetime)):
        return t.strftime("%b %-d, %Y")
    return str(t)


@register.filter
def format_date_short(t: object) -> str:
    """Format as 'Mar 2'."""
    if isinstance(t, (date, datetime)):
        return t.strftime("%b %-d")
    return str(t)


@register.filter
def format_date_iso(t: object) -> str:
    """Format as '2026-01-02' for HTML date inputs."""
    if isinstance(t, (date, datetime)):
        return t.strftime("%Y-%m-%d")
    return str(t)


@register.filter
def neg(value: object) -> float:
    """Negate a number."""
    return -float(value)  # type: ignore[arg-type]


@register.filter
def percentage(part: object, total: object) -> float:
    """Compute (part / total) * 100."""
    if not total:
        return 0.0
    return float(part) / float(total) * 100  # type: ignore[arg-type]


@register.filter
def chart_color(index: object) -> str:
    """Return a color from the 8-color chart palette."""
    return CHART_PALETTE[int(index) % len(CHART_PALETTE)]  # type: ignore[call-overload]


@register.filter
def abs_float(value: object) -> float:
    """Return absolute value."""
    return abs(float(value))  # type: ignore[arg-type]


@register.simple_tag
def conic_gradient(segments: list[dict[str, Any]]) -> str:
    """Generate CSS conic-gradient from chart segments.
    segments: list of dicts with 'color' and 'percentage' keys."""
    if not segments:
        return "conic-gradient(#e2e8f0 0% 100%)"

    parts = []
    cumulative = 0.0
    for seg in segments:
        start = cumulative
        end = cumulative + seg["percentage"]
        if end > 100:
            end = 100
        parts.append(f"{seg['color']} {start:.1f}% {end:.1f}%")
        cumulative = end

    if cumulative < 99.9:
        parts.append(f"#e2e8f0 {cumulative:.1f}% 100%")

    return f"conic-gradient({', '.join(parts)})"


@register.simple_tag
def bar_style(height_pct: float, color: str) -> str:
    """Generate CSS for a bar chart bar."""
    return f"height:{height_pct:.1f}%;background-color:{color}"


# ---------------------------------------------------------------------------
# Additional template filters
# ---------------------------------------------------------------------------


@register.filter
def deref(value: object) -> str:
    """Unwrap a nullable string — returns '' if None."""
    if value is None:
        return ""
    return str(value)


@register.filter
def deref_float(value: object) -> float:
    """Unwrap a nullable float — returns 0.0 if None."""
    if value is None:
        return 0.0
    return float(value)  # type: ignore[arg-type]


@register.filter
def add_float(a: object, b: object) -> float:
    """Add two floats in a template.
    Usage: {{ amount|add_float:fee }}
    """
    return float(a) + float(b)  # type: ignore[arg-type]


@register.filter
def format_account_type(value: object) -> str:
    """Human-readable account type label.
    e.g., 'credit_card' → 'Credit Card', 'credit_limit' → 'Credit Line'
    """
    labels = {
        "savings": "Savings",
        "current": "Current",
        "prepaid": "Prepaid",
        "credit_card": "Credit Card",
        "credit_limit": "Credit Line",
        "cash": "Cash",
    }
    key = str(value)
    return labels.get(key, key)


@register.filter
def format_type(value: object) -> str:
    """Human-readable transaction type label.
    e.g., 'loan_out' → 'Loan Given', 'loan_repayment' → 'Loan Repayment'
    """
    labels = {
        "expense": "Expense",
        "income": "Income",
        "transfer": "Transfer",
        "exchange": "Exchange",
        "loan_out": "Loan Given",
        "loan_in": "Loan Received",
        "loan_repayment": "Loan Repayment",
    }
    key = str(value)
    return labels.get(key, key)


# ---------------------------------------------------------------------------
# Simple tags
# ---------------------------------------------------------------------------


@register.simple_tag
def sparkline_points(values: list[float]) -> str:
    """Generate SVG polyline points from a list of values.

    Normalises values into a '0 0 100 40' viewBox.
    Usage: <polyline points="{% sparkline_points values %}" />
    """
    n = len(values)
    if n == 0:
        return ""
    if n == 1:
        return "0,20 100,20"

    min_v = min(values)
    max_v = max(values)
    span = max_v - min_v or 1  # avoid division by zero when all values are equal

    pts = []
    for i, v in enumerate(values):
        x = i / (n - 1) * 100
        y = 38 - (
            (v - min_v) / span * 36
        )  # 38=bottom, 36=usable height; SVG y is inverted
        pts.append(f"{x:.1f},{y:.1f}")
    return " ".join(pts)


@register.simple_tag(name="dict")
def make_dict(**kwargs: Any) -> dict[str, Any]:
    """Create a dict from keyword arguments for passing multiple values to included templates.

    The tag is named 'dict' in templates; function renamed to avoid shadowing Python's dict built-in.
    Usage: {% dict values=values color="#0d9488" as chart_data %}
           {% include "chart_sparkline.html" with data=chart_data %}
    """
    return kwargs


@register.filter
def get_item(dictionary: object, key: object) -> Any:
    """Look up a dict key in a template.

    Usage: {{ my_dict|get_item:key_var }}
    Returns None if key is missing or dictionary is not a dict.
    """
    if isinstance(dictionary, dict):
        return dictionary.get(str(key))
    return None


@register.filter
def is_image_icon(value: object) -> bool:
    """Return True if value is an image filename (.png or .svg), False for emoji/None.

    Usage: {% if institution.icon|is_image_icon %}<img ...>{% endif %}
    """
    return isinstance(value, str) and value.endswith((".png", ".svg"))


@register.filter
def institution_display_name(stored_name: object) -> str:
    """Expand a stored institution abbreviation to its full display name.

    e.g. "CIB" → "CIB - Commercial International Bank", "BM" → "Banque Misr"
    Falls back to the stored value for custom (non-preset) institutions.

    Usage: {{ institution.name|institution_display_name }}
    """
    from accounts.institution_data import get_display_name

    return get_display_name(str(stored_name)) if stored_name else ""


@register.filter
def categories_json(categories: Any) -> str:
    """Serialize a categories queryset/list to JSON for use in data-categories attribute.

    Returns a JSON string with [{id, name, icon}, ...].
    Usage: data-categories='{{ categories|categories_json }}'
    """
    items = []
    for cat in categories:
        if hasattr(cat, "id"):
            # Model instance
            items.append({"id": str(cat.id), "name": cat.name, "icon": cat.icon or ""})
        elif isinstance(cat, dict):
            # Dict from .values() or service layer
            items.append(
                {
                    "id": str(cat.get("id", "")),
                    "name": cat.get("name", ""),
                    "icon": cat.get("icon", "") or "",
                }
            )
    return mark_safe(json.dumps(items, ensure_ascii=False))
