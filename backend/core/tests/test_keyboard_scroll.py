"""Tests for keyboard scroll-into-view in bottom sheets."""

from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parent.parent.parent.parent / "static"


class TestKeyboardScrollIntoView:
    """Bottom sheet JS must scroll focused inputs into view for mobile keyboard."""

    def test_bottom_sheet_has_scroll_into_view(self) -> None:
        """bottom-sheet.js must include scrollIntoView for focused inputs."""
        js = (STATIC_DIR / "js" / "bottom-sheet.js").read_text()
        assert "scrollIntoView" in js

    def test_listens_for_focus_events(self) -> None:
        """bottom-sheet.js must listen for focusin events on inputs."""
        js = (STATIC_DIR / "js" / "bottom-sheet.js").read_text()
        assert "focusin" in js
