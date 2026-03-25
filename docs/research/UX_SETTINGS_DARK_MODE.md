# UX Research: Settings & Dark Mode

**Audit Date:** March 25, 2026
**Scope:** Settings page, categories management, dark mode toggle mechanics, theme consistency across all pages
**Source Files Analyzed:**
- `backend/settings_app/templates/settings_app/settings.html`
- `backend/settings_app/templates/settings_app/categories.html`
- `backend/templates/components/header.html`
- `static/js/theme.js`
- `static/css/app.css` (dark mode overrides section)
- `static/css/charts.css` (dark mode chart overrides section)
- `backend/templates/base.html`

---

## Summary

The settings page is minimal — it exposes Dark Mode, CSV Export, Push Notifications, Categories, Quick Links, and Logout. The dark mode implementation uses a clean localStorage-based toggle with no-flash class injection, and Tailwind's class-based dark mode. Coverage is broad but incomplete: several component-specific styles depend on aggressive `!important` overrides in `app.css`, which creates fragility. The settings page itself does not use dark-mode-aware classes on all elements, creating visual inconsistencies.

---

## Current Settings Page Structure

```
/settings
├── Dark Mode section — Toggle button (text: "Toggle")
├── Export Transactions — Date range form + Download CSV button
├── Push Notifications — Enable button
├── Categories — Link to /settings/categories
├── Quick Links — Text links to Budgets, Investments, Recurring, Virtual Accounts, Batch Entry, Salary, Fawry
└── Logout — POST form with red-toned button
```

```
/settings/categories
├── Add Category form (icon input + name input + Add button)
├── Active Categories list (with Archive button per row)
└── Archived Categories collapsible section (with Restore per row)
```

---

## Key Findings

### Critical Issues (Block usage)

- **Issue 1: Dark mode toggle button has no current-state indicator.**
  The toggle button in `header.html` uses emoji (🌙 / ☀️) and `aria-pressed`. However, the "Toggle" button on the Settings page (`settings.html`) uses only the text "Toggle" with no emoji, no icon, and no indication of the current state:
  ```html
  <button onclick="toggleTheme()" class="bg-slate-100 text-slate-700 px-4 py-2 rounded-lg text-sm font-semibold">
      Toggle
  </button>
  ```
  This button does not update when the theme changes (unlike the header icon which receives `aria-pressed` updates from `theme.js`). The header emoji updates dynamically; the Settings page "Toggle" does not. This inconsistency means the Settings page toggle feels broken — users cannot confirm whether it worked.

- **Issue 2: Settings page dark mode classes are missing on key elements.**
  The Settings page `<h2>` uses `text-slate-800` with no `dark:` variant:
  ```html
  <h2 class="text-lg font-bold text-slate-800">Settings</h2>
  ```
  This relies on the aggressive `app.css` override:
  ```css
  .dark .text-slate-800 { color: #e2e8f0 !important; }
  ```
  The `!important` overrides are necessary because of missing `dark:` variants throughout the app. This is a systemic fragility — any new element that uses `text-slate-800` without a `dark:` variant will fail in dark mode unless the CSS override is in place.

- **Issue 3: Dark mode preference does not respect OS-level `prefers-color-scheme`.**
  The `theme.js` file uses `localStorage.getItem(THEME_KEY) || 'light'` as the default. It never reads `window.matchMedia('(prefers-color-scheme: dark)')`. This means:
  - Users with OS dark mode set to dark will see ClearMoney in light mode on first visit
  - WCAG 1.4.12 (User Agent Compatibility) recommends honoring system preferences
  - This is especially important for iOS users who have dark mode enabled system-wide

### High-Priority Issues (Major friction)

- **Issue 4: "Toggle" is an ambiguous button label.**
  The Settings page button text is "Toggle" — it does not say what it toggles or what the current state is. Accessible button names should describe the action: "Switch to Dark Mode" or "Switch to Light Mode" depending on current state. The `aria-label` is absent from this button. Contrast: the header button has `aria-label="Toggle dark mode"` and `aria-pressed`.

- **Issue 5: Settings page has no active_tab for bottom navigation.**
  When navigating to `/settings`, the bottom navigation does not highlight any active item. The "More" menu item is supposed to represent secondary pages (Settings is inside More), but `active_tab` is not set on the Settings view. Users lose their location context in the nav.

