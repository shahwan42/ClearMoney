---
id: "154"
title: "Fix pull-to-refresh scroll bug"
type: bug
priority: high
status: done
created: 2026-04-24
updated: 2026-04-24
---

## Description

The custom pull-to-refresh logic in `gestures.js` incorrectly triggers even when the page is scrolled down. This happens because it checks `window.scrollY`, but the actual scrolling happens inside the `main#main-content` element, leaving `window.scrollY` always at 0.

Additionally, native browser pull-to-refresh is not explicitly disabled on the `main` element, leading to potential conflicts and "blank page" issues on mobile devices.

## Acceptance Criteria

- [x] `gestures.js` checks the `scrollTop` of the actual scrolling container instead of `window.scrollY`.
- [x] `overscroll-behavior-y: none` is applied to the `main` element to prevent native browser pull-to-refresh interference.
- [x] Pull-to-refresh only triggers when the user is at the very top of the scroll container.
- [x] The refresh indicator only appears when a valid pull-to-refresh gesture is initiated from the top.

## Progress Notes

- 2026-04-24: Started — Identified root cause in `gestures.js` and `app.css`.
- 2026-04-24: Completed — Updated `gestures.js` to use correct scroll container `scrollTop`, added `overscroll-behavior-y: none` to `main` in `app.css`. Added E2E tests in `e2e/tests/test_gestures.py` to verify fix. All tests passing.
