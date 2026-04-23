"""Currency registry and user preference helpers."""

from __future__ import annotations

from dataclasses import dataclass

from auth_app.models import Currency, UserCurrencyPreference


@dataclass(frozen=True)
class CurrencyOption:
    """Currency option for templates and lightweight service responses."""

    code: str
    name: str
    symbol: str = ""


@dataclass(frozen=True)
class DisplayCurrencyContext:
    """Normalized active/display currency state for one user."""

    active_currencies: list[CurrencyOption]
    selected_currency: str


DEFAULT_DISPLAY_CURRENCY = "EGP"


def get_supported_currencies() -> list[CurrencyOption]:
    """Return all enabled currencies in display order."""
    rows = Currency.objects.filter(is_enabled=True).order_by("display_order", "code")
    return [
        CurrencyOption(code=row.code, name=row.name, symbol=row.symbol or "")
        for row in rows
    ]


def _normalize_codes(codes: list[str] | tuple[str, ...] | set[str]) -> list[str]:
    """Normalize and deduplicate a currency code collection."""
    seen: set[str] = set()
    normalized: list[str] = []
    enabled_codes = {c.code for c in get_supported_currencies()}
    for raw_code in codes:
        code = str(raw_code).upper().strip()
        if not code or code in seen or code not in enabled_codes:
            continue
        normalized.append(code)
        seen.add(code)
    return normalized


def get_or_create_user_currency_preferences(user_id: str) -> UserCurrencyPreference:
    """Fetch currency preferences, creating a safe default row if missing."""
    prefs, _ = UserCurrencyPreference.objects.get_or_create(
        user_id=user_id,
        defaults={
            "active_currency_codes": [DEFAULT_DISPLAY_CURRENCY],
            "selected_display_currency": DEFAULT_DISPLAY_CURRENCY,
        },
    )
    changed = False
    active_codes = _normalize_codes(list(prefs.active_currency_codes or []))
    if not active_codes:
        active_codes = [DEFAULT_DISPLAY_CURRENCY]
        changed = True
    selected = str(prefs.selected_display_currency or DEFAULT_DISPLAY_CURRENCY).upper()
    if selected not in active_codes:
        selected = active_codes[0]
        changed = True
    if changed:
        prefs.active_currency_codes = active_codes
        prefs.selected_display_currency = selected
        prefs.save(
            update_fields=[
                "active_currency_codes",
                "selected_display_currency",
                "updated_at",
            ]
        )
    return prefs


def get_user_active_currency_codes(user_id: str) -> list[str]:
    """Return the user's active currency codes."""
    return list(get_or_create_user_currency_preferences(user_id).active_currency_codes)


def get_user_active_currencies(user_id: str) -> list[CurrencyOption]:
    """Return active currencies as ordered option objects."""
    by_code = {currency.code: currency for currency in get_supported_currencies()}
    codes = get_user_active_currency_codes(user_id)
    return [by_code[code] for code in codes if code in by_code]


def get_user_display_currency_context(user_id: str) -> DisplayCurrencyContext:
    """Return the canonical effective display-currency state for a user."""
    prefs = get_or_create_user_currency_preferences(user_id)
    supported_by_code = {
        currency.code: currency for currency in get_supported_currencies()
    }
    active_currencies = [
        supported_by_code.get(code, CurrencyOption(code=code, name=code))
        for code in prefs.active_currency_codes
    ]
    selected_currency = prefs.selected_display_currency
    return DisplayCurrencyContext(
        active_currencies=active_currencies,
        selected_currency=selected_currency,
    )


def get_user_selected_display_currency(user_id: str) -> str:
    """Return the user's selected display currency."""
    return get_user_display_currency_context(user_id).selected_currency


def resolve_user_currency_choice(user_id: str, currency_code: str | None) -> str:
    """Resolve a user-selectable currency choice to an active currency code."""
    code = str(currency_code or "").upper().strip()
    context = get_user_display_currency_context(user_id)
    if code:
        active_codes = [currency.code for currency in context.active_currencies]
        if code not in active_codes:
            raise ValueError(f"Invalid currency: {code}")
        return code
    return context.selected_currency


def set_user_active_currencies(
    user_id: str, codes: list[str]
) -> UserCurrencyPreference:
    """Replace the user's active currencies, enforcing at least one active code."""
    normalized = _normalize_codes(codes)
    if not normalized:
        raise ValueError("Select at least one currency")
    prefs = get_or_create_user_currency_preferences(user_id)
    prefs.active_currency_codes = normalized
    if prefs.selected_display_currency not in normalized:
        prefs.selected_display_currency = normalized[0]
    prefs.save(
        update_fields=[
            "active_currency_codes",
            "selected_display_currency",
            "updated_at",
        ]
    )
    return prefs


def set_user_selected_display_currency(
    user_id: str, currency_code: str
) -> UserCurrencyPreference:
    """Set the user's selected display currency."""
    code = str(currency_code).upper().strip()
    prefs = get_or_create_user_currency_preferences(user_id)
    active_codes = list(prefs.active_currency_codes or [])
    if code not in active_codes:
        raise ValueError("Selected currency must be active")
    prefs.selected_display_currency = code
    prefs.save(update_fields=["selected_display_currency", "updated_at"])
    return prefs
