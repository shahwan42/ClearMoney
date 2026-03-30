# ClearMoney Tickets

Last updated: 2026-03-30

## In Progress

(none)

## Pending

| ID | Title | Type | Priority | Updated |
| --- | --- | --- | --- | --- |
| [022](pending/022-i18n-infrastructure.md) | i18n infrastructure — settings, middleware, locale dirs | feature | high | 2026-03-30 |
| [023](pending/023-user-language-preference.md) | User language preference — model + middleware + migration | feature | high | 2026-03-30 |
| [024](pending/024-base-html-rtl-config.md) | base.html — dynamic lang/dir + RTL Tailwind config | feature | high | 2026-03-30 |
| [025](pending/025-rtl-shared-components.md) | RTL — shared components + base layout | feature | medium | 2026-03-30 |
| [026](pending/026-rtl-dashboard-accounts.md) | RTL — dashboard + accounts templates | feature | medium | 2026-03-30 |
| [027](pending/027-rtl-remaining-templates.md) | RTL — transactions + remaining app templates | feature | medium | 2026-03-30 |
| [028](pending/028-i18n-auth-templates.md) | i18n strings — auth templates | feature | medium | 2026-03-30 |
| [029](pending/029-i18n-shared-components.md) | i18n strings — shared components + error pages | feature | medium | 2026-03-30 |
| [030](pending/030-i18n-dashboard-templates.md) | i18n strings — dashboard templates | feature | medium | 2026-03-30 |
| [031](pending/031-i18n-transactions-templates.md) | i18n strings — transactions templates | feature | medium | 2026-03-30 |
| [032](pending/032-i18n-accounts-templates.md) | i18n strings — accounts templates | feature | medium | 2026-03-30 |
| [033](pending/033-i18n-budgets-people-virtual.md) | i18n strings — budgets + people + virtual accounts | feature | medium | 2026-03-30 |
| [034](pending/034-i18n-remaining-templates.md) | i18n strings — recurring + investments + reports + settings + exchange rates | feature | medium | 2026-03-30 |
| [035](pending/035-i18n-template-tag-labels.md) | i18n — template tags (account type + transaction type labels) | feature | medium | 2026-03-30 |
| [036](pending/036-i18n-validation-errors.md) | i18n — auth + validation error messages | feature | medium | 2026-03-30 |
| [037](pending/037-i18n-push-notifications-email.md) | i18n — push notifications + email template | feature | medium | 2026-03-30 |
| [038](pending/038-category-name-jsonb.md) | Category name → JSONB migration | feature | high | 2026-03-30 |
| [039](pending/039-bilingual-category-seeding.md) | Bilingual category seeding | feature | medium | 2026-03-30 |
| [040](pending/040-settings-language-toggle.md) | Settings page — language toggle | feature | medium | 2026-03-30 |
| [041](pending/041-extract-month-range-utilities.md) | Extract shared month-range utilities to core/dates.py | refactor | medium | 2026-03-30 |
| [042](pending/042-extract-status-threshold-computation.md) | Extract status/threshold computation to core/status.py | refactor | low | 2026-03-30 |
| [043](pending/043-extract-serialization-helpers.md) | Extract serialization helpers to core/serializers.py | refactor | medium | 2026-03-30 |
| [044](pending/044-decompose-get-statement-data.md) | Decompose get_statement_data (133 lines) | refactor | medium | 2026-03-30 |
| [045](pending/045-decompose-get-net-worth-breakdown.md) | Decompose get_net_worth_breakdown (100 lines) | refactor | medium | 2026-03-30 |
| [046](pending/046-decompose-get-debt-summary.md) | Decompose get_debt_summary (100+ lines) | refactor | medium | 2026-03-30 |
| [047](pending/047-decompose-get-dashboard.md) | Decompose get_dashboard (125 lines) | refactor | medium | 2026-03-30 |
| [048](pending/048-decompose-rule-to-view.md) | Decompose rule_to_view (84 lines) | refactor | low | 2026-03-30 |
| [049](pending/049-standardize-htmx-error-responses.md) | Standardize HTMX error response helpers | refactor | medium | 2026-03-30 |
| [050](pending/050-move-template-display-logic-to-services.md) | Move template display logic to services | refactor | low | 2026-03-30 |
| [051](pending/051-extract-service-factory-decorator.md) | Extract service factory decorator from views | refactor | low | 2026-03-30 |
| [052](pending/052-break-down-large-views.md) | Break down large views (account_add, recurring_add) | refactor | medium | 2026-03-30 |
| [053](pending/053-standardize-service-error-handling.md) | Standardize error handling conventions across services | refactor | low | 2026-03-30 |

