---
id: "160"
title: "Better feedback after recurring rule creation"
type: improvement
priority: medium
status: done
created: 2026-04-26
updated: 2026-04-26
---

## Description

POST `/recurring/add` currently re-renders the rule list silently on success — no confirmation that the rule was saved, no summary of what was created. Replace with a confirmation sheet (mirrors the `_confirm_form.html` pattern from commit d328058) that shows what was just created and offers "Done" / "Add another".

## Acceptance Criteria

- [ ] POST /recurring/add success returns a confirmation sheet (not silent list re-render)
- [ ] Sheet shows: checkmark, "Rule created" heading, summary line, next-due copy
- [ ] Summary line: type prefix if non-expense; amount + currency; note (fallback to category); frequency
  - Examples: `EGP 500 — Vodafone bill — monthly` / `Income: EGP 5000 — Salary — monthly`
- [ ] Next-due copy is conditional on auto_confirm:
  - auto_confirm=true → "Will auto-post EGP {amount} on {next_due}."
  - auto_confirm=false → "Next reminder: {next_due}."
- [ ] Sheet has two actions: "Done" (closes sheet) and "Add another"
- [ ] "Add another" loads blank form with sticky values via query string: `account_id`, `frequency`, `auto_confirm`
- [ ] Non-sticky fields reset: amount, note, person, category, next_due_date
- [ ] List refreshes on each successful creation via HX-OOB swap (no row highlight)
- [ ] Error path unchanged (400 + existing red banner)
- [ ] New template `backend/recurring/templates/recurring/_create_success.html`
- [ ] View tests:
  - [ ] success returns sheet HTML with summary + next-due copy
  - [ ] auto_confirm=true → "auto-post" wording
  - [ ] auto_confirm=false → "next reminder" wording
  - [ ] success response contains HX-OOB list swap
  - [ ] GET /recurring/new with sticky query params prefills form
  - [ ] error path still returns 400 + red banner (regression)
- [ ] E2E tests:
  - [ ] create rule → success sheet visible with summary + next due
  - [ ] click "Add another" → form re-renders blank except sticky fields
  - [ ] click "Done" → sheet closes, list shows new rule
- [ ] `make test`, `make lint`, `make test-e2e` all green

## Progress Notes

- 2026-04-26: Created — design grilled via /grill-me. Plan: confirmation sheet swap (option 3 from Q2), standard content (Q3 #2), Done + Add another (Q4 #2), sticky account/frequency/auto_confirm (Q5 #2 + account), refresh on each / no highlight (Q6 #1), conditional auto_confirm copy (Q7 #2), note→category fallback with type prefix (Q8 #4), single response + HX-OOB + query-string sticky (Q9 a1).
- 2026-04-26: Implemented — wrapped form in `#recurring-form-container`, retargeted form's hx-post, added `_create_success.html` partial, new `recurring_form` GET endpoint for sticky prefill, OOB list swap. 5 new view tests + 3 new E2E tests. All 1592 unit tests pass. Note: pre-existing mypy/format issue on `recurring/services.py` left untouched (not introduced by this ticket).
- 2026-04-26: Completed — Success sheet with checkmark + summary line + conditional auto-post/reminder copy + Done/Add another buttons. Sticky values (account/frequency/auto_confirm) carry over via query string. OOB list refresh per creation. Error path unchanged (400 + red banner).
