---
id: "100"
title: "Smarter More menu organization"
type: improvement
priority: medium
status: pending
created: 2026-03-31
updated: 2026-03-31
---

## Description

The "More" menu has 10 items across 3 sections, making it overwhelming. Reorganize with better grouping, badge unvisited items, or promote the most-used item (Budgets) to a dedicated bottom-nav tab.

## Acceptance Criteria

- [ ] Option A: Promote Budgets to bottom nav (replace "More" icon label, keep More as last item)
- [ ] Option B: Add usage-based ordering — most-tapped items float to top
- [ ] Badge new/unvisited items with a dot indicator (first-time discovery)
- [ ] Group items with clearer section headers and icons
- [ ] Consider removing duplicate nav (Reports/Settings in both header and More menu)
- [ ] Keyboard navigable: arrow keys move between items
- [ ] E2E test for navigating More menu items

## Technical Notes

- Template: `backend/templates/components/bottom-nav.html:85-166`
- Option A is simpler — just swap the 5th tab from "More" to "Budgets" and move More into header
- Badge state: localStorage tracks which menu items have been visited
- Current sections: Money Management (4), Automation (2), App (2) + Reports + Settings

## Progress Notes

- 2026-03-31: Created — addresses overloaded More menu discoverability
