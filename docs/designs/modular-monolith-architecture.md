# Plan #23 — Modular Monolith Architecture

> **Last Updated:** 2026-03-27 (Adapted from original plan, codebase explored)
> **Baseline:** 692 tests passing
>
> **Goal:** Make the implicit module boundaries explicit and enforceable so the codebase
> stays clean as it grows — without over-engineering what already works.

---

## Execution Tracker

| Phase | Status | Start | End | Notes |
| --- | --- | --- | --- | --- |
| **Phase 1** — Fix violations + import-linter | ⏳ TODO | — | — | Fix push→dashboard, transactions→dashboard, add enforcement |
| **Phase 2** — Type boundaries | ⏳ TODO | — | — | Create AccountSummary, BudgetWithSpending, RecurringRulePending types |
| **Phase 3** — Split models | ⏳ TODO | — | — | Move 18 models from core → owning apps (high risk, defer) |
| **Phase 4** — Extract domain logic | ⏳ TODO | — | — | Move health warnings, due dates, net worth, etc. to leaf services |

**Legend:** ⏳ TODO | ⚡ IN PROGRESS | ✅ DONE | ⛔ BLOCKED

---

## What Changed Since Original Plan

The original plan (written before codebase exploration) identified **1 violation**. Exploration revealed **2 violations**:

### Original Plan Findings (1 violation)
- ✅ `push/services.py → dashboard.services` — CONFIRMED

### New Violation Discovered (Regression)
- ✅ `transactions/views.py → dashboard.services` (late import during quick-entry success) — NEW in adaptation

### Good News
- Dashboard services refactored into **modular package** (7 sub-modules)
- Dashboard data uses **typed @dataclass**
- All other cross-module imports remain clean ✓

---

## Current State — Architecture Analysis

### ✅ What Works Well
- **15 focused Django apps** (accounts, auth_app, budgets, categories, dashboard, exchange_rates, investments, jobs, people, push, recurring, reports, settings_app, transactions, virtual_accounts) + core infrastructure
- **Consistent `ServiceClass(user_id, tz)` pattern** across all services
- **`UserScopedManager.for_user()`** — per-user data isolation at query level
- **`AuthenticatedRequest`** — typed request with `user_id`, `email`, `tz`
- **Dashboard services split into package** with typed dataclasses (DueSoonCard, HealthWarning, etc.)
- **Most cross-module imports are correct** (leaf→leaf, leaf→core only)

### ❌ Structural Issues

#### 1. Two Import Violations

**Violation #1: push/services.py → dashboard.services** (line 16)
```python
from dashboard.services import DashboardService
dashboard_svc = DashboardService(self.user_id, self.tz)
data = dashboard_svc.get_dashboard()  # Queries 17 sources, only uses 3 fields
```

**Violation #2: transactions/views.py → dashboard.services** (new regression, ~line 260)
```python
# In quick-entry success handler
from dashboard.services import DashboardService
dashboard_svc = DashboardService(request.user_id, request.tz)
dashboard_data = dashboard_svc.get_dashboard()
# Renders dashboard OOB swaps
```

#### 2. Untyped Boundaries at Cross-Module Calls
- `AccountService.get_all()` → `list[dict[str, Any]]` (used by 4+ modules)
- `BudgetService.get_all_with_spending()` → `list[dict[str, Any]]` (used by push)
- `RecurringService.get_due_pending()` → `list[dict[str, Any]]` (used by push)

#### 3. No Automated Enforcement
- No `import-linter` in CI — anyone can add bad imports undetected

#### 4. All Models Still in core/models.py
- 18 models with no domain ownership
- High-risk refactor needed to split

### Dependency Graph (Current)

