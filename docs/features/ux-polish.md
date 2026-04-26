# UX Polish

Collection of UX enhancements that make ClearMoney feel polished and app-like.

## Success Animations & Toast Notifications

**CSS:** `static/css/app.css` (lines ~52-82)

Three animation keyframes:
- `checkmark-draw` — SVG stroke animation (0.4s ease-out, 0.2s delay)
- `toast-slide-up` — slide in from bottom (0.3s ease-out)
- `success-bounce` — scale 0→1.1→1 (0.4s)

**Template:** `backend/transactions/templates/transactions/_transaction_success.html`
- Animated checkmark SVG with circle background
- "Saved!" message + new balance display
- "Done" button to dismiss
- OOB swap to refresh dashboard recent transactions

**Usage:** Shown after quick-entry transaction creation via HTMX response.

## Smart Category Suggestions

**Endpoint:** `GET /api/transactions/suggest-category?note=...`

**How it works:**
1. User types in note field (quick-entry form)
2. After 300ms of no typing + 3 characters minimum → fetch suggestion
3. SQL: `SELECT category_id FROM transactions WHERE note ILIKE '%keyword%' GROUP BY category_id ORDER BY COUNT(*) DESC LIMIT 1`
4. Returns most-used category ID for matching notes
5. Only auto-selects if category dropdown is empty (preserves user intent)
6. Silent failure — no error shown if suggestion fails

**Backend:** `backend/transactions/views.py` → `helpers.suggest_category()` → Django ORM
**Frontend:** JavaScript in `backend/transactions/templates/transactions/_quick_entry.html` with debounced fetch

## Pull-to-Refresh

**File:** `static/js/gestures.js`

Works on elements with `[data-pull-refresh]` attribute:
1. Detects a downward touch drag only while the scroll container is at the top
2. Shows a release-to-refresh indicator after the threshold is crossed
3. Reloads the page on release after a valid pull

## Empty States

When lists are empty (no accounts, transactions, etc.), a friendly empty state is shown with an icon and helpful message encouraging the user to add their first item.

**Template example:** Each list template includes a conditional block:
```html
{% if transactions %}
    <!-- render list -->
{% else %}
    <div class="text-center text-gray-400 py-12">
        <p>No transactions yet.</p>
        <a href="/transactions/new">Add your first transaction</a>
    </div>
{% endif %}
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

Views pass a `today` context variable populated server-side.

## HTMX Result Pattern

Consistent success/error/info partials for inline feedback. Views return small HTML fragments with a status class:

Types: `success` (green), `error` (red), `info` (blue).

## Key Files

| File | Purpose |
|------|---------|
| `static/css/app.css` | Animations, skeleton, dark mode overrides |
| `static/css/charts.css` | Chart dark mode overrides |
| `static/js/gestures.js` | Swipe-to-delete, pull-to-refresh |
| `static/js/theme.js` | Dark mode toggle |
| `backend/transactions/templates/transactions/_transaction_success.html` | Success animation |

## For Newcomers

- **No JavaScript frameworks** — all UX enhancements use vanilla JS + CSS animations + HTMX.
- **Touch gestures** — implemented with raw `touchstart`/`touchmove`/`touchend` events. No gesture libraries.
- **Skeleton loading** — purely CSS-based shimmer effect. No JavaScript required.
- **HTMX-driven** — most interactions use HTMX for partial page updates rather than full reloads.
- **Date pre-population** — always server-side, never client-side JavaScript. This prevents timezone issues.
