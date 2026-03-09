// Package models — chart.go defines shared chart data types used across
// service and handler layers.
//
// These types are "ViewModels" that shape data for CSS-only chart rendering.
// They live in models (not handler) so both the service layer (which computes
// chart data) and handler layer (which registers template functions) can use them
// without circular imports.
package models

// ChartSegment represents one slice of a donut/pie chart.
// Used by reports (spending by category) and credit card utilization.
type ChartSegment struct {
	Label      string  // Display name (e.g., "Groceries", "Used")
	Amount     float64 // Raw amount for legend display
	Percentage float64 // 0-100, determines slice size in conic-gradient
	Color      string  // CSS color value (hex like "#0d9488")
}
