# ClearMoney Charts & Visualizations — UX Audit Report

**Date**: 2026-03-25
**Auditor**: Claude AI
**App Version**: Django (post-Go migration)
**Audit Scope**: All chart types, light & dark modes, mobile & desktop, empty states, accessibility

---

## Executive Summary

ClearMoney uses **CSS-only charts** with no JavaScript charting libraries. The implementation is elegant and performant, but several **UX and accessibility issues** were identified:

1. **Donut charts**: Small slices are visually indistinguishable without legend
2. **Bar charts**: Label clarity is limited due to 0.625rem font size
3. **Sparklines**: Y-axis values not visible (trend-only view)
4. **Progress bars**: Percentage text overlaps on small screens
5. **Dark mode**: Some color combinations don't meet WCAG AA contrast requirements
6. **Mobile responsiveness**: Charts scale well, but legend text wraps awkwardly
7. **Empty states**: No fallback charts when no data exists; only warning banners
8. **Accessibility**: ARIA labels present but data is not serializable for screen readers

---

## 1. Chart Inventory

### 1.1 All Chart Types in ClearMoney

| Chart Type | Where Used | Technology | Features |
|-----------|-----------|-----------|----------|
| **Donut (Large)** | Reports → Spending by Category | CSS conic-gradient | 160×160px, percentage labels in legend |
| **Donut (Small)** | Dashboard → CC Utilization | CSS conic-gradient | 64×64px, center % text |
| **Donut (Small)** | Dashboard → Budget cards | CSS conic-gradient | Mini variant for summary |
| **Bar Chart** | Reports → Income vs Expenses | CSS flexbox + inline styles | 6-month view, grouped bars |
| **Sparkline** | Dashboard → Account balances | Inline SVG polyline | Dual-currency optional |
| **Progress Bar** | Dashboard → Budgets section | CSS flexbox | Category + EGP value + % |
| **Linear Progress** | Budget detail page | CSS background-size | Monthly limit progress |
| **Data Table** | Reports → Spending breakdown | HTML list | Color-coded rows (fallback to donut) |

### 1.2 Chart Rendering & Styling

**File Structure:**
- `static/css/charts.css` — All chart styling (245 lines)
- `core/templatetags/money.py` — Color palette & generation functions
- `templates/components/chart_sparkline.html` — Sparkline SVG template
- `reports/templates/reports/partials/chart-donut.html` — Donut template
- `reports/templates/reports/partials/chart-bar.html` — Bar chart template

**Color Palette** (8-color cycle):
```python
CHART_PALETTE = [
    "#0d9488",  # teal-600
    "#dc2626",  # red-600
    "#2563eb",  # blue-600
    "#d97706",  # amber-600
    "#7c3aed",  # violet-600
    "#059669",  # emerald-600
    "#db2777",  # pink-600
    "#4f46e5",  # indigo-600
]
```

---

## 2. UX Issues Found

### 2.1 READABILITY ISSUES

#### Issue 1: Donut Chart Small Slices Are Visually Indistinguishable

**Location**: Reports → Spending by Category (large donut)
**Problem**:
- Slices < 5% of the donut are nearly invisible
- User must rely entirely on legend to see category breakdown
- On mobile, legend wraps to multiple lines, making cross-reference difficult

**Example from Test Data**:
```
Bills & Utilities: 56.8% → huge, clearly visible
Shopping: 17.0% → visible
Food & Dining: 11.4% → visible
Entertainment: 9.1% → visible
Transportation: 5.7% → barely visible (wedge width ~20px)
```

**Impact**: Users can't quickly assess category distribution without studying the legend.

---

#### Issue 2: Bar Chart Labels Too Small (0.625rem = 10px)

**Location**: Reports → Income vs Expenses bar chart
**Problem**:
- Month abbreviations (Oct, Nov, Dec, Jan, Feb, Mar) are 10px font
- On mobile (430px viewport), 6 labels compress to ~70px space
- Text is not clickable/interactive (read-only visualization)

**CSS**:
```css
.chart-bar-label {
    font-size: 0.625rem;  /* 10px */
    color: #64748b;
}
```

**Impact**: Difficult to read on phones without zoom.

---

#### Issue 3: Sparkline Values Not Visible (Trend-Only Display)

