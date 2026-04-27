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
from django.utils.encoding import force_str
from django.utils.safestring import mark_safe
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _

register = template.Library()

# Chart color palette — CSS custom properties so dark mode can override via .dark { --chart-N: ... }
CHART_PALETTE = [
    "var(--chart-1)",  # teal
    "var(--chart-2)",  # red
    "var(--chart-3)",  # blue
    "var(--chart-4)",  # amber
    "var(--chart-5)",  # violet
    "var(--chart-6)",  # emerald
    "var(--chart-7)",  # pink
    "var(--chart-8)",  # indigo
]


def _format_number(n: float) -> str:
    """Format a number with thousand separators and 2 decimal places."""
    if n == 0:
        n = 0  # Eliminate negative zero
    return f"{n:,.2f}"


_CURRENCY_SYMBOLS: dict[str, str] = {
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "EGP": "EGP",
}


def get_currency_symbol(code: str) -> str:
    """Return the symbol for a currency code, using a local cache."""
    code = code.upper()
    if code not in _CURRENCY_SYMBOLS:
        # Avoid top-level import to prevent circular dependencies
        from auth_app.models import Currency

        try:
            # We don't use .get() to avoid DB hits on every call if it doesn't exist
            # but since it's a small table it's fine for now.
            cur = Currency.objects.filter(code=code).first()
            if cur and cur.symbol:
                _CURRENCY_SYMBOLS[code] = cur.symbol
            else:
                _CURRENCY_SYMBOLS[code] = code
        except Exception:
            _CURRENCY_SYMBOLS[code] = code
    return _CURRENCY_SYMBOLS[code]


@register.filter
def format_currency(amount: object, currency: object = "EGP") -> str:
    """Format with currency symbol."""
    try:
        if amount is None or str(amount).strip() == "":
            amt = 0.0
        else:
            amt = float(str(amount))
    except (ValueError, TypeError):
        amt = 0.0

    if amt == 0:
        amt = 0.0  # Eliminate negative zero

    cur_code = str(currency).upper() if currency else "EGP"
    symbol = get_currency_symbol(cur_code)

    formatted_num = _format_number(amt)

    # Standard convention: single-character symbols like $, £, € often don't have a space.
    # ISO codes like EGP, USD or multi-char symbols like SAR, Rp usually do.
    if len(symbol) > 1 or symbol == cur_code:
        return f"{symbol} {formatted_num}"

    return f"{symbol}{formatted_num}"


@register.filter
def format_egp(amount: object) -> str:
    """Format as Egyptian Pounds: 'EGP 1,234.56'."""
    return format_currency(amount, "EGP")


@register.filter
def format_usd(amount: object) -> str:
    """Format as US Dollars: '$1,234.56'."""
    return format_currency(amount, "USD")


@register.filter
def format_num(amount: object) -> str:
    """Format number with thousand separators, no currency."""
    try:
        return _format_number(float(amount))  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return "0.00"


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
    try:
        return -float(value)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return 0.0


@register.filter
def percentage(part: object, total: object) -> float:
    """Compute (part / total) * 100."""
    try:
        p = float(part)  # type: ignore[arg-type]
        t = float(total)  # type: ignore[arg-type]
        if not t:
            return 0.0
        return (p / t) * 100
    except (ValueError, TypeError):
        return 0.0


@register.filter
def chart_color(index: object) -> str:
    """Return a color from the 8-color chart palette."""
    try:
        return CHART_PALETTE[int(index) % len(CHART_PALETTE)]  # type: ignore[call-overload]
    except (ValueError, TypeError):
        return CHART_PALETTE[0]


@register.filter
def abs_float(value: object) -> float:
    """Return absolute value."""
    try:
        return abs(float(value))  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return 0.0


@register.simple_tag
def conic_gradient(segments: list[dict[str, Any]]) -> str:
    """Generate CSS conic-gradient from chart segments."""
    if not segments:
        return "conic-gradient(var(--chart-empty) 0% 100%)"

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
        parts.append(f"var(--chart-empty) {cumulative:.1f}% 100%")

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
    try:
        return float(value) if value is not None else 0.0  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return 0.0


@register.filter
def add_float(a: object, b: object) -> float:
    """Add two floats."""
    try:
        return float(a) + float(b)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return 0.0


@register.filter
def subtract(a: object, b: object) -> float:
    """Subtract b from a."""
    try:
        return float(a) - float(b)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return 0.0


@register.filter
def format_account_type(value: object) -> str:
    """Human-readable account type label."""
    labels = {
        "savings": _("Savings"),
        "current": _("Current"),
        "prepaid": _("Prepaid"),
        "credit_card": _("Credit Card"),
        "credit_limit": _("Credit Limit"),
        "cash": _("Cash"),
    }
    key = str(value)
    return force_str(labels.get(key, key))


@register.filter
def format_type(value: object) -> str:
    """Human-readable transaction type label."""
    labels = {
        "expense": _("Expense"),
        "income": _("Income"),
        "transfer": _("Transfer"),
        "exchange": _("Exchange"),
        "loan_out": _("Loan Given"),
        "loan_in": _("Loan Received"),
        "loan_repayment": _("Loan Repayment"),
    }
    key = str(value)
    return force_str(labels.get(key, key))


@register.filter
def split(value: str, arg: str) -> list[str]:
    """Split a string by a delimiter."""
    return str(value).split(arg)


@register.filter
def map_attr(value: list[dict[str, Any]], arg: str) -> list[Any]:
    """Extract a specific key from a list of dicts."""
    if not isinstance(value, list):
        return []
    return [d.get(arg) for d in value if isinstance(d, dict)]


