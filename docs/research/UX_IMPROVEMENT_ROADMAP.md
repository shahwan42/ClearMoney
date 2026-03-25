# ClearMoney UX Improvement Roadmap

**Audit Date:** March 25, 2026
**Status:** Complete — All 8 areas audited
**Compiled From:** 8 research documents covering Dashboard, Account Management, Transactions, Charts, Settings/Dark Mode, Mobile Responsiveness, Error/Loading States, Accessibility

---

## Executive Summary

ClearMoney is a well-engineered personal finance PWA with strong foundational UX patterns. The HTMX-powered interface is fast, the bottom-sheet interaction model is consistent, and the dark mode implementation avoids flash-of-unstyled-content. The app is functional and production-ready.

**However, a systematic audit reveals 60+ specific UX issues across three severity tiers:**

- **11 Critical issues** that block or significantly impair user tasks
- **22 High-priority issues** that create meaningful friction in daily use
- **30+ Medium/Low issues** that affect polish, accessibility, and edge cases

**The three most impactful improvement areas are:**
1. **Accessibility compliance** — 9 WCAG violations, most fixable in under 2 hours each
2. **Touch target sizing** — 5+ interactive elements below 44px minimum affect all mobile users
3. **Dark mode color contrast** — `teal-600` on `slate-800` fails WCAG AA at 3.6:1 (affects primary amounts and links in dark mode)

**Overall WCAG 2.1 Compliance:**
- Level A: ~85%
- Level AA: ~70%
- Level AAA: ~50%

---

## Complete Issue Registry

### Critical Issues

