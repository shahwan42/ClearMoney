---
id: "095"
title: "Loading skeletons for HTMX content"
type: improvement
priority: medium
status: pending
created: 2026-03-31
updated: 2026-03-31
---

## Description

Skeleton CSS is defined in `app.css:164-173` but never used in templates. HTMX-loaded content (net worth, quick-entry sheet, account details) appears with a jump. Add skeleton placeholders for smooth loading.

## Acceptance Criteria

- [ ] Skeleton placeholder shown while net worth section loads on dashboard
- [ ] Skeleton placeholder in quick-entry bottom sheet before form loads
- [ ] Skeleton placeholder on account detail while data loads
- [ ] Skeleton matches approximate layout of final content (correct heights/widths)
- [ ] Skeleton uses existing `.skeleton` CSS class with pulse animation
- [ ] `aria-busy="true"` set on container during loading, `"false"` when content arrives
- [ ] Dark mode compatible (skeleton color adjusts)
- [ ] E2E test verifying skeleton appears briefly before content

## Technical Notes

- Existing CSS: `.skeleton` class in `static/css/app.css:164-173` (pulse animation)
- Use HTMX `hx-indicator` or place skeleton as default content inside `hx-target` divs
- HTMX swaps replace skeleton automatically when response arrives
- Key locations: `home.html` (net worth, spending partials), `bottom-nav.html` (quick-entry), `account_detail.html`

## Progress Notes

- 2026-03-31: Created — leverages existing CSS that's never been used in templates