@register.filter
def money_format(amount: object, currency: object = "EGP") -> str:
    """Alias for format_currency."""
    return format_currency(amount, currency)


@register.filter
def find_all_by_attr(value: list[Any], val: str, attr: str = "currency") -> list[Any]:
    """Find all objects in a list by attribute value. Defaults to 'currency'."""
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        item_val = None
        if isinstance(item, dict):
            item_val = item.get(attr)
        else:
            item_val = getattr(item, attr, None)

        if str(item_val) == str(val):
            result.append(item)
    return result


@register.filter
def find_by_attr(value: list[Any], arg: str) -> Any:
    """Find an object in a list by attribute value. Arg format: 'attr:value'."""
    if not isinstance(value, list) or ":" not in arg:
        return None
    attr, val = arg.split(":", 1)
    for item in value:
        # Check if item is a dict or an object
        item_val = None
        if isinstance(item, dict):
            item_val = item.get(attr)
        else:
            item_val = getattr(item, attr, None)

        if str(item_val) == val:
            return item
    return None


@register.filter
def get_item(dictionary: object, key: object) -> Any:
    """Look up a dict key in a template."""
    if isinstance(dictionary, dict):
        return dictionary.get(str(key))
    return None


@register.filter
def max_float(value: list[float]) -> float:
    """Return the maximum value in a list of floats."""
    if not value:
        return 0.0
    try:
        return max(float(v) for v in value)
    except (ValueError, TypeError):
        return 0.0


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
    if not isinstance(value, str):
        return False
    s = value.lower()
    return s.endswith((".svg", ".png", ".jpg", ".jpeg", ".webp"))


@register.filter
def endswith(value: str, arg: str) -> bool:
    """Check if a string ends with another string."""
    return str(value).lower().endswith(str(arg).lower())


# ---------------------------------------------------------------------------
# Simple tags
# ---------------------------------------------------------------------------


@register.simple_tag
def sparkline_points(values: list[float]) -> str:
    """Generate SVG polyline points from a list of values."""
    n = len(values)
    if n == 0:
        return ""
    if n == 1:
        return "0,20 100,20"

    try:
        floats = [float(v) for v in values]
    except (ValueError, TypeError):
        return ""

    min_v = min(floats)
    max_v = max(floats)
    span = max_v - min_v or 1

    pts = []
    for i, v in enumerate(floats):
        x = i / (n - 1) * 100
        y = 38 - ((v - min_v) / span * 36)
        pts.append(f"{x:.1f},{y:.1f}")
    return " ".join(pts)


@register.simple_tag(name="dict")
def make_dict(**kwargs: Any) -> dict[str, Any]:
    """Create a dict from keyword arguments."""
    return kwargs


@register.filter
def institution_display_name(stored_name: object) -> str:
    """Expand a stored institution abbreviation to its full display name."""
    from accounts.institution_data import get_display_name

    return get_display_name(str(stored_name)) if stored_name else ""


@register.filter
def categories_json(categories: Any) -> str:
    """Serialize a categories queryset/list to JSON for use in data-categories attribute."""
    items = []
    lang = (get_language() or "en").split("-")[0]
    for cat in categories:
        if hasattr(cat, "id"):
            # Model instance
            name_raw = getattr(cat, "name", {})
            if isinstance(name_raw, dict):
                display_name = name_raw.get(lang) or name_raw.get("en", "Uncategorized")
            else:
                display_name = str(name_raw)
            items.append(
                {"id": str(cat.id), "name": display_name, "icon": cat.icon or ""}
            )
        elif isinstance(cat, dict):
            # Dict
            raw_name = cat.get("name", "")
            if isinstance(raw_name, dict):
                resolved = raw_name.get(lang) or raw_name.get("en", "")
            else:
                resolved = raw_name
            items.append(
                {
                    "id": str(cat.get("id", "")),
                    "name": resolved,
                    "icon": cat.get("icon", "") or "",
                }
            )
    return mark_safe(json.dumps(items, ensure_ascii=False))


@register.filter
def accounts_json(accounts: Any) -> str:
    """Serialize account picker data for searchable account comboboxes."""
    items = []
    for account in accounts:
        if hasattr(account, "id"):
            items.append(
                {
                    "id": str(account.id),
                    "name": str(getattr(account, "name", "")),
                    "currency": str(getattr(account, "currency", "")),
                    "type": str(getattr(account, "type", "")),
                    "current_balance": float(getattr(account, "current_balance", 0)),
                    "institution_name": str(
                        getattr(getattr(account, "institution", None), "name", "") or ""
                    ),
                    "institution_icon": str(
                        getattr(getattr(account, "institution", None), "icon", "") or ""
                    ),
                    "institution_color": str(
                        getattr(getattr(account, "institution", None), "color", "")
                        or ""
                    ),
                }
            )
        elif isinstance(account, dict):
            items.append(
                {
                    "id": str(account.get("id", "")),
                    "name": str(account.get("name", "")),
                    "currency": str(account.get("currency", "")),
                    "type": str(account.get("type", "")),
                    "current_balance": float(account.get("current_balance", 0) or 0),
                    "institution_name": str(account.get("institution_name", "") or ""),
                    "institution_icon": str(account.get("institution_icon", "") or ""),
                    "institution_color": str(
                        account.get("institution_color", "") or ""
                    ),
                }
            )
    return json.dumps(items, ensure_ascii=False)


@register.simple_tag
def exchange_rate_label(src_currency: str, dest_currency: str) -> str:
    """Return the rate label for an exchange: '{dest} per 1 {src}'."""
    return f"{dest_currency} per 1 {src_currency}"