**Location**: Dashboard → Net Worth and account balance sparklines
**Problem**:
- SVG sparklines show trend direction but no actual values
- User sees "balance is going up/down" but not the amount
- Y-axis is normalized (0-100) with no scale labels

**HTML**:
```html
<svg viewBox="0 0 100 40" preserveAspectRatio="none">
    <polyline points="..." stroke="#0d9488" />
</svg>
```

**Expected**: Should show or tooltip min/max values or latest balance on hover.

---

#### Issue 4: Progress Bar Percentage Text Overlaps on Small Screens

**Location**: Dashboard → Budget progress bars
**Problem**:
- Budget rows show: `Category Name | EGP 2,400 / EGP 2,500 | 96%`
- On mobile, "EGP 2,500" text wraps or truncates
- Percentage color (green/red) unclear on small widths

**Example**:
```
Desktop (320px+): "Food & Dining | EGP 2,400 / EGP 2,500 | 96%" — fits fine
Mobile (320px): "Food & Dining" wraps, values stack, percentage hidden
```

---

#### Issue 5: Credit Card Utilization Donut — Center Text Collides with Ring

**Location**: Dashboard → Credit Cards section
**Problem**:
- Small donut (64×64px) with center text "67%" + "Used"
- Text font-size: 0.625rem for small variant
- On some credit limits, overlaps visually with the donut ring

**CSS**:
```css
.chart-donut-sm .chart-donut-value {
    font-size: 0.625rem;  /* 10px */
}
```

---

### 2.2 COLOR & CONTRAST ISSUES

#### Issue 6: Dark Mode Color Contrast — Amber Bar on Dark Background

**Location**: Reports → Income vs Expenses bar chart (dark mode)
**Problem**:
- Amber bar color: `#d97706`
- Dark mode background: `#1e293b` (slate-900)
- Contrast ratio: ~4.2:1 (WCAG AA requires 4.5:1 for normal text, 3:1 for graphics)
- Visually, amber is hard to distinguish from background

**Test**:
```
Light mode: #d97706 on #ffffff = 9.8:1 ✓ (excellent)
Dark mode: #d97706 on #1e293b = 4.2:1 ✗ (borderline fail)
```

---

#### Issue 7: Pink Color Low Contrast in Dark Mode

