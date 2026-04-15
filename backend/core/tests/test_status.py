"""Tests for core.status threshold and velocity status helpers."""

from core.status import compute_spending_velocity_status, compute_threshold_status


class TestComputeThresholdStatus:
    def test_below_warning(self) -> None:
        assert compute_threshold_status(0.0, (80.0, 100.0)) == "green"
        assert compute_threshold_status(50.0, (80.0, 100.0)) == "green"
        assert compute_threshold_status(79.9, (80.0, 100.0)) == "green"

    def test_at_warning_threshold(self) -> None:
        assert compute_threshold_status(80.0, (80.0, 100.0)) == "amber"

    def test_between_thresholds(self) -> None:
        assert compute_threshold_status(80.1, (80.0, 100.0)) == "amber"
        assert compute_threshold_status(90.0, (80.0, 100.0)) == "amber"
        assert compute_threshold_status(99.9, (80.0, 100.0)) == "amber"

    def test_at_critical_threshold(self) -> None:
        assert compute_threshold_status(100.0, (80.0, 100.0)) == "red"

    def test_above_critical_threshold(self) -> None:
        assert compute_threshold_status(100.1, (80.0, 100.0)) == "red"
        assert compute_threshold_status(150.0, (80.0, 100.0)) == "red"

    def test_zero_percentage(self) -> None:
        assert compute_threshold_status(0.0, (80.0, 100.0)) == "green"

    def test_custom_thresholds(self) -> None:
        assert compute_threshold_status(49.0, (50.0, 75.0)) == "green"
        assert compute_threshold_status(50.0, (50.0, 75.0)) == "amber"
        assert compute_threshold_status(74.0, (50.0, 75.0)) == "amber"
        assert compute_threshold_status(75.0, (50.0, 75.0)) == "red"


class TestComputeSpendingVelocityStatus:
    def test_under_day_progress(self) -> None:
        assert compute_spending_velocity_status(20.0, 30.0) == "green"
        assert compute_spending_velocity_status(30.0, 30.0) == "green"
        assert compute_spending_velocity_status(0.0, 50.0) == "green"

    def test_at_day_progress_plus_10(self) -> None:
        assert compute_spending_velocity_status(40.0, 30.0) == "amber"

    def test_between_day_progress_and_day_progress_plus_10(self) -> None:
        assert compute_spending_velocity_status(30.1, 30.0) == "amber"
        assert compute_spending_velocity_status(35.0, 30.0) == "amber"
        assert compute_spending_velocity_status(39.9, 30.0) == "amber"

    def test_above_day_progress_plus_10(self) -> None:
        assert compute_spending_velocity_status(40.1, 30.0) == "red"
        assert compute_spending_velocity_status(50.0, 30.0) == "red"
        assert compute_spending_velocity_status(100.0, 30.0) == "red"

    def test_zero_day_progress(self) -> None:
        assert compute_spending_velocity_status(0.0, 0.0) == "green"
        assert compute_spending_velocity_status(5.0, 0.0) == "amber"
        assert compute_spending_velocity_status(15.0, 0.0) == "red"

    def test_end_of_month(self) -> None:
        assert compute_spending_velocity_status(90.0, 95.0) == "green"
        assert compute_spending_velocity_status(100.0, 95.0) == "amber"
        assert compute_spending_velocity_status(110.0, 95.0) == "red"
