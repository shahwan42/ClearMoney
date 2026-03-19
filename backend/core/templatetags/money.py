"""
Template filters — Django equivalents of Go's template functions in templates.go.

Like Laravel's custom Blade directives or Django's @register.filter.
These are available in all templates after {% load money %}.

Usage:
    {% load money %}
    {{ amount|format_egp }}
    {{ amount|format_currency:"USD" }}
    {{ date_val|format_date }}
"""

from datetime import date, datetime
from typing import Any

from django import template

register = template.Library()

# Chart color palette — matches Go's chartPalette in charts.go
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
    """Format a number with thousand separators and 2 decimal places.
    Equivalent of Go's formatNumber() in templates.go."""
    if n == 0:
        n = 0  # Eliminate negative zero
    s = f"{n:,.2f}"
    return s


@register.filter
def format_egp(amount: object) -> str:
    """Format as Egyptian Pounds: 'EGP 1,234.56'. Like Go's formatEGP."""
    return f"EGP {_format_number(float(amount))}"  # type: ignore[arg-type]


@register.filter
def format_usd(amount: object) -> str:
    """Format as US Dollars: '$1,234.56'. Like Go's formatUSD."""
    return f"${_format_number(float(amount))}"  # type: ignore[arg-type]


@register.filter
def format_currency(amount: object, currency: object = "EGP") -> str:
    """Format with currency symbol. Like Go's formatCurrency."""
    amt = float(amount)  # type: ignore[arg-type]
    cur = str(currency).upper()
    if cur == "USD":
        return f"${_format_number(amt)}"
    return f"EGP {_format_number(amt)}"


@register.filter
def format_num(amount: object) -> str:
    """Format number with thousand separators, no currency. Like Go's formatNum."""
    return _format_number(float(amount))  # type: ignore[arg-type]


@register.filter
def format_date(t: object) -> str:
    """Format as 'Mar 2, 2026'. Like Go's formatDate."""
    if isinstance(t, (date, datetime)):
        return t.strftime("%b %-d, %Y")
    return str(t)


@register.filter
def format_date_short(t: object) -> str:
    """Format as 'Mar 2'. Like Go's formatDateShort."""
    if isinstance(t, (date, datetime)):
        return t.strftime("%b %-d")
    return str(t)


@register.filter
def format_date_iso(t: object) -> str:
    """Format as '2026-01-02' for HTML date inputs. Like Go's formatDateISO."""
    if isinstance(t, (date, datetime)):
        return t.strftime("%Y-%m-%d")
    return str(t)


@register.filter
def neg(value: object) -> float:
    """Negate a number. Like Go's neg."""
    return -float(value)  # type: ignore[arg-type]


@register.filter
def percentage(part: object, total: object) -> float:
    """Compute (part / total) * 100. Like Go's percentage."""
    if not total:
        return 0.0
    return float(part) / float(total) * 100  # type: ignore[arg-type]


@register.filter
def chart_color(index: object) -> str:
    """Return a color from the 8-color chart palette. Like Go's chartColor."""
    return CHART_PALETTE[int(index) % len(CHART_PALETTE)]  # type: ignore[call-overload]


@register.filter
def abs_float(value: object) -> float:
    """Return absolute value. Like Go's abs."""
    return abs(float(value))  # type: ignore[arg-type]


@register.simple_tag
def conic_gradient(segments: list[dict[str, Any]]) -> str:
    """Generate CSS conic-gradient from chart segments. Like Go's conicGradient.
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
    """Generate CSS for a bar chart bar. Like Go's barStyle."""
    return f"height:{height_pct:.1f}%;background-color:{color}"