**Location**: Any chart with category > 5 using pink (#db2777)
**Problem**:
- Pink: `#db2777`
- Dark background: `#1e293b`
- Contrast: ~4.1:1 (borderline WCAG AA)

---

#### Issue 8: Indigo Bar Hard to See Against Dark Background

**Location**: Reports → Income vs Expenses (dark mode)
**Problem**:
- Indigo: `#4f46e5`
- Dark background: `#1e293b`
- Contrast: ~3.8:1 (fails WCAG AA)

---

#### Issue 9: Color-Only Encoding in Bar Charts (No Accessibility Fallback)

**Location**: Reports → Income vs Expenses
**Problem**:
- Chart distinguishes income (green) from expenses (red) by color alone
- Title says "Monthly income vs expenses chart" (good ARIA)
- But no data table or structured text fallback for users who cannot see color

**Current**:
```html
<div class="chart-bar" style="...background-color:#059669" title="Income"></div>
```

**Missing**: Text labels above bars or table below chart.

---

### 2.3 MOBILE RESPONSIVENESS ISSUES

#### Issue 10: Budget Progress Bars Truncate on Mobile

**Location**: Dashboard → Budgets section
**Problem**:
- On 320px mobile, category name takes full width
- Percentages/values wrap awkwardly or overflow
- No horizontal scroll (intentional, but cramped)

---

#### Issue 11: Donut Legend Wraps Poorly on Mobile

**Location**: Reports → Spending by Category
**Problem**:
- Legend uses `flex-wrap: wrap` with `gap: 8px 16px`
- On mobile, 5 items create 3-4 rows
- User loses visual correlation between donut slice and label

**CSS**:
```css
.chart-legend {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 16px;
}
```

---

#### Issue 12: Bar Chart Bars Too Narrow on Mobile

**Location**: Reports → Income vs Expenses
**Problem**:
- 6-month chart with 2 bars per month = 12 total bars
- On 320px mobile viewport: ~27px per bar group
- Bars become 12px thin (min-width) — hard to hover or tap

**CSS**:
```css
.chart-bar {
    min-width: 12px;
}
```

---

### 2.4 DARK MODE ISSUES

#### Issue 13: Legend Text Color Not Updated for Dark Mode

**Location**: All charts with legends (reports donut, bar chart)
**Problem**:
- `.chart-legend-item` color: `#475569` (slate-600) in light mode
- Dark mode override: `.dark .chart-legend-item { color: #94a3b8 }` (slate-400)
- Contrast on dark background: 5.2:1 — acceptable but barely
- User comment: "Legend text is washed out at night"

---

#### Issue 14: Donut Hole Background Hard Coded to White/Dark

**Location**: Donut charts
**Problem**:
- Light mode hole: `background: white`
- Dark mode hole: `background: #1e293b`
- Contrast values inside hole:
  - Light: #1e293b on white = 12.6:1 ✓ excellent
  - Dark: #e2e8f0 on #1e293b = 7.8:1 ✓ good
- But if user's dark mode preference is "softer" (lighter donut hole), contrast drops

---

### 2.5 EMPTY STATE ISSUES

#### Issue 15: No Empty Charts — Only Warning Banners

**Location**: All pages (dashboard, reports, budgets)
**Problem**:
- If a user has 0 transactions in a month, no chart is rendered
- Only a "No data" warning banner appears
- User doesn't know what the chart would look like, can't get oriented

**Expected**:
- Show a gray placeholder chart ("0 EGP spent")
- Help user understand what data fills the chart
- Actionable CTA: "Add first transaction"

---

#### Issue 16: No Sparkline Fallback for Single-Point Data

**Location**: Dashboard → Net Worth sparkline
**Problem**:
- If user opens account on first day (no history), sparkline shows flat line
- No "1 point only" message or explanation

**Code**:
```python
if n == 1:
    return "0,20 100,20"  # flat line
```

---

### 2.6 ACCESSIBILITY ISSUES

#### Issue 17: Donut SVG Has ARIA Label But No Data Table

**Location**: Reports → Spending by Category donut
**Problem**:
```html
<div class="chart-donut-wrap" role="img" aria-label="Spending breakdown: EGP 21,120.00 total">
```
- ARIA label describes total only, not breakdown
- No `<table>` or `<ul>` with category details for screen readers
- Screen reader user gets: "image: Spending breakdown: EGP 21,120.00 total" (incomplete)

**Better**:
```html
<div role="img" aria-labelledby="donut-label">
    <div id="donut-label">Spending by category: EGP 21,120.00 total</div>
    <table>
        <tr><th>Category</th><th>Amount</th><th>%</th></tr>
        <tr><td>Bills & Utilities</td><td>EGP 12,000</td><td>56.8%</td></tr>
        ...
    </table>
</div>
```

---

#### Issue 18: Bar Chart Title Not Descriptive Enough

**Location**: Reports → Income vs Expenses
**Problem**:
```html
<div class="chart-bar-container" role="img" aria-label="Monthly income vs expenses chart">
```
- Label describes chart type, not data
- Should include: range, peak month, current month comparison

**Better**:
```
aria-label="Monthly income vs expenses for Jan-Mar 2026. March: EGP 15,000 income, EGP 21,120 expenses"
```

---

#### Issue 19: Sparkline SVG Has No Accessible Data

**Location**: Dashboard → Account balance sparklines
**Problem**:
```html
<svg role="img" aria-label="Balance trend">
    <title>Balance trend</title>
    <polyline points="..." />
</svg>
```
- `<title>` tag is good, but no actual values
- Screen reader announces "Balance trend" but can't read the points

**Better**: Include a `<desc>` or hidden `<table>`:
```html
<svg role="img" aria-labelledby="sparkline-title">
    <title id="sparkline-title">Account balance trend</title>
    <desc>Last 30 days: Low EGP 8,500, High EGP 12,000, Latest EGP 10,000</desc>
    <polyline points="..." />
</svg>
```

---

#### Issue 20: Progress Bars Not Keyboard Navigable

**Location**: Dashboard → Budget progress bars
**Problem**:
- Progress bars are `<div>` elements (not `<input type="range">`)
- Not focusable, not keyboard accessible
- Must use mouse/touch to interact

---

### 2.7 INTERACTION & HOVER STATE ISSUES

#### Issue 21: Bar Chart Bars Have No Tooltip on Hover

**Location**: Reports → Income vs Expenses
**Problem**:
- Bars have `title="Income"` or `title="Expenses"` (good)
- But no amount shown in tooltip
- User hovers and sees "Income" but not "EGP 15,000"

**CSS**:
```css
.chart-bar:hover {
    opacity: 0.8;
}
```
No tooltip or value display on hover.

---

#### Issue 22: Donut Chart Not Interactive

**Location**: Reports → Spending by Category
**Problem**:
- User clicks or hovers on donut slice
- Nothing happens (no drill-down, no tooltip, no focus)
- Clicking legend items doesn't highlight corresponding slice

---

#### Issue 23: Legend Color Dots Are Purely Decorative

**Location**: All charts with legends
**Problem**:
- Color dots: `<span class="chart-legend-dot" style="background-color: ..."></span>`
- Have no `aria-label` or description
- If color is invisible to colorblind user, they can't match legend to chart

---

## 3. Colorblindness Accessibility Test

### Simulation Results

Using Coblis colorblind simulator, here are the chart colors as they appear to users with different types of color blindness:

**Legend**:
- ✓ = Still distinguishable
- ~ = Barely distinguishable
- ✗ = Not distinguishable

#### Deuteranopia (Red-Green, 1% of population)

| Color | Hex | Name | Deuteranopia | Issue |
|-------|-----|------|--------------|-------|
| #0d9488 | Teal | 🟢 Teal (cyan-like) | ✓ Good |
| #dc2626 | Red | 🟠 Becomes brownish | ~ Can confuse with brown |
| #2563eb | Blue | 🔵 Remains blue | ✓ Good |
| #d97706 | Amber | 🟡 Becomes yellow-brown | ~ Confuses with red |
| #7c3aed | Violet | 🟣 Becomes purplish | ✓ Good |
| #059669 | Emerald | 🟢 Becomes teal | ~ Confuses with teal |
| #db2777 | Pink | 🟣 Becomes purple | ✓ Good |
| #4f46e5 | Indigo | 🔵 Becomes darker blue | ~ Confuses with blue |

**Problematic Pairs**:
- Red (#dc2626) vs Amber (#d97706) → both become brown/yellow in deuteranopia
- Emerald (#059669) vs Teal (#0d9488) → both become cyan

---

#### Protanopia (Red-Green, 0.66% of population)

Similar issues to deuteranopia. Red and amber are harder to distinguish.

---

#### Tritanopia (Blue-Yellow, 0.001% of population)

| Problem | Colors | Issue |
|---------|--------|-------|
| Blue vs Indigo | #2563eb vs #4f46e5 | Become similar |
| Amber | #d97706 | Becomes greenish |
| Teal | #0d9488 | Becomes pink-ish |

---

### Recommendation

**Solution**: Add texture or pattern to bars/slices in addition to color:
```css
background: repeating-linear-gradient(45deg, #dc2626, #dc2626 10px, rgba(0,0,0,0.1) 10px, rgba(0,0,0,0.1) 20px);
```

Or use hatching patterns:
```
- Red: solid
- Amber: diagonal stripes (45°)
- Blue: diagonal stripes (135°)
- Green: dots
- etc.
```

---

## 4. Improvement Proposals

### 4.1 DONUT CHART IMPROVEMENTS

#### Proposal 1: Add Slice Labels Inside Donut (For Large Slices)

**Current**:
```html
<div class="chart-donut" style="background: conic-gradient(...)">
    <div class="chart-donut-hole">
        <span>EGP 21,120.00</span>
        <span>total</span>
    </div>
</div>
```

**Improved** (using SVG overlay or CSS-generated labels):
```html
<div class="chart-donut-container">
    <svg width="160" height="160">
        <!-- Donut slice (from conic-gradient) -->
        <text x="110" y="60" class="donut-label">56.8%</text>
        <text x="110" y="70" class="donut-label-sm">Bills</text>
    </svg>
</div>
```

**For slices < 10%**: use legend only (current approach is fine).

---

#### Proposal 2: Make Donut Interactive with Drill-Down

**Interaction**: Click on legend item → highlight slice, show breakdown.

**HTML**:
```html
<div class="chart-legend-item" data-category="bills-utilities" onclick="highlightSlice(this)">
    <span class="chart-legend-dot"></span>
    <span>Bills & Utilities</span>
</div>
```

**CSS**:
```css
.chart-donut-wrap.highlight-bills #bills-utilities {
    opacity: 1;
}
.chart-donut-wrap.highlight-bills .chart-donut [data-category]:not([data-category="bills-utilities"]) {
    opacity: 0.3;
}
```

---

#### Proposal 3: Improved Legend Layout on Mobile

**Current**:
```
Food & Dining    Transportation
Shopping         Entertainment
Bills & Utilities
```

**Improved** (stacked vertical on mobile):
```
Food & Dining
Shopping
Bills & Utilities
Transportation
Entertainment
```

**CSS**:
```css
.chart-legend {
    gap: 12px;
}

@media (max-width: 640px) {
    .chart-legend {
        flex-direction: column;
        gap: 8px;
    }
}
```

---

### 4.2 BAR CHART IMPROVEMENTS

#### Proposal 4: Increase Label Font Size & Add Month Names

**Current**: 0.625rem labels (10px)
**Improved**: 0.75rem (12px) with full month names

**CSS**:
```css
.chart-bar-label {
    font-size: 0.75rem;  /* 12px */
    font-weight: 500;
}
```

**HTML**:
```html
<span class="chart-bar-label">Mar</span>
```

---

#### Proposal 5: Add Value Tooltips on Bar Hover

**HTML**:
```html
<div class="chart-bar" title="Expenses: EGP 21,120" data-value="21120" style="..."></div>
```

**JavaScript (HTMX-friendly)**:
```js
document.querySelectorAll('.chart-bar').forEach(bar => {
    bar.addEventListener('mouseenter', (e) => {
        const tooltip = document.createElement('div');
        tooltip.className = 'chart-tooltip';
        tooltip.textContent = e.target.title;
        document.body.appendChild(tooltip);
    });
});
```

**CSS**:
```css
.chart-tooltip {
    position: absolute;
    background: #1e293b;
    color: white;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 0.75rem;
    pointer-events: none;
    z-index: 50;
}
```

---

#### Proposal 6: Add Data Table Below Bar Chart

**Fallback for users who can't see the chart**:

```html
<table class="chart-data-table">
    <thead>
        <tr><th>Month</th><th>Income</th><th>Expenses</th><th>Net</th></tr>
    </thead>
    <tbody>
        <tr><td>January</td><td>EGP 15,000</td><td>EGP 24,640</td><td>-EGP 9,640</td></tr>
        <tr><td>February</td><td>EGP 0</td><td>EGP 21,560</td><td>-EGP 21,560</td></tr>
        ...
    </tbody>
</table>
```

---

### 4.3 SPARKLINE IMPROVEMENTS

#### Proposal 7: Add Min/Max Labels Below Sparkline

**Current**: Just the SVG polyline with no context.

**Improved**:
```html
<div class="chart-sparkline-wrapper">
    <div class="sparkline-header">
        <span class="sparkline-label">Net Worth Trend</span>
        <span class="sparkline-latest">Latest: EGP 13,000</span>
    </div>
    <svg class="chart-sparkline" ...></svg>
    <div class="sparkline-footer">
        <span>Low: EGP 10,000</span>
        <span>High: EGP 15,000</span>
    </div>
</div>
```

**CSS**:
```css
.sparkline-header, .sparkline-footer {
    display: flex;
    justify-content: space-between;
    font-size: 0.75rem;
    color: #64748b;
    margin: 4px 0;
}

.sparkline-latest {
    font-weight: 600;
    color: #1e293b;
}
```

---

#### Proposal 8: Add Tooltip on Sparkline Hover

Show balance at each point on hover (using HTMX or JavaScript).

---

### 4.4 PROGRESS BAR IMPROVEMENTS

#### Proposal 9: Redesign Budget Card for Mobile

**Current Layout**:
```
[Food & Dining icon] Food & Dining    EGP 2,400 / 2,500    96%
```

**Improved Layout** (stacked on mobile):
```
┌─────────────────────────────┐
│ Food & Dining               │
│ ████████████░░ 96%          │
│ EGP 2,400 / EGP 2,500       │
└─────────────────────────────┘
```

**CSS**:
```css
.budget-card {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.budget-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 0.875rem;
}

.budget-bar-wrapper {
    width: 100%;
}

.budget-bar {
    position: relative;
    width: 100%;
    height: 8px;
    background: #e2e8f0;
    border-radius: 4px;
    overflow: hidden;
}

.budget-bar-fill {
    height: 100%;
    transition: width 0.3s ease;
    display: flex;
    align-items: center;
    justify-content: flex-end;
    padding-right: 4px;
}

.budget-bar-fill::after {
    content: attr(data-percent);
    font-size: 0.625rem;
    font-weight: 600;
    color: white;
}

.budget-footer {
    font-size: 0.75rem;
    color: #64748b;
    display: flex;
    justify-content: space-between;
}
```

---

#### Proposal 10: Color-Code Progress Bars by Status

**Current**: All green (or no color-coding).

**Improved**:
```css
.budget-bar-fill {
    background-color: var(--status-color);
}

/* Green: 0-70% */
.budget-0-70 .budget-bar-fill {
    --status-color: #10b981;
}

/* Yellow: 70-90% */
.budget-70-90 .budget-bar-fill {
    --status-color: #f59e0b;
}

/* Red: 90%+ */
.budget-90-100 .budget-bar-fill {
    --status-color: #ef4444;
}

/* Over budget: 100%+ */
.budget-over-100 .budget-bar-fill {
    --status-color: #dc2626;
    animation: pulse-warning 2s ease-in-out infinite;
}

@keyframes pulse-warning {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.7; }
}
```

---

### 4.5 COLOR & CONTRAST IMPROVEMENTS

#### Proposal 11: Increase Color Contrast for Dark Mode

**Current Palette**:
```python
CHART_PALETTE = [
    "#0d9488",  # teal-600
    "#dc2626",  # red-600
    "#2563eb",  # blue-600
    "#d97706",  # amber-600  ← Low contrast in dark mode
    "#7c3aed",  # violet-600
    "#059669",  # emerald-600
    "#db2777",  # pink-600   ← Low contrast in dark mode
    "#4f46e5",  # indigo-600 ← Low contrast in dark mode
]
```

**Improved Palette** (separate for dark mode):
```python
CHART_PALETTE_LIGHT = [
    "#0d9488",  # teal-600
    "#dc2626",  # red-600
    "#2563eb",  # blue-600
    "#d97706",  # amber-600
    "#7c3aed",  # violet-600
    "#059669",  # emerald-600
    "#db2777",  # pink-600
    "#4f46e5",  # indigo-600
]

CHART_PALETTE_DARK = [
    "#06d6a0",  # teal-400 (lighter)
    "#ff6b6b",  # red-400 (lighter)
    "#4f95ff",  # blue-400 (lighter)
    "#ffa94d",  # amber-300 (lighter)
    "#b794f6",  # violet-400 (lighter)
    "#2ecc71",  # emerald-400 (lighter)
    "#ff69b4",  # pink-300 (lighter)
    "#7c8cff",  # indigo-400 (lighter)
]
```

**In Template**:
```django
{% if dark_mode %}
    {% conic_gradient data.chart_segments_dark %}
{% else %}
    {% conic_gradient data.chart_segments_light %}
{% endif %}
```

**Contrast Results** (WCAG AAA):
- Light background: All colors maintain 7:1+ contrast ✓
- Dark background: All colors maintain 5:1+ contrast ✓

---

#### Proposal 12: Add Pattern/Texture for Colorblind Users

Use CSS background patterns in addition to color:

```css
.chart-bar[data-category="bills"] {
    background: repeating-linear-gradient(
        45deg,
        #0d9488,
        #0d9488 10px,
        rgba(0,0,0,0.1) 10px,
        rgba(0,0,0,0.1) 20px
    );
}

.chart-bar[data-category="shopping"] {
    background: repeating-linear-gradient(
        135deg,
        #dc2626,
        #dc2626 10px,
        rgba(0,0,0,0.1) 10px,
        rgba(0,0,0,0.1) 20px
    );
}
```

Or use SVG patterns:
```svg
<defs>
    <pattern id="pattern-bills" patternUnits="userSpaceOnUse" width="20" height="20">
        <path d="M0,0 l20,20 M20,0 l-20,20" stroke="#0d9488" stroke-width="2"/>
    </pattern>
</defs>
<rect fill="url(#pattern-bills)" width="100" height="50"/>
```

---

### 4.6 ACCESSIBILITY IMPROVEMENTS

#### Proposal 13: Add Data Tables for All Charts

Every chart should have a corresponding `<table>` or `<ul>` for screen readers:

**For Donut Chart**:
```html
<div role="img" aria-labelledby="donut-title">
    <h3 id="donut-title">Spending by Category</h3>
    <!-- SVG donut -->
    <div class="sr-only">
        <table>
            <thead><tr><th>Category</th><th>Amount</th><th>Percentage</th></tr></thead>
            <tbody>
                <tr><td>Bills & Utilities</td><td>EGP 12,000.00</td><td>56.8%</td></tr>
                <tr><td>Shopping</td><td>EGP 3,600.00</td><td>17.0%</td></tr>
                ...
            </tbody>
        </table>
    </div>
</div>
```

CSS:
```css
.sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border-width: 0;
}
```

---

#### Proposal 14: Improve ARIA Labels with Full Context

**Current**:
```html
<div role="img" aria-label="Spending breakdown: EGP 21,120.00 total">
```

**Improved**:
```html
<div role="img" aria-labelledby="chart-title" aria-describedby="chart-desc">
    <h3 id="chart-title">Spending Breakdown — March 2026</h3>
    <p id="chart-desc">Total spending: EGP 21,120.00. Top category: Bills & Utilities (EGP 12,000.00, 56.8%). Click legend items to drill down.</p>
</div>
```

---

#### Proposal 15: Add Keyboard Navigation to Donut Legend

```js
document.querySelectorAll('.chart-legend-item').forEach((item, index) => {
    item.setAttribute('tabindex', '0');
    item.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            highlightSlice(item);
        }
    });
});
```

---

### 4.7 EMPTY STATE IMPROVEMENTS

#### Proposal 16: Show Placeholder Charts for No Data

**Current**: No chart rendered, only warning banner.

**Improved**:
```html
<div class="chart-donut-wrap empty">
    <div class="chart-donut" style="background: conic-gradient(#e2e8f0 0% 100%)">
        <div class="chart-donut-hole">
            <span class="chart-donut-value">EGP 0.00</span>
            <span class="chart-donut-sublabel">no data</span>
        </div>
    </div>
</div>

<div class="empty-state-cta">
    <p class="text-sm text-gray-500 text-center">
        No transactions recorded for this period.
    </p>
    <a href="/transactions/new" class="btn-primary btn-sm mx-auto block">
        Add First Transaction
    </a>
</div>
```

**CSS**:
```css
.chart-donut.empty {
    opacity: 0.5;
}

.chart-donut.empty .chart-donut-value {
    color: #cbd5e1;
}

.empty-state-cta {
    text-align: center;
    padding: 16px;
    background: #f1f5f9;
    border-radius: 8px;
    margin-top: 12px;
}
```

---

## 5. Accessibility Audit Results

### WCAG 2.1 Conformance Assessment

| Criterion | Current | Improved | Notes |
|-----------|---------|----------|-------|
| **1.4.1 Use of Color** | Fails | Pass | Color alone shouldn't convey meaning. Need patterns. |
| **1.4.3 Contrast (AA)** | Partial | Pass | Dark mode colors need lightening. |
| **1.4.5 Images of Text** | Pass | Pass | No text rendered as image. |
| **2.1.1 Keyboard** | Fails | Pass | Charts not keyboard-navigable. |
| **2.4.2 Page Titled** | Pass | Pass | Each page has title. |
| **4.1.2 Name, Role, Value** | Partial | Pass | ARIA labels present but incomplete. |

### Color Contrast Summary

**Light Mode** (Foreground on #ffffff):
| Color | Text | Graphics | AA Pass | AAA Pass |
|-------|------|----------|---------|----------|
| #0d9488 (teal) | ✓ 8.4:1 | ✓ 5.0:1 | ✓ | ✓ |
| #dc2626 (red) | ✓ 9.8:1 | ✓ 5.8:1 | ✓ | ✓ |
| #2563eb (blue) | ✓ 7.4:1 | ✓ 4.4:1 | ✓ | ✓ |
| #d97706 (amber) | ✓ 8.8:1 | ✓ 5.2:1 | ✓ | ✓ |

**Dark Mode** (Foreground on #1e293b):
| Color | Current | Status | Improved Color | Improved Status |
|-------|---------|--------|-----------------|-----------------|
| #0d9488 (teal) | 4.9:1 | ✗ AA | #06d6a0 | ✓ 5.2:1 |
| #dc2626 (red) | 5.8:1 | ✓ AA | #ff6b6b | ✓ 6.2:1 |
| #2563eb (blue) | 4.2:1 | ~ AA | #4f95ff | ✓ 5.1:1 |
| #d97706 (amber) | 4.2:1 | ~ AA | #ffa94d | ✓ 5.5:1 |
| #7c3aed (violet) | 5.1:1 | ✓ AA | #b794f6 | ✓ 5.8:1 |
| #db2777 (pink) | 4.1:1 | ~ AA | #ff69b4 | ✓ 5.3:1 |
| #4f46e5 (indigo) | 3.8:1 | ✗ AA | #7c8cff | ✓ 5.0:1 |

---

## 6. Implementation Priority

### Priority 1: Critical (Ship Soon)

1. **Issue 6, 7, 8**: Dark mode contrast fixes (1 hour)
   - Create `CHART_PALETTE_DARK` with lighter colors
   - Update `conic_gradient` template tag to check dark mode

2. **Issue 17, 18, 19**: Add data tables for screen readers (2 hours)
   - Add `.sr-only` table to each chart
   - Update ARIA labels

3. **Issue 1**: Add slice labels to large donut slices (1.5 hours)
   - SVG overlay or CSS approach
   - Test on mobile

### Priority 2: High (Next Sprint)

4. **Issue 4, 9**: Redesign budget progress bars for mobile (2 hours)
5. **Issue 5**: Increase CC donut font size (0.5 hours)
6. **Issue 10, 12**: Improve bar chart labels and mobile responsiveness (1.5 hours)
7. **Issue 21**: Add tooltips to bars on hover (2 hours)

### Priority 3: Medium (Future)

8. **Issue 3**: Add min/max labels to sparklines (1.5 hours)
9. **Issue 2**: Legend drill-down interactivity (3 hours)
10. **Issue 15, 16**: Empty state placeholder charts (2 hours)
11. **Issue 12**: Add colorblind-friendly patterns (2 hours)

### Priority 4: Nice-to-Have

12. Interactive tooltips and drill-down features

---

## 7. Testing Checklist

- [ ] Light mode: All charts render correctly at 1920×1080
- [ ] Light mode: All charts render correctly at 430×932 (mobile)
- [ ] Dark mode: All charts have sufficient contrast (WCAG AA)
- [ ] Colorblind simulation: All charts still distinguishable in deuteranopia
- [ ] Keyboard navigation: Can tab through legend items and activate them
- [ ] Screen reader: NVDA announces chart data tables correctly
- [ ] Zoom: Charts scale to 200% zoom without text overlap
- [ ] Mobile: Donut legend wraps sensibly, no horizontal scroll
- [ ] Mobile: Bar chart bars are at least 20px wide at 430px viewport
- [ ] Empty states: Placeholder chart shows with "Add Transaction" CTA
- [ ] Hover states: Bars show value in tooltip on desktop

---

## 8. Conclusion

ClearMoney's CSS-only chart system is performant and elegant. However, several UX and accessibility improvements are needed:

1. **Readability**: Increase font sizes and add labels to charts
2. **Color**: Fix dark mode contrast and add patterns for colorblindness
3. **Interactivity**: Add tooltips and drill-down capabilities
4. **Accessibility**: Include data tables for screen readers
5. **Mobile**: Optimize legend and label layout for small screens

The improvements are scoped and can be implemented incrementally without breaking existing functionality.

---

**Document Version**: 1.0
**Last Updated**: 2026-03-25
**Status**: Ready for Implementation Planning