| ID | Area | Issue | WCAG | Fix Effort |
|----|------|-------|------|------------|
| C-01 | Accessibility | Dark mode toggle button (header): 20px touch target, below 44px min | 2.5.5 | Quick win |
| C-02 | Accessibility | Institution edit/delete buttons: 16px, below 44px min | 2.5.5 | Quick win |
| C-03 | Accessibility | Dashboard has no `<h1>` — only `<h2>` section headings | 1.3.1, 2.4.2 | Quick win |
| C-04 | Settings | Dark mode toggle (Settings page) has no current-state feedback — "Toggle" label never updates | 4.1.2 | Quick win |
| C-05 | Settings | `prefers-color-scheme` is ignored on first visit; OS dark mode not honored | WCAG 1.4.12 | Quick win |
| C-06 | Transactions | Transaction filter form search input missing `<label>` element (no for/aria-label) | 1.3.1 | Quick win |
| C-07 | Mobile | Landscape + virtual keyboard: iOS keyboard hides entire bottom-sheet form — no scroll-into-view | 2.5.3 | Half day |
| C-08 | Accounts | Account deletion confirmation is case-sensitive (exact match) — blocks deletion if user types lowercase | N/A | Quick win |
| C-09 | Charts | Donut chart hole background is hardcoded `white` in CSS — visible as white patch in dark mode | N/A | Quick win |
| C-10 | Dark Mode | `teal-600` (#0d9488) on `slate-800` (#1e293b) = 3.6:1 ratio — fails WCAG AA for normal text | 1.4.3 | Quick win |
| C-11 | Dark Mode | Virtual account colored cards use inline `background: colorXX08` — not dark-mode-aware, creates bright patches | N/A | Quick win |

---

### High-Priority Issues

| ID | Area | Issue | Fix Effort |
|----|------|-------|------------|
| H-01 | Dashboard | "More" menu hides Budgets, People, Recurring (daily-use features) — discoverability problem | Half day |
| H-02 | Dashboard | Dashboard has no skeleton loading state — blank flash during HTMX navigation | 1-2 days |
| H-03 | Dashboard | Net worth summary cards (2x2 grid) have no visual affordance for interactivity on touch | Quick win |
| H-04 | Dashboard | Spending section title "This Month vs Last" lacks month names (no temporal context) | Quick win |
| H-05 | Accounts | Institution action buttons have no `aria-label` — only `title` attribute (not read by all screen readers) | Quick win |
| H-06 | Accounts | Custom account name field is hidden behind a toggle — a standard UX feature should be visible by default | Half day |
| H-07 | Accounts | No success feedback when account is created (bottom sheet closes silently) | Quick win |
| H-08 | Transactions | Quick entry tab labels: "Transaction", "Exchange", "Transfer" — "Transaction" is ambiguous (should be "Expense/Income") | Quick win |
| H-09 | Transactions | Transaction filter form: no "Clear filters" button — users can only reset by refreshing | Half day |
| H-10 | Transactions | Delete transaction uses browser `hx-confirm` dialog — does not match app's bottom-sheet design pattern | Half day |
| H-11 | Charts | Bar chart labels use 0.625rem (10px) — below 11px accessibility minimum for small text | Quick win |
| H-12 | Charts | Bar chart has no data table fallback for screen readers — only `role="img"` with single `aria-label` | Half day |
| H-13 | Settings | Push notifications "Enable" button never reflects current permission state | Quick win |
| H-14 | Settings | Settings page has no `active_tab` set — no active item highlighted in bottom nav | Quick win |
| H-15 | Settings | Quick Links section in Settings duplicates the More menu — confusing secondary navigation | Half day |
| H-16 | Error States | Error messages from server (400 responses) have no field-level association (`aria-describedby`) | Half day |
| H-17 | Error States | No "undo" option after transaction deletion — browser dialog is the only safeguard | 1-2 days |
| H-18 | Mobile | Virtual accounts horizontal scroll has no scroll indicator — users may not discover scrollable content | Quick win |
| H-19 | Mobile | Bottom sheet forms on 320px iPhone SE: buttons too close to keyboard dismiss area | Half day |
| H-20 | Accessibility | Form validation errors not associated with specific fields — no `aria-invalid` or `aria-describedby` | Half day |
| H-21 | Accessibility | Delete confirmation input not announced to screen readers when unhidden | Quick win |
| H-22 | Accessibility | Donut chart: category slices have no accessible legend fallback | Half day |

---

### Medium-Priority Issues

| ID | Area | Issue | Fix Effort |
|----|------|-------|------------|
| M-01 | Dashboard | Streak widget (🔥 emoji) not hidden from screen readers | Quick win |
| M-02 | Dashboard | Virtual accounts scroll fade indicator missing (users don't know it scrolls) | Quick win |
| M-03 | Dashboard | Health warning cards are links but have no CTA text or chevron affordance | Quick win |
| M-04 | Dashboard | Spending velocity bar uses 2px hairline "today" marker — barely visible | Quick win |
| M-05 | Dashboard | Header has duplicate links to Accounts (also in bottom nav) and Settings (also in More) | Half day |
| M-06 | Dashboard | Pull-to-refresh has no visible indicator or threshold marker | Half day |
| M-07 | Accounts | Account type icons missing — no visual differentiation between Checking, Savings, Credit Card | Half day |
| M-08 | Accounts | Credit card "available credit" shown as small gray text — same visual weight as type/currency | Quick win |
| M-09 | Transactions | Category combobox has no visual hint it's searchable (no magnifier icon, no "Search" placeholder) | Quick win |
| M-10 | Transactions | "Load more" button on transaction list has no loading state | Quick win |
| M-11 | Transactions | Date filter range (From/To) has no visual connection or range indicator | Half day |
| M-12 | Charts | Donut chart segments: slices under 5% are too thin to distinguish or tap | 1-2 days |
| M-13 | Charts | Sparkline opacity fill is very subtle (0.1) — nearly invisible on accounts with small ranges | Quick win |
| M-14 | Charts | Bar chart bars have no value labels or tooltips — amounts only visible by reading the table below | Half day |
| M-15 | Settings | Settings page `<h2>` used as page title (no `<h1>`) — heading hierarchy violation | Quick win |
| M-16 | Settings | Categories page: Archive confirmation uses full-page form POST (no HTMX, no spinner) | Half day |
| M-17 | Settings | CSV export form: no date-range validation — silent empty download on invalid range | Quick win |
| M-18 | Error States | Empty state on transactions list: "No transactions found" has no illustration or CTA | Quick win |
| M-19 | Error States | 429 rate limit page has no retry timer | Half day |
| M-20 | Error States | Skeleton loading exists in CSS but is not used in dashboard sections | 1-2 days |
| M-21 | Mobile | Tablet layout (768px+) is single-column — could benefit from 2-column adaptive layout | 1-2 days |
| M-22 | Mobile | Long transaction notes truncate without indication — user cannot see full note in list view | Quick win |
| M-23 | Accessibility | Settings page dark mode button `aria-pressed` not synchronized with theme.js updates | Quick win |
| M-24 | Accessibility | Report page has no `<h1>` | Quick win |
| M-25 | Accessibility | Section header labels: gray-500 (#6b7280) on white: 3.95:1 — just below 4.5:1 AA for normal text | Quick win |

---

### Low-Priority Issues (Polish)

| ID | Area | Issue | Fix Effort |
|----|------|-------|------------|
| L-01 | Dashboard | Section title casing inconsistent (UPPERCASE vs Title Case) | Quick win |
| L-02 | Dashboard | "View All" link in Recent Transactions is 14px text — borderline touch target | Quick win |
| L-03 | Accounts | Dormant toggle button text inverted: "Active" means "mark as dormant", confusing | Quick win |
| L-04 | Transactions | Quick transfer and exchange tabs have no keyboard navigation between tab panels | Half day |
| L-05 | Charts | Trend arrows (▲▼) use Unicode — some screen readers announce as "up-pointing triangle" | Quick win |
| L-06 | Charts | No chart legend on the donut for the first time without data — empty chart state | Quick win |
| L-07 | Settings | Export CSV button has no feedback on download start | Quick win |
| L-08 | Settings | Logout button has no confirmation — single click logs out immediately | Quick win |
| L-09 | Error States | Browser native `confirm()` dialog for delete — inconsistent with app design language | Half day |
| L-10 | Accessibility | Offline indicator (offline.js) has no `aria-live` announcement for screen readers | Quick win |

---

## Implementation Timeline

### Phase 0: Quick Wins — Do Today (< 1 hour each, cumulative ~8 hours)

These are small template or CSS changes with no Python changes needed.

| Priority | Task | File(s) | Notes |
|----------|------|---------|-------|
| 1 | Fix `teal-600` dark mode contrast — use `dark:text-teal-400` on balance amounts | `app.css` + templates | Replace `color: #0d9488` with `color: #2dd4bf` in dark mode |
| 2 | Add `<h1>` to dashboard (greeting/date bar) | `home.html` | Simple markup addition |
| 3 | Honor `prefers-color-scheme` in theme.js | `static/js/theme.js` | 1-line change |
| 4 | Update Settings page dark mode toggle to show current state | `settings.html` + `theme.js` | Sync `aria-pressed` + update label |
| 5 | Fix institution edit/delete button touch targets (add padding) | `_institution_card.html` | `p-2` instead of `px-1 py-1` |
| 6 | Add `aria-label` to institution action buttons | `_institution_card.html` | `aria-label="Edit [name]"` |
| 7 | Add month names to spending section title ("March vs February") | `_spending.html` | Pass month labels from view |
| 8 | Add visual affordance (chevron + `active:bg-gray-100`) to net worth summary cards | `_net_worth.html` | Small SVG + active state |
| 9 | Add virtual accounts right-edge gradient scroll indicator | `_virtual_accounts.html` | 1 new div with gradient |
| 10 | Fix push notifications button state in Settings | `settings.html` + `push.js` | Check `Notification.permission` on load |
| 11 | Add `active_tab='more'` to settings view | `settings_app/views.py` | 1-line Python change |
| 12 | Fix donut chart dark mode — remove hardcoded `background: white` | `charts.css` | Use CSS variable or dark override |
| 13 | Fix virtual account card dark mode inline styles | `_virtual_accounts.html` | Add dark variant borders |
| 14 | Add streak emoji `aria-hidden="true"` with visually-hidden text | `_streak.html` | 2-line change |
| 15 | Improve spending velocity "today" marker visibility | `_spending.html` | Use tick mark above bar |
| 16 | Add `<h1>` to Settings page (change `<h2>` to `<h1>`) | `settings.html` | Single tag change |
| 17 | Add `<h1>` to Reports page | `reports.html` | Single tag change |
| 18 | Make deletion confirmation case-insensitive | `account_detail.html` (JS) | `.toLowerCase()` comparison |
| 19 | Add CSV export date-range validation | `settings.html` | Inline JS validation |
| 20 | Add category icon preview | `categories.html` | `oninput` + preview span |

---

### Phase 1: High Impact — Sprint 1 (2-4 hours each, cumulative ~2 days)

These require slightly more thought but are still contained.

| Priority | Task | Files | Estimated Time |
|----------|------|-------|---------------|
| 1 | **Fix form validation error association** — add `aria-invalid` and `aria-describedby` to all form fields | All form templates | Half day |
| 2 | **Add transaction Quick Entry tab clarity** — rename "Transaction" tab to "Expense / Income" | `bottom-nav.html` | 1 hour |
| 3 | **Add success feedback when account is created** — toast notification | `_add_account_form.html` + account view | 1 hour |
| 4 | **Add "Clear filters" button** to transaction filter bar | `transactions.html` + `_transaction_list.html` | 2 hours |
| 5 | **Replace browser `hx-confirm` delete dialog** with styled in-page confirmation | `_transaction_row.html` | Half day |
| 6 | **Add bar chart value labels** (small text above each bar) | `chart-bar.html` + `charts.css` | 2 hours |
| 7 | **Increase bar chart label font size** from 0.625rem to 0.75rem | `charts.css` | Quick |
| 8 | **Add account type icon** to account rows in accounts list | `_institution_card.html` | 2 hours |
| 9 | **Add "Load more" spinner** to transaction pagination button | `_transaction_list.html` | 1 hour |
| 10 | **Reorganize Settings page** into logical groups with section headers | `settings.html` | Half day |
| 11 | **Fix scroll-into-view on focus** for bottom-sheet form inputs | `static/js/bottom-sheet.js` | Half day |
| 12 | **Add Quick Links chevron-row navigation pattern** to Settings | `settings.html` | 2 hours |

---

### Phase 2: Architecture Improvements — Sprint 2 (1-2 days each)

These are meaningful UX improvements that require some Django backend work.

| Priority | Task | Description | Estimated Time |
|----------|------|-------------|---------------|
| 1 | **Promote Budgets to bottom navigation** | Swap Accounts in bottom nav for Budgets (or use Reports as the 5th tab). Move Accounts to header-only. | Half day |
| 2 | **Dashboard skeleton loading** | Add HTMX lazy loading for heavy sections (spending, budgets, credit cards). Render net worth card first. | 1-2 days |
| 3 | **Transaction undo** | After delete, show 5-second undo toast. Delay actual DB delete by 5 seconds or use soft-delete pattern. | 1-2 days |
| 4 | **Collapsible dashboard sections** | Wrap Investments, People, Streak in `<details>` with `localStorage` persistence for collapse state. | Half day |
| 5 | **Donut chart screen reader data table** | Add visually-hidden `<table>` with category names and amounts next to donut chart. | 1 day |
| 6 | **Category combobox search hint** | Add search icon and "Search categories..." placeholder that's clearly styled as a search field. | 1 hour |
| 7 | **Transaction filter date range indicator** | Show "X transactions from DATE to DATE" label below filters when active. | Half day |

---

### Phase 3: Major Initiatives — Sprint 3+ (1 week+)

These are larger, cross-cutting improvements.

| Priority | Task | Description | Estimated Time |
|----------|------|-------------|---------------|
| 1 | **Tablet-adaptive layout** | Implement 2-column grid at 768px+ for dashboard, accounts, and transactions. | 1 week |
| 2 | **Systematic dark mode migration** | Replace all `!important` overrides in `app.css` with proper `dark:` Tailwind variants in templates. | 1 week |
| 3 | **Onboarding flow** | Empty state dashboard: show preview of features with illustration. Add onboarding checklist (add account → add transaction → set budget). | 1 week |
| 4 | **Dashboard personalization** | Allow users to reorder and hide dashboard sections. Store preferences server-side. | 2+ weeks |
| 5 | **Chart interactivity** | Tap on donut slices to drill down to filtered transactions. Tap on bar groups to see month detail. | 2 weeks |

---

## Impact/Effort Matrix

```
HIGH IMPACT
    |  [Dark mode contrast]   [h1 heading]          [Skeleton loading]
    |  [touch targets]        [prefers-color-scheme] [Undo delete]
    |  [form aria-invalid]    [Quick wins batch]     [Budgets in nav]
    |
    |  [Settings page reorg]  [Account type icons]   [Tablet layout]
    |  [Add clear filters]    [Onboarding flow]
    |
LOW |  [Chart value labels]   [Section titles]       [Dark mode migration]
    |  [Streak aria]          [Scroll indicators]
    +--LOW effort------------------------HIGH effort-->
```

### Effort x Impact Tiers

**Tier 1: Easy + High Impact (Do first)**
- Fix teal-600 dark mode contrast (1 line of CSS)
- Add `<h1>` to dashboard, settings, reports (3 template files)
- Honor `prefers-color-scheme` (1 line JS)
- Fix institution button touch targets (padding addition)
- Add month names to spending section
- Fix Settings toggle button state

**Tier 2: Medium effort, High impact**
- Add form validation error field association (`aria-invalid` + `aria-describedby`)
- Replace `hx-confirm` with styled delete confirmation
- Dashboard skeleton loading states
- Promote Budgets to bottom navigation

**Tier 3: Higher effort, Worth it**
- Transaction undo (soft delete + toast)
- Donut chart accessibility table
- Tablet adaptive layout
- Systematic dark mode migration

---

## Accessibility Compliance Summary

### Current Status: WCAG 2.1 Level AA ~70%

| Criterion | Status | Notes |
|-----------|--------|-------|
| 1.1.1 Non-text Content | PARTIAL | Most SVG icons have aria-hidden; some charts lack data alternatives |
| 1.3.1 Info and Relationships | PARTIAL | Good semantic HTML; missing `<h1>` on several pages; form errors not associated to fields |
| 1.3.3 Sensory Characteristics | PASS | Color not the only means of conveying information (labels present) |
| 1.4.1 Use of Color | PASS | Color is supplementary (text labels accompany all color-coded elements) |
| 1.4.3 Contrast (Minimum) | PARTIAL | Several failures: teal-600 on slate-800 (dark mode, 3.6:1), gray-500 labels on white (3.95:1) |
| 1.4.4 Resize Text | PASS | Uses relative units; no fixed px text sizes that don't scale |
| 1.4.10 Reflow | PASS | Single-column layout reflows well at 320px |
| 1.4.12 Non-text Contrast | PARTIAL | OS dark mode preference ignored |
| 2.1.1 Keyboard | PASS | All interactive elements keyboard-accessible |
| 2.1.2 No Keyboard Trap | PASS | Bottom sheets include Escape key close |
| 2.4.2 Page Titled | PARTIAL | HTML `<title>` tags present; visible page `<h1>` missing on several pages |
| 2.4.3 Focus Order | PASS | Tab order is logical on all tested pages |
| 2.4.4 Link Purpose | PARTIAL | "View All", "Manage" links lack context in some placements |
| 2.4.7 Focus Visible | PASS | Browser default focus rings visible |
| 2.5.3 Label in Name | PARTIAL | Several icon-only buttons miss accessible labels |
| 2.5.5 Target Size | FAIL | 5+ interactive elements below 44×44px minimum |
| 3.1.1 Language of Page | PASS | `<html lang="en">` present |
| 3.3.1 Error Identification | PARTIAL | Errors shown but not associated to specific fields |
| 3.3.2 Labels or Instructions | PARTIAL | Most inputs labeled; some edge cases missing |
| 4.1.2 Name, Role, Value | PARTIAL | `aria-pressed` on some toggles but not all; `aria-expanded` on accordions |

---

## Quick Wins Batch Script

The following changes can be made in a single focused session (~4-6 hours) and collectively move WCAG compliance from ~70% to ~82%:

1. `static/js/theme.js` — Add `prefers-color-scheme` fallback (2 lines)
2. `static/css/app.css` — Add `dark:text-teal-400` override for balance amounts (5 lines)
3. `static/css/charts.css` — Fix donut hole dark mode (2 lines)
4. `backend/templates/components/header.html` — Increase dark toggle button padding to `p-2`
5. `backend/accounts/templates/accounts/_institution_card.html` — Increase action button padding, add `aria-label`
6. `backend/dashboard/templates/dashboard/home.html` — Add `<h1>` greeting bar
7. `backend/dashboard/templates/dashboard/_spending.html` — Add month name to title
8. `backend/dashboard/templates/dashboard/_net_worth.html` — Add chevrons and `active:` state to 2x2 grid
9. `backend/dashboard/templates/dashboard/_virtual_accounts.html` — Add fade indicator + `aria-label` on scroll container
10. `backend/dashboard/templates/dashboard/_streak.html` — Add `aria-hidden="true"` to emoji
11. `backend/settings_app/templates/settings_app/settings.html` — Fix toggle label + `<h2>` → `<h1>` + add push permission state check
12. `backend/reports/templates/reports/reports.html` — Change `<h2>` to `<h1>`
13. `backend/accounts/templates/accounts/account_detail.html` (JS) — Case-insensitive deletion check

---

## Files Requiring Changes by Module

### Quick Win Changes (no Python required)

| File | Changes Needed |
|------|---------------|
| `static/js/theme.js` | Add `prefers-color-scheme` fallback; update Settings toggle |
| `static/css/app.css` | Add teal dark mode contrast fix; fix virtual account cards |
| `static/css/charts.css` | Fix donut hole dark mode background |
| `templates/components/header.html` | Increase dark toggle touch target |
| `templates/components/bottom-nav.html` | N/A (currently fine) |
| `dashboard/home.html` | Add `<h1>` greeting |
| `dashboard/_spending.html` | Month name in title |
| `dashboard/_net_worth.html` | Chevrons + active states on grid |
| `dashboard/_virtual_accounts.html` | Scroll fade indicator |
| `dashboard/_streak.html` | `aria-hidden` on emoji |
| `accounts/_institution_card.html` | Touch target + aria-labels |
| `accounts/account_detail.html` | Case-insensitive delete confirmation |
| `settings_app/settings.html` | Toggle label + heading fix + push state |
| `settings_app/categories.html` | Icon preview |
| `reports/reports.html` | `<h1>` heading |

### Backend Changes Required

| File | Changes Needed |
|------|---------------|
| `settings_app/views.py` | Set `active_tab='more'` in context |
| `dashboard/views.py` | Pass month label strings to spending context |
| `transactions/views.py` | No changes for quick wins |

---

## Tracking Progress

### Recommended Metrics

After implementing improvements, track:

1. **WCAG compliance score** — Target: Level AA 90%+
2. **Touch target compliance** — All interactive elements >= 44×44px
3. **Contrast failures** — Zero AA failures in both light and dark mode
4. **Core task completion time** — Add transaction: target < 30 seconds
5. **Error recovery rate** — What % of form errors do users successfully correct

### Definition of Done for Each Phase

**Phase 0 (Quick Wins):**
- All 20 items from Quick Wins list committed
- `make test` passes
- `make lint` passes (zero errors)
- Contrast check passes for teal colors in dark mode

**Phase 1:**
- All high-priority issues addressed
- Manual keyboard navigation test: no stuck focus
- Form validation: all errors associated to fields
- `make test-e2e` passes

**Phase 2:**
- Skeleton loading tested on throttled connection (Chrome DevTools: Slow 3G)
- Budgets in bottom nav with `active_tab` coverage in all views
- Transaction undo e2e test added

---

## Research Document Index

| Document | Size | Status | Key Issues Count |
|----------|------|--------|-----------------|
| `UX_DASHBOARD_NAVIGATION.md` | 824 lines | Complete | 18 issues, 8 proposals |
| `UX_ACCOUNT_MANAGEMENT.md` | 1,074 lines | Complete | 7+ critical, full workflow analysis |
| `UX_TRANSACTION_MANAGEMENT.md` | 767 lines | Complete | Form UX, batch entry, gestures |
| `UX_CHARTS_VISUALIZATIONS.md` | 1,149 lines | Complete | Color contrast, dark mode, accessibility |
| `UX_SETTINGS_DARK_MODE.md` | 360 lines | Complete | 20 issues, 6 proposals, contrast audit |
| `UX_MOBILE_RESPONSIVENESS.md` | 853 lines | Complete | Touch targets, keyboard, landscape |
| `UX_ERROR_LOADING_EMPTY.md` | 993 lines | Complete | State patterns, empty states, feedback |
| `UX_ACCESSIBILITY_AUDIT.md` | 1,336 lines | Complete | WCAG audit, 9 critical, 8 high |
| `MULTI_CURRENCY_UX_PATTERNS.md` | 569 lines | Complete | Multi-currency display patterns |

**Total documented:** ~8,600 lines of research
**Total issues identified:** 63 specific issues
**Total improvement proposals:** 35+ actionable proposals

---

## Next Steps

1. **Review this roadmap** with Ahmed and prioritize Phase 0
2. **Implement Phase 0** in a single focused session (4-6 hours)
3. **Run `make test && make lint`** to confirm no regressions
4. **Manual dark mode check** — navigate all pages in dark mode, look for light islands
5. **Keyboard navigation check** — Tab through dashboard, accounts, transaction add flow
6. **Plan Phase 1 sprint** — estimate 2-3 days of work

---

**Last Updated:** 2026-03-25
**Authors:** ClearMoney UX Audit Team (comprehensive code review + template analysis)
