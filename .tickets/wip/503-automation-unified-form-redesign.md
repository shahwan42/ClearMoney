---
id: "503"
title: "Automation unified form redesign"
type: improvement
priority: high
status: wip
created: 2026-04-27
updated: 2026-04-27
---

## Description

Redesign the automation (recurring rules) form to be almost identical to the quick entry unified form. Users currently face two different form paradigms — quick entry is polished with comboboxes, dynamic type switching, and a "More options" pattern, while automation uses a plain form. Unify the experience.

## Acceptance Criteria

- [ ] Automation form moved to a bottom sheet (same pattern as quick entry on dashboard)
- [ ] Type radio: expense / income / transfer / exchange (adds exchange support)
- [ ] Account: combobox with type-based filtering (mirrors quick entry)
- [ ] Category: combobox with Expenses/Income optgroups (hidden for transfer/exchange)
- [ ] Destination account: select (transfer/exchange), mirrors quick entry
- [ ] Scheduling section always visible: frequency, next due date, auto-confirm toggle
- [ ] More options section: fee, pot (virtual account), tags
- [ ] Pending toggle removed (superseded by auto-confirm)
- [ ] Edit existing rule: tap rule → bottom sheet opens pre-filled
- [ ] Exchange type: rate optional at rule creation, required at confirmation
- [ ] Confirm form updated: looks like quick entry pre-filled, all fields editable including tags/pot/fee, exchange rate required
- [ ] template_transaction JSONB stores tags, pot (va_id), fee, exchange rate
- [ ] Existing rules without new fields work without migration (JSONB optional keys)
- [ ] All tests pass, new service tests for exchange rule creation + confirmation

## Progress Notes

- 2026-04-27: Started — Grilled user on design, agreed on full spec above
- 2026-04-27: Phase 1 complete — service layer updated: exchange branch in build_template_transaction, tags/va_id/fee for expense/income, exchange+auto_confirm validation, new update() method, _execute_rule handles exchange + tags/va_id/fee + apply_post_create_logic. 1747 tests passing.
- 2026-04-27: Phase 2+3 complete — _form.html rewritten (4-tab type radio, account/category comboboxes, scheduling section, More options, exchange support, edit mode), recurring.html moved to bottom sheets, _rule_list.html rows open edit sheet, views updated with _get_form_context() + edit/update endpoints. 1754 tests passing.
- 2026-04-27: Phase 4 complete — _confirm_form.html rewritten: account combobox, exchange rate field, tags/fee/pot fields, dual-context hx_target+sheet_name. 1754 tests passing, lint clean.
- 2026-04-27: E2E updated — test_recurring.py fully rewritten for bottom sheet UI (8/8 pass), test_form_validation.py updated for new IDs (3/3 pass), test_virtual_accounts.py recurring steps updated + @pytest.mark.timeout(90) for heavy cross-feature test. All 278 E2E tests pass (1 flaky loading skeleton test is pre-existing race condition, passes on retry).
