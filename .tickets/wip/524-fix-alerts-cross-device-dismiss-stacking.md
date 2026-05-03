---
id: "524"
title: "Fix alerts: cross-device dismiss, stacking, won't-close"
type: bug
priority: high
status: wip
created: 2026-05-03
updated: 2026-05-03
---

## Description

Banner alerts have three bugs:
1. Dismiss stored in localStorage → closing on device A has no effect on device B
2. Multiple alerts stack visually with no limit
3. Dismiss button sometimes fails to close (localStorage race condition)

## Affected User Journeys

- CP-5 (Dashboard): notification banner is part of every page load
- J-1 (Setup): alerts visible on first session across devices

## Acceptance Criteria

- [ ] Dismissing an alert on one device hides it on all devices
- [ ] Maximum 1 banner shown; extras collapsed into "N more →" pill → `/notifications`
- [ ] Priority order: CC due 0-1d → CC due 2-3d → health → budget ≥100% → budget ≥80% → recurring
- [ ] Dismiss persists across page loads and devices (DB-backed, not localStorage)
- [ ] When a resolved condition recurs, the alert reappears (no stale is_read block)
- [ ] No auto-dismiss — banner stays until explicitly closed
- [ ] `make test` passes, `make lint` passes

## Implementation Plan

1. `generate_and_persist`: delete ALL (read+unread) for resolved tags so recurrence shows fresh
2. `check_notifications` view: call `generate_and_persist()`, return unread DB records as JSON including `id` field
3. `push.js`: replace localStorage dismiss logic with `fetch POST /notifications/<id>/read`; render only top (highest priority) notification + "N more →" pill if count > 1
4. Priority sorting in `check_notifications` response (server-side)

## Progress Notes

- 2026-05-03: Started — grilled design, agreed spec, beginning implementation
- 2026-05-03: Implemented — generate_and_persist on every poll, DB-backed dismiss via POST /api/push/dismiss/<id>, priority sorting, max-1-banner + collapse pill, +6 tests (1853 total), lint clean