```
                     core (infra: models, middleware, types, managers, templatetags)
                       │
          ┌────────────┼──────────────────────────────────────────┐
          ▼            ▼                                          ▼
       auth_app    accounts    categories    investments    exchange_rates
                       │            │
                       ▼            ▼
                  transactions    budgets
                       │
          ┌────────────┼──────────┐
          ▼            ▼          ▼
      recurring    people    virtual_accounts
          │
          ▼
   ┌──────┴──────────────────┐
   ▼                         ▼
  jobs                    dashboard  ◄──── push (VIOLATION #1)
   │                         ▲
   ▼                         │ transactions (VIOLATION #2)
 (cron)                      │
                          reports

Rule: arrows point DOWN (from depender to dependency). No upward arrows allowed.
Violations: push → dashboard, transactions → dashboard
```

---

## Phases

### Phase 1 — Fix Both Violations + Add Automated Enforcement

**Goal:** Fix push → dashboard AND transactions → dashboard. Add `import-linter` so CI catches future violations.

**Duration:** 1-2 days

#### 1a. Fix `push → dashboard` Coupling

**Problem:** Push imports DashboardService and calls get_dashboard() (17 sources) just to read 3 fields:
```python
# push/services.py:16
from dashboard.services import DashboardService

dashboard_svc = DashboardService(self.user_id, self.tz)
data = dashboard_svc.get_dashboard()
cards = data.get("due_soon_cards", [])      # Only these 3 fields used
warnings = data.get("health_warnings", [])
budgets = data.get("budgets", [])
```

**Solution:** Push calls leaf services directly. Extract reusable functions from dashboard modules.

**Files to create/modify:**

```python
# core/billing.py — ADD
# (Already has billing logic; extend with due-date computation)
def compute_due_date(account: dict[str, Any], tz: ZoneInfo) -> DueDate | None:
    """Compute due date from CC account metadata and billing cycle."""
    # Extract from dashboard/credit_cards.py::_compute_due_date (rename, make public)
```

```python
# accounts/services.py — ADD PUBLIC METHOD
def get_health_warnings(user_id: str, accounts: list[dict], tz: ZoneInfo) -> list[HealthWarning]:
    """Compute health warnings from accounts."""
    # Extract from dashboard/widgets.py::load_health_warnings
    # Return typed HealthWarning dataclass (from dashboard.services)
```

```python
# push/services.py — REWRITE (lines 16, 45-110)
# BEFORE
from dashboard.services import DashboardService
...
dashboard_svc = DashboardService(self.user_id, self.tz)
data = dashboard_svc.get_dashboard()

# AFTER
from accounts.services import AccountService
from budgets.services import BudgetService
from core.billing import compute_due_date
from dashboard.services import HealthWarning, DueSoonCard  # import types only

...
acct_svc = AccountService(self.user_id, self.tz)
budget_svc = BudgetService(self.user_id, self.tz)

# Get all accounts to find credit cards
all_accounts = acct_svc.get_all()
credit_cards = [a for a in all_accounts if a["account_type"] in ["credit_card", "credit_limit"]]

# CC due dates — compute directly
due_soon: list[DueSoonCard] = []
for card in credit_cards:
    due = compute_due_date(card, self.tz)
    if due and due.days_until_due <= 3:
        due_soon.append(due)

# Health warnings — call leaf function
warnings = get_health_warnings(self.user_id, credit_cards, self.tz)

# Budgets — use BudgetService
budgets = budget_svc.get_all_with_spending()
```

**Result:** push depends on accounts + budgets (leaves) + core (infra), not dashboard (aggregator).

#### 1b. Fix `transactions → dashboard` Coupling

**Problem:** transactions/views.py imports DashboardService to refresh dashboard after transaction created:
```python
# In quick_entry_success handler (~line 260)
from dashboard.services import DashboardService

dashboard_svc = DashboardService(request.user_id, request.tz)
dashboard_data = dashboard_svc.get_dashboard()
# Renders dashboard/_net_worth.html, dashboard/_accounts.html
```

**Solution:** Call AccountService directly, build minimal data for OOB swaps.

