// Package models — chart.go defines shared chart data types used across
// service and handler layers.
//
// These types are "ViewModels" (or DTOs — Data Transfer Objects) that shape data
// specifically for CSS-only chart rendering in templates. They don't correspond to
// any database table — they're computed in the service layer and consumed by
// template functions.
//
// Why are these in models/ instead of handler/?
// Go enforces a strict rule: no circular imports. If these lived in the handler
// package, the service package couldn't reference them (service -> handler is not
// allowed because handler already imports service). By placing shared types in
// models/, both service and handler can import them freely.
//
// Laravel analogy: These are like API Resources or View Composers — they transform
// raw data into a shape that's convenient for the view layer.
//
// Django analogy: Similar to serializer classes or context data dictionaries that
// you'd build in a view and pass to a template. No database backing, just structured
// data for rendering.
//
// See: https://go.dev/doc/faq#no_circular_imports for why Go prohibits circular imports
package models

// ChartSegment represents one slice of a donut/pie chart.
// Used by reports (spending by category) and credit card utilization.
//
// The template layer uses these fields to generate CSS conic-gradient() values:
//   - Percentage determines the arc size of each slice
//   - Color is the CSS color for that slice
//   - Label and Amount are displayed in the chart legend
//
// Note: No struct tags (json/db) because this type is never serialized to JSON
// or read from the database. It's purely an in-memory ViewModel.
type ChartSegment struct {
	Label      string  // Display name (e.g., "Groceries", "Used")
	Amount     float64 // Raw amount for legend display (e.g., 3500.00)
	Percentage float64 // 0-100, determines slice size in CSS conic-gradient
	Color      string  // CSS color value (hex like "#0d9488" or named like "teal")
}
