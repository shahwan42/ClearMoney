// Tests for timezone-aware time functions.
//
// Verifies that Now() returns UTC, Today/MonthStart/MonthEnd respect the user's
// timezone (Africa/Cairo = UTC+2), ParseDateInTZ interprets date strings in the
// user's local timezone, and InUserTZ converts UTC times for display.
//
// These tests are critical because ClearMoney stores all times in UTC but
// displays them in the user's timezone — similar to Django's USE_TZ=True.
package timeutil

import (
	"testing"
	"time"
)

func TestNow_ReturnsUTC(t *testing.T) {
	now := Now()
	if now.Location() != time.UTC {
		t.Errorf("Now() returned location %v, want UTC", now.Location())
	}
}

func TestToday_CairoTimezone(t *testing.T) {
	cairo, err := time.LoadLocation("Africa/Cairo")
	if err != nil {
		t.Fatalf("failed to load Cairo timezone: %v", err)
	}

	today := Today(cairo)

	// Result should be in UTC
	if today.Location() != time.UTC {
		t.Errorf("Today() returned location %v, want UTC", today.Location())
	}

	// When converted back to Cairo, should be midnight
	inCairo := today.In(cairo)
	if inCairo.Hour() != 0 || inCairo.Minute() != 0 || inCairo.Second() != 0 {
		t.Errorf("Today() in Cairo = %v, want midnight", inCairo)
	}
}

func TestMonthStart(t *testing.T) {
	cairo, _ := time.LoadLocation("Africa/Cairo")

	// March 15, 2026 in Cairo
	input := time.Date(2026, 3, 15, 14, 30, 0, 0, cairo)
	start := MonthStart(input, cairo)

	// Should be March 1 midnight Cairo = Feb 28 22:00 UTC (Cairo is UTC+2)
	inCairo := start.In(cairo)
	if inCairo.Year() != 2026 || inCairo.Month() != 3 || inCairo.Day() != 1 {
		t.Errorf("MonthStart = %v in Cairo, want 2026-03-01", inCairo)
	}
	if inCairo.Hour() != 0 || inCairo.Minute() != 0 {
		t.Errorf("MonthStart time = %v, want midnight", inCairo)
	}
	if start.Location() != time.UTC {
		t.Errorf("MonthStart location = %v, want UTC", start.Location())
	}
}

func TestMonthEnd(t *testing.T) {
	cairo, _ := time.LoadLocation("Africa/Cairo")

	// March 15, 2026 in Cairo
	input := time.Date(2026, 3, 15, 14, 30, 0, 0, cairo)
	end := MonthEnd(input, cairo)

	// Should be April 1 midnight Cairo
	inCairo := end.In(cairo)
	if inCairo.Year() != 2026 || inCairo.Month() != 4 || inCairo.Day() != 1 {
		t.Errorf("MonthEnd = %v in Cairo, want 2026-04-01", inCairo)
	}
	if end.Location() != time.UTC {
		t.Errorf("MonthEnd location = %v, want UTC", end.Location())
	}
}

func TestMonthEnd_DecemberWrapsToJanuary(t *testing.T) {
	cairo, _ := time.LoadLocation("Africa/Cairo")

	// December 2026
	input := time.Date(2026, 12, 15, 0, 0, 0, 0, cairo)
	end := MonthEnd(input, cairo)

	inCairo := end.In(cairo)
	if inCairo.Year() != 2027 || inCairo.Month() != 1 || inCairo.Day() != 1 {
		t.Errorf("MonthEnd for December = %v in Cairo, want 2027-01-01", inCairo)
	}
}

func TestParseDateInTZ(t *testing.T) {
	cairo, _ := time.LoadLocation("Africa/Cairo")

	parsed, err := ParseDateInTZ("2026-03-15", cairo)
	if err != nil {
		t.Fatalf("ParseDateInTZ failed: %v", err)
	}

	// Should be in UTC
	if parsed.Location() != time.UTC {
		t.Errorf("ParseDateInTZ location = %v, want UTC", parsed.Location())
	}

	// When converted to Cairo, should be March 15 midnight
	inCairo := parsed.In(cairo)
	if inCairo.Year() != 2026 || inCairo.Month() != 3 || inCairo.Day() != 15 {
		t.Errorf("ParseDateInTZ = %v in Cairo, want 2026-03-15", inCairo)
	}
	if inCairo.Hour() != 0 {
		t.Errorf("ParseDateInTZ hour = %d, want 0", inCairo.Hour())
	}

	// UTC time should be 22:00 on March 14 (Cairo is UTC+2)
	if parsed.Hour() != 22 || parsed.Day() != 14 {
		t.Errorf("ParseDateInTZ UTC = %v, want 2026-03-14T22:00:00Z", parsed)
	}
}

func TestParseDateInTZ_InvalidInput(t *testing.T) {
	cairo, _ := time.LoadLocation("Africa/Cairo")

	_, err := ParseDateInTZ("not-a-date", cairo)
	if err == nil {
		t.Error("ParseDateInTZ should return error for invalid input")
	}
}

func TestInUserTZ(t *testing.T) {
	cairo, _ := time.LoadLocation("Africa/Cairo")

	// 22:00 UTC = midnight Cairo (next day)
	utcTime := time.Date(2026, 3, 14, 22, 0, 0, 0, time.UTC)
	local := InUserTZ(utcTime, cairo)

	if local.Day() != 15 || local.Month() != 3 || local.Hour() != 0 {
		t.Errorf("InUserTZ = %v, want 2026-03-15 00:00 Cairo", local)
	}
}

func TestLoadLocation_Valid(t *testing.T) {
	loc := LoadLocation("Africa/Cairo")
	if loc.String() != "Africa/Cairo" {
		t.Errorf("LoadLocation = %v, want Africa/Cairo", loc)
	}
}

func TestLoadLocation_Invalid_FallsBackToUTC(t *testing.T) {
	loc := LoadLocation("Invalid/Timezone")
	if loc != time.UTC {
		t.Errorf("LoadLocation invalid = %v, want UTC", loc)
	}
}