**Files to create/modify:**

```python
# dashboard/services/accounts.py — EXTRACT PUBLIC FUNCTION
def compute_net_worth_for_accounts(accounts: list[dict[str, Any]]) -> dict[str, float]:
    """Compute net worth summary from accounts list.

    Returns: {
        "net_worth_egp": float,
        "net_worth_usd": float,
        "egp_total": float,
        "usd_total": float,
    }
    """
    # Extract from DashboardService._compute_net_worth
    # Make pure function that doesn't depend on self.tz
```

```python
# transactions/views.py — REWRITE (lines ~250-280)
# BEFORE
from dashboard.services import DashboardService
...
dashboard_svc = DashboardService(request.user_id, request.tz)
dashboard_data = dashboard_svc.get_dashboard()
ctx = {"data": dashboard_data}

# AFTER
from accounts.services import AccountService
from dashboard.services import compute_net_worth_for_accounts

acct_svc = AccountService(request.user_id, request.tz)
all_accounts = acct_svc.get_all()

# Compute net worth
nw_summary = compute_net_worth_for_accounts(all_accounts)

# Prepare minimal dashboard context for OOB renders
minimal_dashboard = {
    "net_worth": nw_summary["net_worth_egp"],
    "net_worth_usd": nw_summary["net_worth_usd"],
    "institutions": [...]  # build from all_accounts
    # ... only what's needed for the 2 partials
}
ctx = {"data": minimal_dashboard}
```

#### 1c. Add `import-linter` to Enforce Boundaries

```bash
uv add --group dev import-linter
```

```toml
# backend/pyproject.toml
[tool.importlinter]
root_packages = [
    "accounts", "auth_app", "budgets", "categories", "core",
    "dashboard", "exchange_rates", "investments", "jobs",
    "people", "push", "recurring", "reports",
    "settings_app", "transactions", "virtual_accounts",
]

[[tool.importlinter.contracts]]
name = "Leaf modules must not import from aggregators"
type = "forbidden"
source_modules = [
    "accounts", "auth_app", "budgets", "categories",
    "exchange_rates", "investments", "people",
    "recurring", "transactions", "virtual_accounts",
]
forbidden_modules = [
    "dashboard",
    "reports",
    "push",
    "jobs",
    "settings_app",
]

[[tool.importlinter.contracts]]
name = "Aggregators must not import from each other"
type = "independence"
modules = [
    "dashboard",
    "reports",
    "push",
    "jobs",
    "settings_app",
]
```

```makefile
# Makefile
lint-imports:
	uv run lint-imports

lint: lint-ruff lint-mypy lint-imports
```

**Deliverable:**
- ✅ Both violations fixed (push, transactions use leaf services only)
- ✅ `make lint` fails if new violations added
- ✅ Dashboard exports reusable functions

---

### Phase 2 — Typed Contracts at Cross-Module Boundaries

**Goal:** Replace `dict[str, Any]` with typed dataclasses where data crosses module boundaries.

**Duration:** 1-2 days

**Scope:** Only the 4 actual cross-module calls (not internal dicts):

| Service method | Called by | Return type today | Target type |
| --- | --- | --- | --- |
| `AccountService.get_all()` | recurring, virtual_accounts, people, transactions views; push (Phase 1) | `list[dict[str, Any]]` | `list[AccountSummary]` |
| `AccountService.get_for_dropdown()` | (cross-module in forms) | `list[dict[str, Any]]` | `list[AccountDropdownItem]` |
| `BudgetService.get_all_with_spending()` | push (after Phase 1) | `list[dict[str, Any]]` | `list[BudgetWithSpending]` |
| `RecurringService.get_due_pending()` | push | `list[dict[str, Any]]` | `list[RecurringRulePending]` |

**Implementation:**