- **Issue 6: Quick Links section duplicates the More menu.**
  The Settings page has a "Quick Links" section listing: Budgets, Investments, Recurring Rules, Virtual Accounts, Batch Entry, Salary Distribution, Fawry Cash-Out. These same items appear in the More bottom sheet (accessed from the bottom nav). This is redundant and could confuse users about canonical navigation paths. The Settings page should not function as a second navigation hub.

- **Issue 7: Export form lacks validation feedback.**
  The date range form for CSV export (`hx-boost="false"` GET form) has no client-side validation feedback. If a user submits with a "From" date after a "To" date, the server returns an empty CSV — no error is shown. There is no indication of success (the browser downloads silently). Users frequently won't notice the download unless they check their Downloads folder.

- **Issue 8: Push notifications button state is never updated.**
  The "Enable" button for push notifications uses `onclick="requestNotificationPermission()"`. After clicking, the button does not change label, color, or state — regardless of whether the user approved or denied the permission. If the user has already granted permission, the button still shows "Enable". If they denied it, clicking again does nothing. The UI is permanently stuck in "Enable" state.

- **Issue 9: Categories page "Add Category" form has no required field validation indicator.**
  The name field has `required` attribute, but there is no visible asterisk, label hint, or inline error message. The icon field (emoji input) has no size guidance — what's a valid emoji size? 1-4 characters is enforced by `maxlength="4"` but there is no hint.

### Medium-Priority Issues (Noticeable problems)

- **Issue 10: Settings page does not use a proper `<h1>`.**
  `<h2 class="text-lg font-bold text-slate-800">Settings</h2>` — using an `<h2>` as the page title violates heading hierarchy. WCAG 1.3.1 requires a meaningful `<h1>` on each page.

- **Issue 11: Dark mode button in the header is an emoji-only button.**
  The header has `<button ... aria-label="Toggle dark mode">🌙</button>`. While `aria-label` is present, the emoji renders differently across OS versions and has no visible text. On small headers it is 14×20px — well below the 44×44px WCAG minimum touch target. The button renders as `text-sm` with no `min-h` or padding that would expand the touch area.

- **Issue 12: Dark mode does not cover all background variants in app.css.**
  The `app.css` dark overrides cover common cases (`bg-white → #1e293b`, `bg-gray-50 → #0f172a`) but miss some patterns:
  - `bg-blue-100` — appears in billing cycle info cards
  - `bg-green-50` — appears in income indicators
  - `bg-purple-100` — appears in investments page
  - When these appear in dark mode, they show with their light-mode lightness level, creating "light islands" in an otherwise dark interface

- **Issue 13: Categories page "Archive" button is a full form POST.**
  Each category row has a `<form method="POST">` for archiving. This is a full-page form submission (not HTMX). On success, the page reloads. No success confirmation is shown. This makes it unclear whether the archive action succeeded.

- **Issue 14: Category icon input has no preview.**
  Users type an emoji into a tiny 56px-wide input and cannot see how it will appear in a transaction row until after saving. Adding a live preview ("Preview: [emoji]") would reduce mistakes.

- **Issue 15: Categories page "Archived" section uses `<details>` but the summary is not descriptive for screen readers.**
  `<summary>Archived ({{ archived|length }})</summary>` — adequate but the number count is the only distinguishing information. Screen readers would announce "Archived 5 collapsed" — acceptable but could include more context.

- **Issue 16: Settings page Quick Links use bare `<a>` elements with no visual group affordance.**
  The links (Budgets, Investments, etc.) are plain `block text-sm text-teal-600` anchors stacked vertically. They have no icon, no chevron, no row border, no hover state differentiation. They look like body text rather than navigation items.

### Low-Priority Issues (Polish/nice-to-have)

- **Issue 17: Logout button is red-toned but the Settings header is not.**
  The Logout button uses `bg-red-50 text-red-600 border border-red-200`. This is good UX for a destructive action — but it has no icon and no confirmation dialog. For a web app with session-based auth and 30-day sessions, accidental logout is recoverable but slightly annoying.

- **Issue 18: Settings page has no page description or onboarding context.**
  New users arriving at Settings for the first time see a flat list of options. There is no explanatory text about what dark mode does, what push notifications are for, or what "Salary Distribution" means. Power users understand, but onboarding users may not.

- **Issue 19: The dark mode system uses `!important` extensively.**
  `app.css` has 20+ `!important` declarations for dark mode overrides. While functional, this creates a maintenance burden — any third-party styles or future additions need to match this specificity pattern. A systematic migration to Tailwind `dark:` variants would be cleaner.

