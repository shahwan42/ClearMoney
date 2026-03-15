// charts.go — CSS-only chart components (no JavaScript charting libraries).
//
// These are the building blocks for all data visualization in ClearMoney.
// Instead of pulling in a JS charting library (Chart.js, ApexCharts), we use
// pure CSS and SVG techniques that work without any client-side JavaScript:
//
//   - CSS conic-gradient() for donut/pie charts (browser renders colored arc segments)
//   - CSS flexbox + height percentages for bar charts
//   - Inline SVG <polyline> for sparklines (mini line charts)
//   - Unicode arrows + color classes for trend indicators (up/down arrows)
//
// Think of this like a set of Blade components (@component('chart-donut', ...))
// or Django template tags ({% donut_chart segments %}) — reusable partials
// that accept data and render self-contained chart HTML.
//
// The data flow is: Handler computes chart data structs -> passes to template ->
// template calls functions like {{conicGradient .Segments}} to generate CSS.
//
// Why CSS-only charts?
//   - Zero JavaScript dependencies = faster page loads
//   - Works with HTMX partial updates (no chart library reinitialization needed)
//   - Accessible and progressively enhanced
//   - Lightweight enough for a PWA on mobile
//
// See: https://developer.mozilla.org/en-US/docs/Web/CSS/gradient/conic-gradient
// See: https://developer.mozilla.org/en-US/docs/Web/SVG/Element/polyline
package handler

import (
	"fmt"
	"html/template"
	"math"
	"strings"

	"github.com/shahwan42/clearmoney/internal/models"
)

// --- Chart Data Types ---
// These structs are "ViewModels" — they shape data for chart template partials.
// Handlers compute these from service data and pass them to templates via
// {{template "chart-donut" .DonutData}}.
//
// ChartSegment is defined in models/chart.go (shared between service and handler).

// DonutChartData is passed to the "chart-donut" template partial.
// The donut is rendered as a div with conic-gradient background + white center circle.
type DonutChartData struct {
	Segments []models.ChartSegment // Chart slices (must sum to ~100%)
	CenterLabel string         // Main text in the donut hole (e.g., "45%")
	CenterSub   string         // Secondary label below (e.g., "of budget")
	Small       bool           // If true, renders 64px mini donut instead of 160px
}

// BarGroup represents one column group in a bar chart.
// For a monthly income vs expenses chart, each group is one month.
type BarGroup struct {
	Label string     // X-axis label (e.g., "Jan", "Feb")
	Bars  []BarValue // One or more bars per group (e.g., income + expense)
}

// BarValue represents a single bar within a BarGroup.
// HeightPct is pre-computed by the handler (use ComputeBarHeights helper).
type BarValue struct {
	Value     float64 // Raw numeric value
	HeightPct float64 // 0-100, bar height as percentage of chart area
	Color     string  // CSS color for this bar
	Label     string  // Tooltip/legend label (e.g., "Income")
}

// BarChartData is passed to the "chart-bar" template partial.
type BarChartData struct {
	Groups []BarGroup   // Bar groups (one per x-axis tick)
	Legend []LegendItem // Optional legend entries
}

// LegendItem is a color + label pair for chart legends.
type LegendItem struct {
	Label string
	Color string
}

// SparklineData is passed to the "chart-sparkline" template partial.
// The sparkline is an inline SVG polyline — a mini line chart without axes.
type SparklineData struct {
	Values []float64 // Raw data points to plot
	Color  string    // SVG stroke color (e.g., "#0d9488")
	Width  int       // SVG width in px (0 defaults to 120)
	Height int       // SVG height in px (0 defaults to 40)
}

// TrendData is passed to the "chart-trend" template partial.
// Shows an arrow (▲/▼) with percentage change, colored green or red.
type TrendData struct {
	Change float64 // Signed percentage change (-5.2 or +3.1)
	Label  string  // Context (e.g., "vs last month")
	IsGood bool    // Determines color: true = green, false = red
}

// --- Chart Color Palette ---
// 8 distinct colors that work in both light and dark mode.
// Based on Tailwind's color-600 variants for good contrast on white/dark backgrounds.

var chartPalette = []string{
	"#0d9488", // teal-600    — primary, used for positive values
	"#dc2626", // red-600     — expenses, warnings
	"#2563eb", // blue-600    — informational
	"#d97706", // amber-600   — caution
	"#7c3aed", // violet-600  — categories
	"#059669", // emerald-600 — income, success
	"#db2777", // pink-600    — accent
	"#4f46e5", // indigo-600  — secondary
}

// ChartColor returns a color from the 8-color palette by index.
// Wraps around: index 8 returns the same color as index 0.
// Used by handlers to auto-assign colors to chart segments.
//
// Usage in templates: {{chartColor $index}}
func ChartColor(index int) string {
	if index < 0 {
		index = 0
	}
	return chartPalette[index%len(chartPalette)]
}

