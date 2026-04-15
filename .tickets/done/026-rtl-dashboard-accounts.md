---
id: "026"
title: "RTL — dashboard + accounts templates"
type: feature
priority: medium
status: done
created: 2026-03-30
updated: 2026-04-15
---

## Description

Convert physical Tailwind directional classes to logical equivalents in all dashboard (15 files) and accounts (13 files) templates.

## Acceptance Criteria

- [ ] All `ml-/mr-/pl-/pr-/left-/right-/text-left/text-right` replaced with logical equivalents in dashboard templates
- [ ] All `ml-/mr-/pl-/pr-/left-/right-/text-left/text-right` replaced with logical equivalents in accounts templates
- [ ] Dashboard panels, cards, and net worth section render correctly in RTL
- [ ] Account list, forms, institution cards render correctly in RTL
- [ ] No visual regressions in LTR mode

## Dependencies

- Ticket #025 (RTL shared components)

## Files

- `backend/dashboard/templates/dashboard/` (15 files)
- `backend/accounts/templates/accounts/` (13 files)

## Progress Notes

- 2026-03-30: Created — RTL for dashboard + accounts
- 2026-04-13: Completed — All physical directional classes replaced with logical equivalents (ms-, me-, start-, end-). Dashboard and accounts templates render correctly in RTL.