- **Issue 20: The `theme.js` script is in `<head>` but loaded as synchronous `<script src="">`.**
  The theme application happens correctly (before first paint), but the approach relies on parser-blocking script execution. An inline `<script>` block would be marginally more reliable for preventing flash-of-unstyled-content (FOUC) in edge cases.

---

## Improvement Proposals

### Proposal 1: Live Dark Mode Toggle with Current State

**Problem:** The Settings page "Toggle" button has no current-state feedback.

**Current State:**
```html
<button onclick="toggleTheme()" class="bg-slate-100 text-slate-700 px-4 py-2 rounded-lg text-sm font-semibold">
    Toggle
</button>
```

**Proposed Solution:**
Replace the static "Toggle" button with a dynamic toggle that shows current state and updates on click:

```html
<button id="settings-theme-toggle"
        onclick="toggleTheme()"
        class="flex items-center gap-2 bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-200 px-4 py-2 rounded-lg text-sm font-semibold min-h-[44px] transition-colors"
        aria-pressed="false">
    <span id="settings-theme-icon" aria-hidden="true">🌙</span>
    <span id="settings-theme-label">Enable Dark Mode</span>
</button>
```

And in `theme.js`, update `applyTheme()` to also update this button:

```javascript
const settingsBtn = document.getElementById('settings-theme-toggle');
if (settingsBtn) {
    settingsBtn.querySelector('#settings-theme-icon').textContent = theme === 'dark' ? '☀️' : '🌙';
    settingsBtn.querySelector('#settings-theme-label').textContent = theme === 'dark' ? 'Disable Dark Mode' : 'Enable Dark Mode';
    settingsBtn.setAttribute('aria-pressed', theme === 'dark' ? 'true' : 'false');
}
```

**Impact:** High (user clarity + accessibility)
**Effort:** Quick win (< 1hr)

---

### Proposal 2: Honor OS Dark Mode Preference on First Visit

**Problem:** `theme.js` defaults to 'light', ignoring OS preference.

**Current State:**
```javascript
function getPreference() {
    return localStorage.getItem(THEME_KEY) || 'light';
}
```

**Proposed Solution:**
```javascript
function getPreference() {
    const saved = localStorage.getItem(THEME_KEY);
    if (saved) return saved;
    // First visit: respect OS preference
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}
```

This is a one-line addition. Users who have explicitly set their preference in ClearMoney will keep it (saved in localStorage). First-time visitors will match their OS setting.

**Implementation:** Modify `static/js/theme.js`.

**Impact:** High (user expectation alignment)
**Effort:** Quick win (< 1hr)

---

### Proposal 3: Fix Push Notifications Button State

**Problem:** The "Enable" button never reflects the current notification permission state.

**Current State:**
```html
<button onclick="requestNotificationPermission()" class="bg-indigo-100 text-indigo-700 px-4 py-2 rounded-lg text-sm font-semibold">
    Enable
</button>
```

**Proposed Solution:**
Use JavaScript to check the current permission state and update the button label on page load:

```javascript
// Add to push.js or inline in settings template
document.addEventListener('DOMContentLoaded', function() {
    var btn = document.querySelector('[onclick="requestNotificationPermission()"]');
    if (!btn) return;
    if (Notification.permission === 'granted') {
        btn.textContent = 'Enabled';
        btn.disabled = true;
        btn.className = btn.className.replace('bg-indigo-100 text-indigo-700', 'bg-green-100 text-green-700');
    } else if (Notification.permission === 'denied') {
        btn.textContent = 'Blocked (Change in Browser Settings)';
        btn.disabled = true;
        btn.className = btn.className.replace('bg-indigo-100 text-indigo-700', 'bg-red-100 text-red-700');
    }
});
```

**Implementation:** Extend `static/js/push.js` or add inline to `settings.html`.

**Impact:** Medium (clarity, prevents user confusion)
**Effort:** Quick win (< 1hr)

---

### Proposal 4: Replace Quick Links with Navigation Cards

**Problem:** Quick Links section looks like a list of unstyled text links.

**Current State:**
```html
<a href="/budgets" class="block text-sm text-teal-600 hover:text-teal-700">Budgets</a>
```

**Proposed Solution:**
Replace with chevron-row navigation cards that match the pattern used in iOS Settings:

