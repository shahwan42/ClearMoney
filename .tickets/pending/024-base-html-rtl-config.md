---
id: "024"
title: "base.html — dynamic lang/dir + RTL Tailwind config"
type: feature
priority: high
status: pending
created: 2026-03-30
updated: 2026-03-30
---

## Description

Update `base.html` to dynamically set the HTML `lang` and `dir` attributes based on the active language. Configure Tailwind CDN to support RTL variants. Add an Arabic web font.

## Acceptance Criteria

- [ ] `<html lang="{{ LANGUAGE_CODE }}" dir="{% if LANGUAGE_CODE == 'ar' %}rtl{% else %}ltr{% endif %}">`
- [ ] Tailwind CDN configured to support `rtl:` variant classes
- [ ] Arabic web font added (e.g., Noto Sans Arabic or IBM Plex Sans Arabic) with appropriate `font-family` fallback
- [ ] When user language is Arabic, page renders RTL with Arabic font
- [ ] When user language is English, page renders LTR as before (no regression)
- [ ] `make test` passes, `make lint` clean

## Dependencies

- Ticket #023 (user language preference)

## Files

- `backend/templates/base.html`

## Progress Notes

- 2026-03-30: Created — RTL foundation in base template
