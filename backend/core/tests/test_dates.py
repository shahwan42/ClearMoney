"""Tests for core.dates month-range utilities."""

from datetime import date

from core.dates import month_range, next_month_range, prev_month_range


class TestMonthRange:
    def test_january(self) -> None:
        result = month_range(date(2024, 1, 15))
        assert result == (date(2024, 1, 1), date(2024, 2, 1))

    def test_non_december(self) -> None:
        result = month_range(date(2024, 6, 20))
        assert result == (date(2024, 6, 1), date(2024, 7, 1))

    def test_december(self) -> None:
        result = month_range(date(2024, 12, 5))
        assert result == (date(2024, 12, 1), date(2025, 1, 1))

    def test_leap_year_february(self) -> None:
        result = month_range(date(2024, 2, 29))
        assert result == (date(2024, 2, 1), date(2024, 3, 1))

    def test_first_day_of_month(self) -> None:
        result = month_range(date(2024, 3, 1))
        assert result == (date(2024, 3, 1), date(2024, 4, 1))


class TestPrevMonthRange:
    def test_january(self) -> None:
        result = prev_month_range(date(2024, 1, 15))
        assert result == (date(2023, 12, 1), date(2024, 1, 1))

    def test_non_january(self) -> None:
        result = prev_month_range(date(2024, 6, 20))
        assert result == (date(2024, 5, 1), date(2024, 6, 1))

    def test_march_leap_year(self) -> None:
        result = prev_month_range(date(2024, 3, 1))
        assert result == (date(2024, 2, 1), date(2024, 3, 1))


class TestNextMonthRange:
    def test_january(self) -> None:
        result = next_month_range(date(2024, 1, 15))
        assert result == (date(2024, 2, 1), date(2024, 3, 1))

    def test_non_december(self) -> None:
        result = next_month_range(date(2024, 6, 20))
        assert result == (date(2024, 7, 1), date(2024, 8, 1))

    def test_december(self) -> None:
        result = next_month_range(date(2024, 12, 5))
        assert result == (date(2025, 1, 1), date(2025, 2, 1))

    def test_november(self) -> None:
        result = next_month_range(date(2024, 11, 15))
        assert result == (date(2024, 12, 1), date(2025, 1, 1))

    def test_february_leap_year(self) -> None:
        result = next_month_range(date(2024, 2, 29))
        assert result == (date(2024, 3, 1), date(2024, 4, 1))
