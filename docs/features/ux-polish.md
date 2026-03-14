# UX Polish

Collection of UX enhancements that make ClearMoney feel polished and app-like.

## Success Animations & Toast Notifications

**CSS:** `static/css/app.css` (lines ~52-82)

Three animation keyframes:
- `checkmark-draw` — SVG stroke animation (0.4s ease-out, 0.2s delay)
- `toast-slide-up` — slide in from bottom (0.3s ease-out)
- `success-bounce` — scale 0→1.1→1 (0.4s)

**Template:** `internal/templates/partials/success-toast.html`
- Animated checkmark SVG with circle background
- "Saved!" message + new balance display
- "Done" button to dismiss
- OOB swap to refresh dashboard recent transactions

**Usage:** Shown after quick-entry transaction creation via HTMX response.

## Skeleton Loading

**CSS:** `static/css/app.css` (lines ~102-118)
- `skeleton-shimmer` — gradient moves left-to-right (1.5s infinite)
- `.skeleton` class — gray gradient background with border-radius
- Dark mode: darker gradient (slate-400 to slate-600)

**Templates:**
- `partials/skeleton-card.html` — dashboard card placeholder (label + value + subtitle)
- `partials/skeleton-list.html` — transaction list placeholder (3 rows)

**Usage:** HTMX `hx-indicator` attribute shows skeleton while loading partial content.

## Smart Category Suggestions

**Endpoint:** `GET /api/transactions/suggest-category?note=...`

**How it works:**
1. User types in note field (quick-entry form)
2. After 300ms of no typing + 3 characters minimum → fetch suggestion
3. SQL: `SELECT category_id FROM transactions WHERE note ILIKE '%keyword%' GROUP BY category_id ORDER BY COUNT(*) DESC LIMIT 1`
4. Returns most-used category ID for matching notes
5. Only auto-selects if category dropdown is empty (preserves user intent)
6. Silent failure — no error shown if suggestion fails

**Backend:** `pages.go` → `transaction.go` service → `transaction.go` repo
**Frontend:** JavaScript in `partials/quick-entry.html` with debounced fetch

## Swipe-to-Delete Gestures

**File:** `static/js/gestures.js` (lines ~52-113)

Works on elements with `[data-swipe-delete]` attribute:
1. Detects touch drag left >80px
2. Shows red delete indicator when drag >50px
3. On release with dx < -60: `confirm()` prompt, then DELETE request
4. Animates removal with opacity fade (0.3s)
5. Sets `HX-Request: true` header for HTMX compatibility

**Backend:** Delete handler returns empty 200 OK; HTMX removes the row via `hx-swap="outerHTML"`.

## Pull-to-Refresh

**File:** `static/js/gestures.js` (lines ~13-50)

Works on elements with `[data-pull-refresh]` attribute:
1. Detects touch drag down >60px from top
2. Shows "Release to refresh" indicator
3. On release: `window.location.reload()`

## Empty States

When lists are empty (no accounts, transactions, etc.), a friendly empty state is shown with an icon and helpful message encouraging the user to add their first item.

**Template example:** Each list template includes a conditional block:
```html
{{if .Data}}
    <!-- render list -->
{{else}}
    <div class="text-center text-gray-400 py-12">
        <p>No transactions yet.</p>
        <a href="/transactions/new">Add your first transaction</a>
    </div>
{{end}}
```

## Dark Mode

See [Settings](settings.md) for toggle implementation details.

**Implementation:**
- Tailwind `darkMode: 'class'` — toggling adds/removes `dark` class on `<html>`
- Persisted in localStorage (key: `clearmoney-theme`)
- Applied before DOM renders (no flash)
- Custom CSS overrides in `static/css/app.css` and `static/css/charts.css`

**Colors:**
- Primary dark background: `#0f172a` (slate-900)
- Card backgrounds: slate-800
- Input fields: dark backgrounds with light borders
- Charts: explicit colors preserved, only backgrounds/text adapt

## Clickable Header

The ClearMoney logo/title in the header is a link to `/` (dashboard), providing quick navigation back to home from any page.

## Date Pre-Population

All date inputs default to today via server-side rendering:
```html
<input type="date" value="{{formatDateISO .Data.Today}}">
```

View model structs carry a `Today time.Time` field populated by the handler.

## HTMX Result Pattern

**Template:** `internal/templates/partials/htmx-result.html`

Consistent success/error/info partials for inline feedback:
```go
h.renderHTMXResult(w, "success", "Saved!", "Transaction created")
h.renderHTMXResult(w, "error", "Failed", "Amount must be positive")
```

Types: `success` (green), `error` (red), `info` (blue).

## Key Files

| File | Purpose |
|------|---------|
| `static/css/app.css` | Animations, skeleton, dark mode overrides |
| `static/css/charts.css` | Chart dark mode overrides |
| `static/js/gestures.js` | Swipe-to-delete, pull-to-refresh |
| `static/js/theme.js` | Dark mode toggle |
| `internal/templates/partials/success-toast.html` | Success animation |
| `internal/templates/partials/skeleton-card.html` | Card skeleton |
| `internal/templates/partials/skeleton-list.html` | List skeleton |
| `internal/templates/partials/htmx-result.html` | Success/error/info partials |

## For Newcomers

- **No JavaScript frameworks** — all UX enhancements use vanilla JS + CSS animations + HTMX.
- **Touch gestures** — implemented with raw `touchstart`/`touchmove`/`touchend` events. No gesture libraries.
- **Skeleton loading** — purely CSS-based shimmer effect. No JavaScript required.
- **HTMX-driven** — most interactions use HTMX for partial page updates rather than full reloads.
- **Date pre-population** — always server-side, never client-side JavaScript. This prevents timezone issues.