## Done

| ID | Title | Type | Priority | Updated |
| --- | --- | --- | --- | --- |
| [020](done/020-recurring-rules-money-movement-fee.md) | Recurring rules money movement + fee | feature | medium | 2026-03-30 |
| [021](done/021-net-worth-debt-calculation.md) | Net worth debt calculation | feature | medium | 2026-03-29 |
| [019](done/019-budget-detail-contributing-transactions.md) | Show contributing transactions on budget click | feature | medium | 2026-03-28 |
| [017](done/017-allow-updating-budgets.md) | Allow updating budgets | feature | medium | 2026-03-28 |
| [018](done/018-enter-key-submits-parent-form-in-category-combobox.md) | Enter key in new-category form submits parent form | bug | high | 2026-03-28 |
| [016](done/016-update-fee-unnecessary-float-roundtrip.md) | update_fee_for_transaction unnecessary Decimal→float→Decimal round-trip | improvement | low | 2026-03-28 |
| [015](done/015-quick-entry-date-missing-max-constraint.md) | Quick-entry date picker allows future dates | bug | low | 2026-03-28 |
| [014](done/014-edit-form-note-missing-maxlength.md) | Edit form note input missing maxlength | bug | low | 2026-03-28 |
| [013](done/013-quick-entry-note-missing-maxlength.md) | Quick-entry note input missing maxlength | bug | low | 2026-03-28 |
| [012](done/012-add-fee-to-transactions.md) | Add optional fee to expense/income transactions | feature | medium | 2026-03-28 |
| [011](done/011-merge-transfer-exchange-move-money.md) | Merge transfer & exchange into Move Money tab | feature | medium | 2026-03-28 |
| [010](done/010-simplify-account-deletion-ux.md) | Simplify account & institution deletion UX | improvement | medium | 2026-03-28 |
| [009](done/009-phase-4-extract-domain-logic.md) | Phase 4: Extract domain logic from dashboard to leaf services | improvement | medium | 2026-03-28 |
| [008](done/008-e2e-test-isolation-flakiness.md) | E2E test isolation flakiness — fix database connection handling under load | chore | medium | 2026-03-28 |
| [007](done/007-phase-3-cleanup-update-import-sites.md) | Phase 3 Cleanup — update import sites and remove shims | chore | medium | 2026-03-28 |
| [006](done/006-phase-3-split-core-models.md) | Phase 3 — split core/models.py into module-owned models | refactor | high | 2026-03-27 |
| [005](done/005-phase-2-typed-module-boundaries.md) | Phase 2 — Typed contracts at module boundaries | improvement | medium | 2026-03-27 |
| [004](done/004-phase-1-fix-import-violations.md) | Phase 1: Fix dashboard import violations + enforce boundaries | improvement | high | 2026-03-27 |
| [003](done/003-qa-audit-fixes-complete.md) | QA audit fixes complete | chore | high | 2026-03-27 |
| [001](done/001-setup-ai-ticketing-system.md) | Setup AI-first ticketing system | chore | medium | 2026-03-27 |

## Rejected

| ID | Title | Type | Priority | Updated |
| --- | --- | --- | --- | --- |
| [002](rejected/002-unified-transaction-form.md) | Unified transaction form | feature | high | 2026-03-27 |
