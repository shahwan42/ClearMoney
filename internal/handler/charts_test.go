// charts_test.go — Unit tests for CSS-only chart helper functions.
//
// These tests verify that chart functions produce correct CSS/SVG output.
// They are pure unit tests (no database, no HTTP) — testing mathematical
// and string-formatting logic only.
//
// Go testing patterns for Laravel/Django developers:
//
//   Table-driven tests: Go convention for testing multiple inputs/outputs.
//   Instead of separate test methods per case (like PHPUnit's @dataProvider),
//   Go uses a slice of test structs in a loop:
//     tests := []struct{ input int; expected string }{ {1, "a"}, {2, "b"} }
//     for _, tt := range tests { ... }
//
//   t.Errorf vs t.Fatalf:
//     t.Errorf logs the error but continues running the test (like PHPUnit's assertEquals)
//     t.Fatalf logs the error and stops the test immediately (like PHPUnit's assertSame with early exit)
//
// See: https://pkg.go.dev/testing
package handler

import (
	"html/template"
	"strings"
	"testing"
	"time"

	"github.com/shahwan42/clearmoney/internal/models"
	"github.com/shahwan42/clearmoney/internal/templates"
)

// --- ConicGradient Tests ---
// ConicGradient generates CSS conic-gradient strings for donut charts.
// These tests verify correct segment positioning, gap fills, and overflow handling.

func TestConicGradient_Empty(t *testing.T) {
	result := ConicGradient(nil)
	expected := template.CSS("conic-gradient(#e2e8f0 0% 100%)")
	if result != expected {
		t.Errorf("empty segments:\n  got  %q\n  want %q", result, expected)
	}
}

func TestConicGradient_SingleSegment(t *testing.T) {
	segments := []models.ChartSegment{
		{Label: "Groceries", Amount: 1500, Percentage: 45.0, Color: "#0d9488"},
	}
	result := string(ConicGradient(segments))
	// Should have the teal segment from 0-45%, then gray fill from 45-100%
	if !strings.Contains(result, "#0d9488 0.0% 45.0%") {
		t.Errorf("missing teal segment in: %s", result)
	}
	if !strings.Contains(result, "#e2e8f0 45.0% 100%") {
		t.Errorf("missing gray fill in: %s", result)
	}
}

func TestConicGradient_MultipleSegments(t *testing.T) {
	segments := []models.ChartSegment{
		{Color: "#0d9488", Percentage: 60.0},
		{Color: "#dc2626", Percentage: 40.0},
	}
	result := string(ConicGradient(segments))
	expected := "conic-gradient(#0d9488 0.0% 60.0%, #dc2626 60.0% 100.0%)"
	if result != expected {
		t.Errorf("two segments:\n  got  %q\n  want %q", result, expected)
	}
}

func TestConicGradient_OverflowCappedAt100(t *testing.T) {
	segments := []models.ChartSegment{
		{Color: "#0d9488", Percentage: 70.0},
		{Color: "#dc2626", Percentage: 50.0}, // would overflow to 120%
	}
	result := string(ConicGradient(segments))
	// Second segment should be capped at 100%
	if !strings.Contains(result, "#dc2626 70.0% 100.0%") {
		t.Errorf("expected second segment capped at 100%%, got: %s", result)
	}
}

// --- SparklinePoints Tests ---

func TestSparklinePoints_Empty(t *testing.T) {
	result := SparklinePoints(nil)
	if result != "" {
		t.Errorf("empty values: got %q, want empty string", result)
	}
}

func TestSparklinePoints_SingleValue(t *testing.T) {
	result := SparklinePoints([]float64{100})
	if result != "0,20 100,20" {
		t.Errorf("single value: got %q, want %q", result, "0,20 100,20")
	}
}

func TestSparklinePoints_TwoValues_MinMax(t *testing.T) {
	result := SparklinePoints([]float64{0, 100})
	// 0 should be at bottom (y=38), 100 at top (y=2)
	expected := "0.0,38.0 100.0,2.0"
	if result != expected {
		t.Errorf("min→max:\n  got  %q\n  want %q", result, expected)
	}
}

func TestSparklinePoints_AllEqual(t *testing.T) {
	result := SparklinePoints([]float64{50, 50, 50})
	// All equal values: should be a flat line (same Y for all points)
	parts := strings.Split(result, " ")
	if len(parts) != 3 {
		t.Fatalf("expected 3 points, got %d", len(parts))
	}
	// All Y values should be the same
	y1 := strings.Split(parts[0], ",")[1]
	y2 := strings.Split(parts[1], ",")[1]
	y3 := strings.Split(parts[2], ",")[1]
	if y1 != y2 || y2 != y3 {
		t.Errorf("all-equal values should produce flat line, got Y values: %s, %s, %s", y1, y2, y3)
	}
}