// ConicGradient generates a CSS conic-gradient() value from chart segments.
// This is the core of CSS-only donut charts — the browser renders the gradient
// as colored slices in a circle, no Canvas or SVG needed.
//
// Accepts both handler.ChartSegment and service.ChartSegment (or any struct
// with Color and Percentage fields) via the SegmentLike interface.
//
// Example output: "conic-gradient(#0d9488 0.0% 35.2%, #dc2626 35.2% 60.0%, #e2e8f0 60.0% 100.0%)"
//
// Returns template.CSS so Go's html/template won't escape it in style attributes.
func ConicGradient(segments []models.ChartSegment) template.CSS {
	if len(segments) == 0 {
		// Empty state: full gray circle
		return template.CSS("conic-gradient(#e2e8f0 0% 100%)")
	}

	var parts []string
	cumulative := 0.0
	for _, seg := range segments {
		start := cumulative
		end := cumulative + seg.Percentage
		if end > 100 {
			end = 100
		}
		parts = append(parts, fmt.Sprintf("%s %.1f%% %.1f%%", seg.Color, start, end))
		cumulative = end
	}

	// Fill remaining area with light gray (for segments that don't sum to 100%)
	if cumulative < 99.9 {
		parts = append(parts, fmt.Sprintf("#e2e8f0 %.1f%% 100%%", cumulative))
	}

	return template.CSS("conic-gradient(" + strings.Join(parts, ", ") + ")")
}

// SparklinePoints converts a series of numeric values into SVG polyline points.
// Values are normalized to fit within a viewBox of "0 0 100 40".
//
// This is how we create mini line charts (sparklines) without JavaScript —
// just an SVG <polyline> element with computed coordinate pairs.
//
// Example: [100, 150, 120, 200] → "0.0,30.0 33.3,12.0 66.7,22.8 100.0,2.0"
func SparklinePoints(values []float64) string {
	n := len(values)
	if n == 0 {
		return ""
	}
	// Single value: draw a flat horizontal line in the middle
	if n == 1 {
		return "0,20 100,20"
	}

	// Find min and max for normalization (like sklearn's MinMaxScaler)
	minV, maxV := values[0], values[0]
	for _, v := range values[1:] {
		if v < minV {
			minV = v
		}
		if v > maxV {
			maxV = v
		}
	}
	span := maxV - minV
	if span == 0 {
		// All values are equal: flat line in the middle
		span = 1
	}

	// Convert each value to x,y coordinates within the "0 0 100 40" viewBox.
	// X: evenly spaced from 0 to 100 (like numpy.linspace)
	// Y: normalized to 2-38 range (2px padding top/bottom within 40px height)
	//    Lower Y = higher on screen (SVG y-axis is inverted)
	var pts []string
	for i, v := range values {
		x := float64(i) / float64(n-1) * 100
		y := 38 - ((v - minV) / span * 36) // 38=bottom, 36=usable height
		pts = append(pts, fmt.Sprintf("%.1f,%.1f", x, y))
	}
	return strings.Join(pts, " ")
}

// BarStyle generates a safe CSS style string for a bar chart bar.
// Returns template.CSS so Go's html/template won't escape it.
//
// Usage in templates: style="{{barStyle .HeightPct .Color}}"
func BarStyle(heightPct float64, color string) template.CSS {
	return template.CSS(fmt.Sprintf("height:%.1f%%;background-color:%s", heightPct, color))
}

// AbsFloat returns the absolute value of a float64.
// Used in templates to display positive numbers for trend indicators
// (e.g., show "5.2%" instead of "-5.2%" next to a ▼ arrow).
func AbsFloat(v float64) float64 {
	return math.Abs(v)
}

// ComputeBarHeights calculates HeightPct for all bars in a chart relative
// to the maximum value. This normalizes bars so the tallest is 100%.
//
// Call this in the handler before passing BarChartData to the template:
//
//	groups := []BarGroup{...}
//	ComputeBarHeights(groups)
func ComputeBarHeights(groups []BarGroup) {
	maxVal := 0.0
	for _, g := range groups {
		for _, b := range g.Bars {
			if b.Value > maxVal {
				maxVal = b.Value
			}
		}
	}
	if maxVal == 0 {
		return
	}
	for i := range groups {
		for j := range groups[i].Bars {
			groups[i].Bars[j].HeightPct = groups[i].Bars[j].Value / maxVal * 100
		}
	}
}

// ChartFuncs returns template functions for chart rendering.
// These are merged into the global TemplateFuncs map so all templates can use them.
//
// In Laravel terms, these are like custom Blade directives registered in AppServiceProvider:
//   Blade::directive('conicGradient', function ($expression) { ... });
//
// In Django terms, these are like custom template filters in a templatetags module:
//   @register.filter
//   def conic_gradient(segments): ...
//
// These functions return template.CSS (a special type that tells Go's html/template
// to NOT escape the output). Without template.CSS, Go would HTML-escape the CSS
// and break style attributes. This is similar to Laravel's {!! $html !!} (unescaped)
// vs {{ $html }} (escaped).
// See: https://pkg.go.dev/html/template#CSS
func ChartFuncs() template.FuncMap {
	return template.FuncMap{
		// conicGradient generates a CSS conic-gradient from chart segments.
		// Usage in templates: style="background: {{conicGradient .Segments}}"
		"conicGradient": ConicGradient,

		// sparklinePoints converts numeric values to SVG polyline coordinate string.
		// Usage: <polyline points="{{sparklinePoints .Values}}" />
		"sparklinePoints": SparklinePoints,

		// chartColor returns a color from the 8-color palette by index.
		// Usage: {{chartColor $index}} or style="color: {{chartColor 0}}"
		"chartColor": ChartColor,

		// barStyle generates safe CSS for a bar element (height + color).
		// Usage: style="{{barStyle .HeightPct .Color}}"
		"barStyle": BarStyle,

		// abs returns the absolute value of a float64.
		// Usage: {{printf "%.1f" (abs .Change)}}%
		"abs": AbsFloat,
	}
}