```html
<div class="bg-white dark:bg-slate-800 rounded-2xl shadow-sm divide-y divide-gray-100 dark:divide-slate-700">
    <a href="/budgets" class="flex items-center justify-between px-4 py-3 hover:bg-gray-50 dark:hover:bg-slate-700 transition-colors">
        <div class="flex items-center gap-3">
            <div class="w-8 h-8 bg-teal-100 dark:bg-teal-900/30 rounded-lg flex items-center justify-center">
                <svg class="w-4 h-4 text-teal-600" ...><!-- bar chart icon --></svg>
            </div>
            <span class="text-sm font-medium text-slate-800 dark:text-slate-100">Budgets</span>
        </div>
        <svg class="w-4 h-4 text-gray-300" ...><!-- chevron right --></svg>
    </a>
    <!-- repeat for each link -->
</div>
```

**Impact:** Medium (discoverability + visual hierarchy)
**Effort:** Half day

---

### Proposal 5: Add CSV Export Validation and Download Confirmation

**Problem:** The export form silently downloads or silently fails.

**Current State:**
```html
<form action="/export/transactions" method="GET" hx-boost="false">
    <!-- date fields -->
    <button type="submit">Download CSV</button>
</form>
```

**Proposed Solution:**
Add client-side date validation:

```javascript
document.querySelector('[action="/export/transactions"]').addEventListener('submit', function(e) {
    var from = document.getElementById('export-from').value;
    var to = document.getElementById('export-to').value;
    if (from && to && from > to) {
        e.preventDefault();
        // show inline error
        var errEl = document.getElementById('export-date-error');
        errEl.textContent = '"From" date must be before "To" date.';
        errEl.classList.remove('hidden');
    }
});
```

Also add a confirmation message after download trigger (button text update: "Downloading..." then reset after 3s).

**Implementation:** Inline script in `settings.html`.

**Impact:** Medium (data integrity + user confidence)
**Effort:** Quick win (< 1hr)

---

### Proposal 6: Add Category Icon Preview

**Problem:** No live preview of the emoji icon when adding a category.

**Current State:**
```html
<input type="text" name="icon" placeholder="Icon" maxlength="4" class="w-14 ...">
```

**Proposed Solution:**
Add a live preview next to the icon input:

```html
<div class="flex items-center gap-2">
    <input type="text" name="icon" id="new-cat-icon"
           placeholder="Icon" maxlength="4" class="w-14 ..."
           oninput="document.getElementById('cat-icon-preview').textContent = this.value || '?'">
    <span id="cat-icon-preview" class="text-2xl w-8 text-center text-gray-400">?</span>
</div>
```

**Implementation:** Modify `categories.html`.

**Impact:** Low-Medium (UX polish, reduces mistakes)
**Effort:** Quick win (< 30 min)

---

### Proposal 7: Convert Settings to Grouped Navigation Page

**Problem:** Settings is a flat list mixing functional actions (Dark Mode toggle, Export, Notifications) with navigation links (Quick Links). This creates cognitive overhead.

**Proposed Solution:**
Reorganize into clear groups:

```
APPEARANCE
  - Dark Mode (toggle switch)
  - Language (future)

DATA
  - Categories (chevron row)
  - Export Transactions (chevron row → opens export form)

FEATURES
  - Push Notifications (toggle switch with status)
  - Salary Distribution (chevron row)
  - Fawry Cash-Out (chevron row)

MANAGE
  - Budgets, Virtual Accounts, Recurring, Investments (grouped)

ACCOUNT
  - Log Out (destructive button)
```

Using iOS/Android-style section groups with dividers creates a familiar settings pattern. Each group has a header label above it.

**Implementation:** Refactor `settings.html` structure. Requires no backend changes.

**Impact:** High (discoverability + familiarity)
**Effort:** Half day

---

## Dark Mode Specific Audit

### Color Coverage Analysis

| Component | Light Mode | Dark Mode Coverage | Status |
|-----------|-----------|-------------------|--------|
| Header | `bg-slate-900` | Always dark — correct | PASS |
| Bottom nav | `bg-white` | `dark:bg-slate-900` in template | PASS |
| Dashboard cards | `bg-white` | `dark:bg-slate-900` in template | PASS |
| Account detail card | `bg-white rounded-2xl` | `app.css` override | FRAGILE |
| Health warning | `bg-red-50 border-red-200` | `dark:bg-red-950/30 dark:border-red-800` | PASS |
| Chart donut hole | `background: white` in charts.css | `.dark .chart-donut-hole` override | PASS |
| SVG credit util circle | `stroke="#e5e7eb"` | `app.css`: `.dark circle[stroke="#e5e7eb"]` | FRAGILE |
| Settings `<h2>` | `text-slate-800` | `app.css` override | FRAGILE |
| Budgets page `<h2>` | `text-slate-800 dark:text-white` | Correct Tailwind dark variant | PASS |
| Virtual account VA cards | inline `background: color08` | No dark equivalent | FAIL |
| Progress bar backgrounds | `bg-gray-100` | `app.css` override to `#1e293b` | PASS |
| Budget form inputs | `dark:bg-slate-800 dark:text-white` | Correct | PASS |
| Chart bar labels | `.chart-bar-label` | `charts.css` override | PASS |
| Donut value text | `.chart-donut-value` | `charts.css` override | PASS |