func TestSparklinePoints_MultipleValues(t *testing.T) {
	values := []float64{10, 20, 15, 25, 5}
	result := SparklinePoints(values)
	parts := strings.Split(result, " ")
	if len(parts) != 5 {
		t.Fatalf("expected 5 points, got %d: %q", len(parts), result)
	}
	// First point X should be 0, last should be 100
	if !strings.HasPrefix(parts[0], "0.0,") {
		t.Errorf("first point should start at X=0, got %q", parts[0])
	}
	if !strings.HasPrefix(parts[4], "100.0,") {
		t.Errorf("last point should be at X=100, got %q", parts[4])
	}
}

// --- ChartColor Tests ---

func TestChartColor_ValidIndices(t *testing.T) {
	// First color should be teal-600
	if ChartColor(0) != "#0d9488" {
		t.Errorf("index 0: got %q, want #0d9488", ChartColor(0))
	}
	// Second color should be red-600
	if ChartColor(1) != "#dc2626" {
		t.Errorf("index 1: got %q, want #dc2626", ChartColor(1))
	}
}

func TestChartColor_Wraps(t *testing.T) {
	// Index 8 should wrap to index 0 (palette has 8 colors)
	if ChartColor(8) != ChartColor(0) {
		t.Errorf("expected wrap: color(8)=%q, color(0)=%q", ChartColor(8), ChartColor(0))
	}
}

func TestChartColor_NegativeIndex(t *testing.T) {
	// Negative index should not panic, returns first color
	if ChartColor(-1) != "#0d9488" {
		t.Errorf("negative index: got %q, want #0d9488", ChartColor(-1))
	}
}

// --- BarStyle Tests ---

func TestBarStyle_Output(t *testing.T) {
	result := BarStyle(75.5, "#0d9488")
	expected := template.CSS("height:75.5%;background-color:#0d9488")
	if result != expected {
		t.Errorf("barStyle:\n  got  %q\n  want %q", result, expected)
	}
}

func TestBarStyle_Zero(t *testing.T) {
	result := BarStyle(0, "#dc2626")
	expected := template.CSS("height:0.0%;background-color:#dc2626")
	if result != expected {
		t.Errorf("barStyle zero:\n  got  %q\n  want %q", result, expected)
	}
}

// --- AbsFloat Tests ---

func TestAbsFloat(t *testing.T) {
	tests := []struct {
		input    float64
		expected float64
	}{
		{5.2, 5.2},
		{-5.2, 5.2},
		{0, 0},
		{-0.001, 0.001},
	}
	for _, tt := range tests {
		got := AbsFloat(tt.input)
		if got != tt.expected {
			t.Errorf("abs(%f) = %f, want %f", tt.input, got, tt.expected)
		}
	}
}

// --- ComputeBarHeights Tests ---

func TestComputeBarHeights_Normal(t *testing.T) {
	groups := []BarGroup{
		{Label: "Jan", Bars: []BarValue{{Value: 1000, Color: "#0d9488"}}},
		{Label: "Feb", Bars: []BarValue{{Value: 500, Color: "#0d9488"}}},
	}
	ComputeBarHeights(groups)
	if groups[0].Bars[0].HeightPct != 100 {
		t.Errorf("max bar should be 100%%, got %.1f%%", groups[0].Bars[0].HeightPct)
	}
	if groups[1].Bars[0].HeightPct != 50 {
		t.Errorf("half bar should be 50%%, got %.1f%%", groups[1].Bars[0].HeightPct)
	}
}

func TestComputeBarHeights_AllZero(t *testing.T) {
	groups := []BarGroup{
		{Label: "Jan", Bars: []BarValue{{Value: 0}}},
	}
	ComputeBarHeights(groups)
	// All zeros: heights should remain 0 (no division by zero)
	if groups[0].Bars[0].HeightPct != 0 {
		t.Errorf("zero bar should be 0%%, got %.1f%%", groups[0].Bars[0].HeightPct)
	}
}

// --- Template Parsing Test ---
// Verify all chart partials parse without errors when included in the template set.
// This is an integration-level check: it ensures chart template partials are valid
// Go template syntax and can be loaded alongside all other templates.

func TestChartTemplates_Parse(t *testing.T) {
	_, err := ParseTemplates(templates.FS, time.UTC)
	if err != nil {
		t.Fatalf("chart templates failed to parse: %v", err)
	}
}