```python
# accounts/types.py — CREATE
from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class AccountSummary:
    """Minimal account data for cross-module consumers."""
    id: str
    name: str
    institution_name: str
    balance: Decimal
    currency: str
    account_type: str
    is_credit: bool
    is_dormant: bool
    credit_limit: Decimal | None = None
    billing_cycle: dict[str, Any] | None = None  # for CC features

@dataclass(frozen=True)
class AccountDropdownItem:
    """Account for form dropdowns."""
    id: str
    name: str
    currency: str
    balance: Decimal | None = None  # optional if include_balance=False
```

```python
# budgets/types.py — CREATE
from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class BudgetWithSpending:
    """Budget with current spending summary."""
    id: str
    category_id: str
    category_name: str
    category_icon: str
    monthly_limit: Decimal
    spent: Decimal
    percentage: float  # spent / limit * 100
    currency: str
```

```python
# recurring/types.py — CREATE
from dataclasses import dataclass
from datetime import date

@dataclass(frozen=True)
class RecurringRulePending:
    """Recurring rule awaiting confirmation."""
    id: str
    frequency: str  # "daily", "weekly", "monthly", "yearly"
    next_due_date: date
    last_executed: date | None = None
    notes: str = ""
```

**Steps:**
1. Create types.py files in accounts, budgets, recurring
2. Update AccountService, BudgetService, RecurringService to return typed dataclasses
3. Update all cross-module callers (push, transactions, views) to expect typed returns
4. Run mypy — type-check all boundaries

**Deliverable:** Cross-module data flows are type-checked by mypy.

---

### Phase 3 — Split `core/models.py` into Module-Owned Models

**Goal:** Each module owns its models. `core/` becomes pure infrastructure.

**Risk:** HIGH | **Effort:** 2-3 weeks | **Benefit:** Medium

**Prerequisites:** Phases 1-2 must be stable first. Do during feature freeze.

**Correct migration technique:** Use `SeparateDatabaseAndState` for each model migration.

**Migration order (batches, leaves first):**
1. ExchangeRateLog → exchange_rates
2. Category → categories
3. Institution → accounts
4. Investment → investments
5. Budget → budgets
6. Person → people
7. VirtualAccount → virtual_accounts
8. RecurringRule → recurring
9. Account → accounts
10. DailySnapshot, AccountSnapshot → jobs
11. Transaction, VirtualAccountAllocation → transactions
12. User, Session, AuthToken → auth_app

**Process:**
- Ship each batch as separate PR
- Run `make test` + `make migrate` after each
- Keep transitional re-exports in `core/models.py` until all imports updated
- Only remove shim after migration complete

**Deliverable:** Each app owns its models. `core/models.py` is empty (or contains only infrastructure).

---

## NEW: Phase 4 — Extract Domain Logic (Reusable Functions)

**Goal:** Move domain-specific logic from dashboard submodules into owning services.

**Duration:** 2-3 days | **Risk:** Low | **Benefit:** High

**Rationale:** The violations in Phase 1 exposed that dashboard has business logic that belongs in leaf services. Extract this logic so dashboard uses services (not the reverse).

**Items:**

| Logic | Current Location | Target Location | Reason |
| --- | --- | --- | --- |
| Health warnings computation | dashboard/widgets.py::load_health_warnings() | accounts/services.py::get_health_warnings() | Account health is account logic |
| Due date computation | dashboard/credit_cards.py::_compute_due_date() | core/billing.py::compute_due_date() | CC math belongs in shared billing module |
| Net worth computation | dashboard/services/accounts.py::compute_net_worth() | core/accounting.py::compute_net_worth_for_accounts() | Pure accounting logic, used by push + transactions |
| Budget spending calculation | dashboard/spending.py::load_budget_spending() | budgets/services.py::compute_budget_spending() | Budget math belongs in budgets module |
| Spending velocity | dashboard/spending.py::compute_spending_comparison() | reports/services.py::compute_spending_velocity() | Velocity is a reporting concept |
| Transaction recency | dashboard/activity.py::load_recent_transactions() | transactions/services.py::get_recent(limit=10) | Recent txns is transaction logic |

