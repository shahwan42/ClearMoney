# Charts (CSS-Only)

All charts in ClearMoney are built with CSS and inline SVG — no JavaScript charting libraries. This keeps the bundle tiny and avoids external dependencies.

## Chart Types

### Donut Chart

**Technology:** CSS `conic-gradient()`

**Template:** `backend/reports/templates/reports/partials/chart-donut.html`

```html
<div style="background: {{ segments|conic_gradient }}">
    <div class="chart-donut-hole">
        <span>{{ center_label }}</span>
    </div>
</div>
```

**Template Filter:** `conic_gradient` in `backend/core/templatetags/money.py`

- Input: list of `ChartSegment` (color + percentage)
- Output: CSS string like `"conic-gradient(#0d9488 0.0% 35.2%, #dc2626 35.2% 60.0%, #e2e8f0 60.0% 100.0%)"`
- Fills remaining space with light gray (#e2e8f0)

**CSS:** `static/css/charts.css` (lines ~14-73)
- `.chart-donut` — 160px circle with conic-gradient background
- `.chart-donut-hole` — white 60% center with flexed content
- `.chart-donut-sm` — 64px mini variant
- Dark mode: hole becomes slate-800

**Used in:** Reports (spending by category), Credit card utilization

### Bar Chart

**Technology:** CSS flexbox with proportional heights

**Template:** `backend/reports/templates/reports/partials/chart-bar.html`

```html
<div style="{{ bar|bar_style }}"></div>
```

**Template Filter:** `bar_style` in `backend/core/templatetags/money.py`

- Input: height percentage (0-100) and color hex
- Output: CSS string like `"height:75.5%;background-color:#0d9488"`

Heights are normalized to 0-100 relative to the maximum value across all months.

**CSS:** `static/css/charts.css` (lines ~75-125)
- `.chart-bar-area` — flex container with 160px height, align-end
- `.chart-bar-group` — flex group per x-axis tick
- `.chart-bar` — rounded top, hover opacity
- Labels below in `.chart-bar-labels`

**Used in:** Reports (6-month income vs expenses)

### Sparkline

**Technology:** Inline SVG `<polyline>` + `<polygon>`

**Template:** `backend/templates/components/chart-sparkline.html`

```html
<svg viewBox="0 0 {{ width }} {{ height }}">
    <polygon points="0,{{ height }} {{ values|sparkline_points }} {{ width }},{{ height }}" />
    <polyline points="{{ values|sparkline_points }}" />
</svg>
```

**Template Filter:** `sparkline_points` in `backend/core/templatetags/money.py`

- Input: list of numeric values
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

Shows `▲ +5.2%` (green) or `▼ -3.1%` (red) based on percentage change. Color determined by `IsGood` flag (context-dependent — spending increase is bad, balance increase is good).

**Used in:** Dashboard (net worth change, spending change, category changes)

### Credit Card Utilization Ring

**Technology:** SVG circle with `stroke-dasharray`

Two `<circle>` elements:
1. Background gray circle (full circumference)
2. Foreground colored circle (partial, based on utilization %)

```html
<circle stroke-dasharray="{{ utilization_pct }}, 100" />
```

Color thresholds: green (<50%), amber (50-80%), red (>80%)

**Used in:** Dashboard (mini CC rings), Account detail (larger donut)

## Color Palette

**File:** `backend/core/templatetags/money.py` — `chart_color` filter

8-color palette that cycles:
1. `#0d9488` — teal
2. `#dc2626` — red
3. `#2563eb` — blue
4. `#d97706` — amber
5. `#7c3aed` — violet
6. `#059669` — emerald
7. `#db2777` — pink
8. `#4f46e5` — indigo

`chart_color(index)` wraps via modulo: `palette[index % 8]`

## Template Filters

All defined in `backend/core/templatetags/money.py`:

| Filter | Signature | Purpose |
| ------ | --------- | ------- |
| `conic_gradient` | `list[ChartSegment] → str` | Donut background CSS |
| `bar_style` | `(float, str) → str` | Bar height + color CSS |
| `chart_color` | `int → str` | Color from palette by index |

## Dark Mode Support

All charts adapt to dark mode via Tailwind's `dark:` variants and custom CSS overrides:
- Donut hole: white → slate-800
- Text colors: dark → light
- Bar backgrounds: subtle opacity adjustments
- Sparkline strokes: maintained (already use explicit colors)

## Key Files

| File | Purpose |
|------|---------|
| `backend/core/templatetags/money.py` | Template filters: conic_gradient, bar_style, chart_color |
| `backend/reports/templates/reports/partials/chart-donut.html` | Donut chart partial |
| `backend/reports/templates/reports/partials/chart-bar.html` | Bar chart partial |
| `static/css/charts.css` | All chart CSS + dark mode overrides |

## For Newcomers

- **No JavaScript charting** — all charts are pure CSS/SVG. No dependencies, instant rendering.
- **Template filters** — Django template filters in `money.py` handle chart rendering (conic_gradient, bar_style, chart_color).
- **Normalized heights** — bar charts normalize to 0-100 scale. The tallest bar is always 100%.
- **Dark mode** — chart colors are explicit (not Tailwind classes), so dark mode overrides only affect backgrounds and text, not chart colors.
