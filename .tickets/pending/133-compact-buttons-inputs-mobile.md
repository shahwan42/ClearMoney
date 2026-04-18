---
id: "133"
title: "Compact buttons and inputs for better mobile visuals"
type: improvement
priority: medium
status: pending
created: 2026-04-18
updated: 2026-04-18
---

## Description

Buttons and input fields across the app feel too tall/padded on mobile screens, making forms visually heavy. Additionally, some inputs and buttons overflow their container or ignore horizontal padding, causing layout issues on narrow viewports.

Two goals:
1. **Compact sizing** — reduce vertical padding on buttons and inputs so they feel lighter and more native on mobile without sacrificing tap target minimums (WCAG 2.5.5: 44×44px target).
2. **Width containment** — no input or button may exceed its container's inner width (i.e., `max-width: 100%` with `box-sizing: border-box` respected). All widths must account for the container's padding.

## Scope

Applies globally to:
- All `<input>`, `<select>`, `<textarea>` elements
- All `<button>` and `<a class="btn*">` elements
- Bottom sheet forms (transaction new, transfer, exchange)
- Settings, accounts, budgets, people, recurring, virtual accounts pages
- Any inline form within HTMX partials

## Acceptance Criteria

- [ ] Button vertical padding reduced: `py-2` → `py-1.5` (Tailwind) or equivalent, keeping min-height ≥ 44px on touch targets
- [ ] Input vertical padding reduced: `py-2` → `py-1.5` consistently across all forms
- [ ] No input or button has a computed width wider than `container width − container padding` on any screen ≤ 430px (iPhone Pro Max)
- [ ] `box-sizing: border-box` enforced on all form elements (can be global via base stylesheet)
- [ ] `max-w-full` or `w-full` used correctly so elements don't escape their parent
- [ ] All form elements remain keyboard accessible (visible focus ring, Tab order unchanged)
- [ ] Tap targets remain ≥ 44×44px (WCAG 2.5.5) — verify with Playwright viewport 390×844
- [ ] No horizontal scroll introduced on any page at 390px viewport width
- [ ] Dark mode unaffected — no color or contrast regressions
- [ ] `make lint` passes (zero ruff + mypy errors)
- [ ] `make test` count ≥ baseline (no tests deleted)
- [ ] Playwright visual snapshot confirms compact appearance on mobile viewport

## Implementation Notes

### Tailwind classes to audit
- `py-2`, `py-3`, `px-4`, `px-6` on `<input>`, `<button>`, `<a>` — reduce by one step where > `py-1.5`
- `w-full` missing on some inputs inside padded containers — add it
- `min-w-0` may be needed inside flex rows to prevent overflow

### CSS global fix (base.html or static/css)
```css
*, *::before, *::after {
  box-sizing: border-box;
}
input, select, textarea, button {
  max-width: 100%;
}
```

### Key files to touch
- `backend/templates/base.html` — global style block
- `backend/transactions/templates/transactions/transaction_new.html`
- `backend/transactions/templates/transactions/_transfer_form.html`
- `backend/accounts/templates/accounts/_account_form.html`
- `backend/accounts/templates/accounts/_add_account_form.html`
- `backend/budgets/templates/budgets/budgets.html`
- `backend/people/templates/people/people.html`
- `backend/recurring/templates/recurring/_form.html`
- `backend/virtual_accounts/templates/virtual_accounts/virtual_accounts.html`

### Testing approach
1. Open Playwright at 390px viewport (iPhone 14)
2. Snapshot each form page — visually confirm compact layout
3. Tab through all inputs — confirm focus rings visible
4. Measure element widths with `browser_evaluate` — confirm none exceed viewport − padding

## Progress Notes

- 2026-04-18: Created — Ticket captures compact UI + overflow containment requirements for mobile forms
