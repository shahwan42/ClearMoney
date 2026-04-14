---
id: "040"
title: "Settings page — language toggle"
type: feature
priority: medium
status: done
created: 2026-03-30
updated: 2026-04-15
---

## Description

Add a language selector to the settings page so users can switch between English and Arabic. The toggle updates the user's `language` field and reloads the page in the selected language.

## Acceptance Criteria

- [x] Language selector added to settings page (English / العربية)
- [x] HTMX POST to update user's `language` field in DB
- [x] Page reloads in selected language after toggle (full page reload to apply `dir` and `lang` changes)
- [x] Settings page itself renders correctly in both languages
- [x] E2E test: toggle language → verify page switches
- [x] `make test` passes, `make lint` clean

## Dependencies

- Ticket #023 (user language preference) ✓
- Ticket #034 (settings template i18n) ✓

## Files

- `backend/settings_app/templates/settings_app/settings.html` — added Language section
- `backend/settings_app/views.py` — added `set_language` view
- `backend/settings_app/urls.py` — added `/settings/language` route
- `e2e/tests/test_reports_settings.py` — added `test_language_toggle_switches_language`

## Progress Notes

- 2026-03-30: Created — Language toggle in settings UI
- 2026-04-15: Implemented — Added URL route, view, and toggle UI; E2E test passes
