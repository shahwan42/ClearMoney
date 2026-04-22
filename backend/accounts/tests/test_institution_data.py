"""
Tests for accounts/institution_data.py — static preset lists for banks, fintechs, wallets.

All tests are pure (no DB required).
"""

import os

from django.conf import settings

from accounts.institution_data import (
    EGYPTIAN_BANKS,
    EGYPTIAN_FINTECHS,
    WALLET_EXAMPLES,
    get_display_name,
)
from core.templatetags.money import is_image_icon


class TestInstitutionPresets:
    """Static preset lists are well-formed."""

    def test_banks_have_required_fields(self) -> None:
        for bank in EGYPTIAN_BANKS:
            assert "name" in bank
            assert "icon" in bank
            assert "color" in bank
            assert bank["color"].startswith("#")
            assert bank["icon"].endswith((".png", ".svg"))

    def test_fintechs_have_required_fields(self) -> None:
        for fintech in EGYPTIAN_FINTECHS:
            assert "name" in fintech
            assert "icon" in fintech
            assert "color" in fintech
            assert fintech["icon"].endswith((".png", ".svg"))

    def test_wallets_have_required_fields(self) -> None:
        for wallet in WALLET_EXAMPLES:
            assert "name" in wallet
            assert "icon" in wallet
            assert "color" in wallet
            assert "group" in wallet
            assert wallet["group"] in ("physical", "digital")

    def test_no_duplicate_bank_names(self) -> None:
        names = [b["name"] for b in EGYPTIAN_BANKS]
        assert len(names) == len(set(names))

    def test_no_duplicate_fintech_names(self) -> None:
        names = [f["name"] for f in EGYPTIAN_FINTECHS]
        assert len(names) == len(set(names))

    def test_no_duplicate_wallet_names(self) -> None:
        names = [w["name"] for w in WALLET_EXAMPLES]
        assert len(names) == len(set(names))

    def test_physical_wallets_use_emoji(self) -> None:
        for wallet in WALLET_EXAMPLES:
            if wallet["group"] == "physical":
                assert not is_image_icon(wallet["icon"])

    def test_digital_wallets_use_image_icon(self) -> None:
        for wallet in WALLET_EXAMPLES:
            if wallet["group"] == "digital":
                assert is_image_icon(wallet["icon"])

    def test_wallets_have_both_groups(self) -> None:
        groups = {w["group"] for w in WALLET_EXAMPLES}
        assert "physical" in groups
        assert "digital" in groups

    def test_banks_not_empty(self) -> None:
        assert len(EGYPTIAN_BANKS) >= 5

    def test_fintechs_not_empty(self) -> None:
        assert len(EGYPTIAN_FINTECHS) >= 3

    def test_all_image_icons_exist_on_disk(self) -> None:
        """Every .png/.svg icon referenced in presets must exist in static/img/institutions/."""
        # Look in STATICFILES_DIRS (source), not STATIC_ROOT (collected output)
        icon_dir: str | None = None
        for static_dir in settings.STATICFILES_DIRS:
            candidate = os.path.join(str(static_dir), "img", "institutions")
            if os.path.isdir(candidate):
                icon_dir = candidate
                break

        assert icon_dir is not None, (
            f"static/img/institutions/ not found in STATICFILES_DIRS: {settings.STATICFILES_DIRS}"
        )

        all_presets = EGYPTIAN_BANKS + EGYPTIAN_FINTECHS + WALLET_EXAMPLES
        for preset in all_presets:
            if is_image_icon(preset["icon"]):
                path = os.path.join(icon_dir, preset["icon"])
                assert os.path.exists(path), f"Missing icon file: {path}"


class TestGetDisplayName:
    """get_display_name() resolves stored abbreviations to full display names."""

    def test_preset_returns_full_name(self) -> None:
        """Known preset abbreviation returns the full 'ABBR - Full Name' string."""
        assert get_display_name("CIB") == "CIB - Commercial International Bank"

    def test_custom_name_passes_through(self) -> None:
        """Non-preset names are returned as-is (custom institutions)."""
        assert get_display_name("My Custom Bank") == "My Custom Bank"

    def test_empty_string(self) -> None:
        """Empty string is not a preset — returned unchanged."""
        assert get_display_name("") == ""


class TestIsImageIcon:
    """is_image_icon() distinguishes filenames from emojis."""

    def test_png_is_image(self) -> None:
        assert is_image_icon("cib.png") is True

    def test_svg_is_image(self) -> None:
        assert is_image_icon("telda.svg") is True

    def test_emoji_is_not_image(self) -> None:
        assert is_image_icon("👛") is False

    def test_empty_string_is_not_image(self) -> None:
        assert is_image_icon("") is False
