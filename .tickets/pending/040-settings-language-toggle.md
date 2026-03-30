---
id: "040"
title: "Settings page — language toggle"
type: feature
priority: medium
status: pending
created: 2026-03-30
updated: 2026-03-30
---

## Description

Add a language selector to the settings page so users can switch between English and Arabic. The toggle updates the user's `language` field and reloads the page in the selected language.

## Acceptance Criteria

- [ ] Language selector added to settings page (English / العربية)
- [ ] HTMX POST to update user's `language` field in DB
- [ ] Page reloads in selected language after toggle (full page reload to apply `dir` and `lang` changes)
- [ ] Settings page itself renders correctly in both languages
- [ ] E2E test: toggle language → verify page switches
- [ ] `make test` passes, `make lint` clean

## Dependencies

- Ticket #023 (user language preference)
- Ticket #034 (settings template i18n — so the settings page itself is translated)

## Files

- `backend/settings_app/templates/settings_app/settings.html`
- `backend/settings_app/views.py`
- `backend/settings_app/services.py` (or inline in view)

## Progress Notes

- 2026-03-30: Created — Language toggle in settings UI