**Implementation pattern:**

```python
# Step 1: Define the function in the leaf service with business logic
# accounts/services.py
def get_health_warnings(user_id: str, accounts: list[dict], tz: ZoneInfo) -> list[HealthWarning]:
    """Compute health warnings from account conditions."""
    warnings = []
    for account in accounts:
        # Health logic: no activity, low balance, CC utilization, etc.
        ...
    return warnings

# Step 2: Dashboard imports and uses the leaf function
# dashboard/services/widgets.py
from accounts.services import get_health_warnings

warnings = get_health_warnings(user_id, all_accounts, tz)

# Step 3: Tests live with the service, not dashboard
# accounts/tests/test_services.py
def test_get_health_warnings():
    ...
```

**Deliverable:**
- ✅ Dashboard becomes a pure aggregator (calls leaf services only)
- ✅ Business logic testable at the service layer
- ✅ Leaf modules own their domain logic

---

## Summary

| Phase | What Changes | Risk | Effort | Value | Status |
| --- | --- | --- | --- | --- | --- |
| 1 — Fix violations + enforce | Fix 2 bad imports, add import-linter, extract 3 functions | Low | 1-2 days | High | ⏳ TODO |
| 2 — Typed boundaries | Dataclasses for 4 cross-module returns | Low | 1-2 days | Medium | ⏳ TODO |
| 3 — Split models | Models move to owning apps | High | 2-3 weeks | Medium | ⏳ TODO |
| 4 — Extract domain logic | Move 6+ functions from dashboard to leaf services | Medium | 2-3 days | High | ⏳ TODO |

**Recommendation:** Start with Phase 1 (highest value, lowest risk). Can run Phases 2 & 4 in parallel after Phase 1 stabilizes.

---

## Files That Change (Phase 1)

```
backend/
  # Core changes
  push/services.py                           EDIT — remove dashboard import, use leaf services
  transactions/views.py                      EDIT — remove dashboard import, use accounts service
  accounts/services.py                       EDIT — add public get_health_warnings() method
  core/billing.py                            EDIT — add public compute_due_date() function
  dashboard/services/accounts.py             EDIT — extract compute_net_worth_for_accounts()

  # Config
  pyproject.toml                             EDIT — add import-linter config
  Makefile                                   EDIT — add lint-imports target
```

---

## Decisions

| Decision | Rationale |
| --- | --- |
| Fix both violations in Phase 1 | Dashboard imports were a regression not in original plan; fixing together maintains coherence |
| Extract functions to leaf services, not core | Leaf services own their domain (accounts health, credit card math, etc.) |
| core/billing.py for CC math | Shared across accounts (health checks) + dashboard (due dates) + push (notifications) |
| Type only cross-module calls in Phase 2 | Internal dicts stay untyped; boundary types catch bugs faster |
| Phase 4 for logic extraction | Separates architectural cleanup (Phases 1-3) from domain consolidation (Phase 4) |
| Defer Phase 3 until Phases 1-2 stable | Model splitting is high-risk; do after proving the import + type structure works |

---

## Implementation Checklist (Phase 1)

- [ ] Extract `compute_due_date()` from dashboard/credit_cards.py → core/billing.py
- [ ] Extract `get_health_warnings()` from dashboard/widgets.py → accounts/services.py
- [ ] Extract `compute_net_worth_for_accounts()` from dashboard/services/accounts.py
- [ ] Rewrite push/services.py to use leaf services instead of DashboardService
- [ ] Rewrite transactions/views.py to use AccountService instead of DashboardService
- [ ] Add import-linter to pyproject.toml
- [ ] Add lint-imports to Makefile
- [ ] Run `make test` — all tests pass
- [ ] Run `make lint` — no import violations
- [ ] Create PR with Phase 1 changes
