---
id: "506"
title: "Rename Gas category to Fuel"
type: improvement
priority: medium
status: done
created: 2026-04-27
updated: 2026-04-27
---

## Description

Rename the system default "Gas" category to "Fuel" across all existing users and new registrations. Also update the Arabic name (غاز → وقود) and icon (🔥 → ⛽) to match vehicle fuel semantics.

## Acceptance Criteria

- [x] All existing `categories` rows with `name->>'en' = 'Gas'` and `is_system = true` updated to Fuel/وقود/⛽
- [x] Seed in `auth_app/services.py` updated so new users get Fuel category
- [x] Migration runs cleanly, tests pass

## Progress Notes

- 2026-04-27: Started — writing data migration + seed update
- 2026-04-27: Completed — migration 0008_rename_gas_to_fuel applied, seed updated in auth_app/services.py
