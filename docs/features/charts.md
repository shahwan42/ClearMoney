# Charts (CSS-Only)

All charts in ClearMoney are built with CSS and inline SVG — no JavaScript charting libraries. This keeps the bundle tiny and avoids external dependencies.

## Chart Types

### Donut Chart

**Technology:** CSS `conic-gradient()`

**Template:** `internal/templates/partials/chart-donut.html`

```html
<div style="background: {{conicGradient .Segments}}">
    <div class="chart-donut-hole">
        <span>{{.CenterLabel}}</span>
    </div>
</div>
```

**Template Function:** `conicGradient()` in `internal/handler/charts.go` (line ~136)
- Input: Array of `ChartSegment` (Color + Percentage)
- Output: `template.CSS` string like `"conic-gradient(#0d9488 0.0% 35.2%, #dc2626 35.2% 60.0%, #e2e8f0 60.0% 100.0%)"`
- Fills remaining space with light gray (#e2e8f0)

**CSS:** `static/css/charts.css` (lines ~14-73)
- `.chart-donut` — 160px circle with conic-gradient background
- `.chart-donut-hole` — white 60% center with flexed content
- `.chart-donut-sm` — 64px mini variant
- Dark mode: hole becomes slate-800

**Used in:** Reports (spending by category), Credit card utilization

### Bar Chart

**Technology:** CSS flexbox with proportional heights

**Template:** `internal/templates/partials/chart-bar.html`

```html
<div style="{{barStyle .HeightPct .Color}}"></div>
```

**Template Function:** `barStyle()` in `charts.go` (line ~212)
- Input: height percentage (0-100), color hex
- Output: `template.CSS` like `"height:75.5%;background-color:#0d9488"`

**Helper:** `ComputeBarHeights()` (line ~230) normalizes all bars relative to max value.

**CSS:** `static/css/charts.css` (lines ~75-125)
- `.chart-bar-area` — flex container with 160px height, align-end
- `.chart-bar-group` — flex group per x-axis tick
- `.chart-bar` — rounded top, hover opacity
- Labels below in `.chart-bar-labels`

**Used in:** Reports (6-month income vs expenses)

### Sparkline

**Technology:** Inline SVG `<polyline>` + `<polygon>`

**Template:** `internal/templates/partials/chart-sparkline.html`

```html
<svg viewBox="0 0 {{.Width}} {{.Height}}">
    <polygon points="0,{{.Height}} {{sparklinePoints .Values}} {{.Width}},{{.Height}}" />
    <polyline points="{{sparklinePoints .Values}}" />
</svg>
```

**Template Function:** `sparklinePoints()` in `charts.go` (line ~169)
- Input: Array of float64 values
- Output: SVG coordinate string like `"0.0,30.0 33.3,12.0 66.7,22.8 100.0,2.0"`
- Normalizes values to viewBox dimensions
- Single value returns flat line; empty returns ""

**CSS:** `static/css/charts.css` (lines ~127-149)
- `.chart-sparkline` — inline-block SVG
- `polyline` — stroke-width 1.5, round joins/caps
- `.sparkline-fill` — polygon with 0.1 opacity fill (shaded area under curve)

**Used in:** Dashboard (net worth 30-day), Account detail (balance 30-day), Dashboard (per-account mini sparklines)

### Trend Indicator

**Technology:** Text with arrow character

**Template:** `internal/templates/partials/chart-trend.html`

Shows `▲ +5.2%` (green) or `▼ -3.1%` (red) based on percentage change. Color determined by `IsGood` flag (context-dependent — spending increase is bad, balance increase is good).

**Used in:** Dashboard (net worth change, spending change, category changes)

### Credit Card Utilization Ring

**Technology:** SVG circle with `stroke-dasharray`

Two `<circle>` elements:
1. Background gray circle (full circumference)
2. Foreground colored circle (partial, based on utilization %)

```html
<circle stroke-dasharray="{{.UtilizationPct}}, 100" />
```

Color thresholds: green (<50%), amber (50-80%), red (>80%)

**Used in:** Dashboard (mini CC rings), Account detail (larger donut)

## Color Palette

**File:** `internal/handler/charts.go` (lines ~103-124)

8-color palette that cycles:
1. `#0d9488` — teal
2. `#dc2626` — red
3. `#2563eb` — blue
4. `#d97706` — amber
5. `#7c3aed` — violet
6. `#059669` — emerald
7. `#db2777` — pink
8. `#4f46e5` — indigo

`ChartColor(index)` wraps via modulo: `palette[index % 8]`

## Template Functions

All registered via `ChartFuncs()` in `charts.go` (line ~264):

| Function | Signature | Purpose |
|----------|-----------|---------|
| `conicGradient` | `[]ChartSegment → template.CSS` | Donut background |
| `sparklinePoints` | `[]float64 → string` | SVG polyline coordinates |
| `chartColor` | `int → string` | Color from palette by index |
| `barStyle` | `(float64, string) → template.CSS` | Bar height + color CSS |
| `absFloat` | `float64 → float64` | Absolute value |

These are merged into the global `TemplateFuncs()` in `templates.go`.

## Dark Mode Support

All charts adapt to dark mode via Tailwind's `dark:` variants and custom CSS overrides:
- Donut hole: white → slate-800
- Text colors: dark → light
- Bar backgrounds: subtle opacity adjustments
- Sparkline strokes: maintained (already use explicit colors)

## Key Files

| File | Purpose |
|------|---------|
| `internal/handler/charts.go` | Template functions + color palette |
| `internal/models/chart.go` | ChartSegment struct |
| `internal/templates/partials/chart-donut.html` | Donut chart partial |
| `internal/templates/partials/chart-bar.html` | Bar chart partial |
| `internal/templates/partials/chart-sparkline.html` | Sparkline partial |
| `internal/templates/partials/chart-trend.html` | Trend arrow partial |
| `static/css/charts.css` | All chart CSS + dark mode overrides |

## For Newcomers

- **No JavaScript charting** — all charts are pure CSS/SVG. This means no dependencies, no bundle size, and instant rendering.
- **`template.CSS` return type** — used for safe CSS injection in templates (Go's html/template normally escapes CSS).
- **Normalized heights** — bar charts normalize to 0-100 scale. The tallest bar is always 100%.
- **Sparkline viewBox** — SVG uses relative coordinates (0-100 x, 0-40 y). The `sparklinePoints` function normalizes any value range to fit.
- **Dark mode** — chart colors are explicit (not Tailwind classes), so dark mode overrides only affect backgrounds and text, not the chart colors themselves.