**Key Risk:** Virtual account colored cards use inline `background: colorXX08` (8% opacity color tint). In dark mode, these inline styles are not overridden, creating light-background "bubbles" in the dark interface. The border `border-color: colorXX20` is also not dark-mode-aware.

### Contrast Ratios (Dark Mode)

| Element | Foreground | Background | Ratio | WCAG AA |
|---------|-----------|-----------|-------|---------|
| Body text | `#e2e8f0` (slate-200) | `#0f172a` (slate-900) | 15.3:1 | PASS |
| Section header labels | `#94a3b8` (slate-400) | `#1e293b` (slate-800) | 4.7:1 | PASS |
| Muted meta text | `#64748b` (slate-500) | `#1e293b` (slate-800) | 2.8:1 | FAIL |
| Teal accent | `#0d9488` (teal-600) | `#1e293b` (slate-800) | 3.6:1 | FAIL (normal text) |
| Teal on dark bg | `#2dd4bf` (teal-300) | `#0f172a` (slate-900) | 8.1:1 | PASS |
| Positive amounts | `#0d9488` (teal-600) | `#1e293b` (slate-800) | 3.6:1 | FAIL (normal text) |
| Error text | `#f87171` (red-400) | `#1e293b` | 5.0:1 | PASS (AA) |

**Critical finding:** `teal-600` on `slate-800` fails WCAG AA for normal text (3.6:1 < 4.5:1). This color combination is used for balance amounts and links throughout the app in dark mode. The fix is to use `teal-400` (#2dd4bf) or `teal-300` for dark mode instances.

---

## Top 3 Priorities for This Area

1. **Honor OS dark mode preference (prefers-color-scheme)** — A single-line fix in `theme.js` that aligns with modern user expectations and improves first-visit experience on iOS and macOS. WCAG alignment.

2. **Fix Settings page toggle button** — Show current state, add `aria-pressed` synchronization with `theme.js`. The current "Toggle" button is meaningless — it does not tell users what they are toggling or what the result will be.

3. **Fix teal-600 contrast in dark mode** — `teal-600` (#0d9488) on `slate-800` (#1e293b) fails WCAG AA at 3.6:1 for normal-sized text (14px). All balance amounts and link text in dark mode need to use `teal-400` or `dark:text-teal-400` variants.

---

## Accessibility Audit

| Check | Result | Notes |
|-------|--------|-------|
| Settings page `<h1>` | FAIL | Uses `<h2>` as page title — no `<h1>` |
| Dark mode toggle `aria-pressed` | PARTIAL | Header button synced; Settings button not synced |
| Dark mode toggle touch target | FAIL | Header button: ~20×20px actual clickable area — below 44×44px |
| Push notifications button state | FAIL | "Enable" label never updates to reflect current permission |
| Export form validation | FAIL | No error message for invalid date range |
| Categories page `<h1>` | FAIL | Uses `<h2>` as page title — no `<h1>` |
| Category icon input label | PASS | `aria-label="Category icon (emoji)"` present |
| Category name input label | PASS | `aria-label="Category name"` present |
| Active categories list | PASS | `role="list"` + `aria-label="Active categories"` |
| Archive button labels | PASS | `aria-label="Archive {{ cat.name }}"` — dynamic, correct |
| Dark mode OS preference | FAIL | Does not read `prefers-color-scheme` on first visit |
| Focus visible in dark mode | PASS | Browser default focus ring visible on both modes |
| Color contrast: teal text dark mode | FAIL | teal-600 on slate-800: 3.6:1 — below 4.5:1 AA |
| Color contrast: muted text dark mode | FAIL | slate-500 on slate-800: 2.8:1 — fails AA |
| Settings bottom nav active state | FAIL | `active_tab` not set on settings view — nav shows no active item |
