id: "153"
title: "Cleanup, compatibility removal, docs, and guardrails"
type: chore
priority: medium
status: done
created: 2026-04-22
updated: 2026-04-24
description: |
  Remove transitional dual-currency compatibility paths, update docs and seed
  data, and add product guardrails once the generalized multi-currency rollout is
  complete.
details: |
  - Remove legacy dual-currency fields and compatibility code after all runtime
    consumers are migrated
  - Update docs, seed data, factories, admin configuration, and QA scenarios for
    third-currency coverage
  - Prevent users from deactivating currencies still referenced by live data
  - Ensure any remaining USD/EGP exchange-rate behavior is explicitly isolated as
    legacy FX functionality rather than part of generalized summary calculations
acceptance_criteria:
  - [x] No production path depends on dual-currency-only domain structures
  - [x] Currency deactivation guardrails prevent inconsistent user state
  - [x] Docs and seed/factory data reflect generalized multi-currency behavior
  - [x] Test coverage includes non-USD/EGP cases in all major domains
critical_files:
  - backend/tests/factories.py
  - backend/jobs/management/commands/qa_seed.py
  - backend/auth_app/models.py
  - backend/settings_app/views.py
  - backend/people/models.py
  - backend/people/services.py
  - backend/jobs/services/snapshot.py
  - docs/
research_findings: |
  - DailySnapshot is legacy; HistoricalSnapshot is the new standard.
  - Person model has legacy net_balance, net_balance_egp, net_balance_usd.
  - Dashboard services (activity.py, accounts.py) still fall back to legacy Person fields.
  - ExchangeRateLog is USD/EGP specific and used in legacy snapshot logic.
execution_plan:
  - step: 1
    description: Remove DailySnapshot and legacy snapshot logic
    tasks:
      - Remove DailySnapshot from auth_app/models.py and admin.py
      - Cleanup jobs/services/snapshot.py (remove _upsert_daily, _convert_totals_to_egp)
      - Update jobs/tests/ to remove DailySnapshot checks
  - step: 2
    description: Remove legacy Person fields
    tasks:
      - Remove net_balance* fields from people/models.py
      - Cleanup people/services.py (remove legacy updates and normalization)
      - Update dashboard/services/ (activity.py, accounts.py) to use generalized balances only
      - Update people/admin.py and tests
  - step: 3
    description: Implement currency deactivation guardrails
    tasks:
      - Implement is_currency_in_use(user_id, currency_code) helper in auth_app/currency.py
      - Update set_user_active_currencies to prevent deactivating in-use currencies
  - step: 4
    description: Update Seed Data and Factories
    tasks:
      - Add EUR account/budget to qa_seed.py
      - Cleanup factories.py (remove legacy snapshots and fields)
  - step: 5
    description: Documentation and Migrations
    tasks:
      - Create migration to drop legacy columns and tables
      - Update docs/ to reflect generalized multi-currency state
progress_notes:
  - 2026-04-22: Created as the final cleanup and hardening ticket
  - 2026-04-24: Commencing implementation. Identified all legacy fields and logic.
  - 2026-04-24: Removed DailySnapshot model and legacy snapshot logic.
  - 2026-04-24: Removed legacy Person fields and updated dashboard services.
  - 2026-04-24: Implemented currency deactivation guardrails and added tests.
  - 2026-04-24: Updated qa_seed.py with EUR data and cleaned up factories.py.
  - 2026-04-24: Generated migrations and verified all unit/E2E tests pass.
