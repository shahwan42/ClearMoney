-- =============================================================================
-- Migration 000014: Daily Balance Snapshots
-- =============================================================================
--
-- TIME-SERIES / SNAPSHOT PATTERN
-- --------------------------------
-- This migration creates two tables that capture daily "snapshots" of financial state.
-- Instead of computing historical balances by replaying all transactions from the
-- beginning of time (expensive), we take a daily photo of the current state.
--
-- This is a common pattern in analytics and dashboards:
--   - daily_snapshots:  one row per day with the aggregate net worth + daily totals
--   - account_snapshots: one row per (day, account) pair with that account's EOD balance
--
-- Together, they power:
--   - Net worth sparkline on the dashboard (last 30 days of daily_snapshots)
--   - Per-account balance sparklines (last 30 days of account_snapshots)
--   - Month-over-month spending comparisons
--   - Trend indicators (up/down arrows)
--
-- Laravel equivalent:
--   // You'd run a scheduled command (app:take-snapshot) via Laravel's scheduler:
--   // $schedule->command('app:take-snapshot')->daily();
--   // The command creates a DailySnapshot Eloquent model.
--
-- Django equivalent:
--   // A Celery beat task or management command run by cron:
--   // @periodic_task(run_every=crontab(hour=23, minute=59))
--   // def take_daily_snapshot(): DailySnapshot.objects.create(...)
-- =============================================================================

-- Daily balance snapshots for historical tracking.
-- Captures net worth and per-account balances daily for sparklines and trend indicators.

-- daily_snapshots: one row per day with aggregate net worth + spending/income totals.
--
-- UNIQUE on date
-- ----------------
-- The date column has a UNIQUE constraint, ensuring only one snapshot per day.
-- This enables UPSERT (INSERT ... ON CONFLICT DO UPDATE):
--   INSERT INTO daily_snapshots (date, net_worth_egp, ...)
--   VALUES ('2024-03-15', 50000, ...)
--   ON CONFLICT (date) DO UPDATE SET net_worth_egp = EXCLUDED.net_worth_egp;
--
-- UPSERT is PostgreSQL's "create or update" — like Laravel's updateOrCreate():
--   DailySnapshot::updateOrCreate(['date' => $date], ['net_worth_egp' => $value]);
-- Or Django's update_or_create():
--   DailySnapshot.objects.update_or_create(date=date, defaults={'net_worth_egp': value})
--
-- Docs: https://www.postgresql.org/docs/current/sql-insert.html#SQL-ON-CONFLICT
--
-- net_worth_egp: total net worth converted to EGP (for single-currency display)
-- net_worth_raw: sum of all balances without currency conversion
-- exchange_rate: the USD/EGP rate used for conversion on that day
-- daily_spending / daily_income: total expenses/income for that specific day
CREATE TABLE IF NOT EXISTS daily_snapshots (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date            DATE NOT NULL UNIQUE,
    net_worth_egp   NUMERIC(15,2) NOT NULL DEFAULT 0,
    net_worth_raw   NUMERIC(15,2) NOT NULL DEFAULT 0,
    exchange_rate   NUMERIC(10,4) NOT NULL DEFAULT 0,
    daily_spending  NUMERIC(15,2) NOT NULL DEFAULT 0,
    daily_income    NUMERIC(15,2) NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- account_snapshots: one row per (date, account) pair with the account's balance at EOD.
--
-- COMPOSITE UNIQUE CONSTRAINT: UNIQUE(date, account_id)
-- -------------------------------------------------------
-- This ensures only one snapshot per account per day.
-- Unlike the single-column UNIQUE on daily_snapshots.date, this is a multi-column
-- unique constraint — the COMBINATION of (date, account_id) must be unique.
--
-- Valid:   (2024-03-15, account-A) and (2024-03-15, account-B) — same date, different accounts
-- Valid:   (2024-03-15, account-A) and (2024-03-16, account-A) — same account, different dates
-- Invalid: (2024-03-15, account-A) and (2024-03-15, account-A) — duplicate, rejected
--
-- Also enables UPSERT with ON CONFLICT (date, account_id) DO UPDATE.
--
-- Laravel: $table->unique(['date', 'account_id']);
-- Django:  class Meta: unique_together = [['date', 'account_id']]
--          // Or: constraints = [models.UniqueConstraint(fields=['date','account_id'], name='...')]
CREATE TABLE IF NOT EXISTS account_snapshots (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date        DATE NOT NULL,
    account_id  UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    balance     NUMERIC(15,2) NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(date, account_id)
);

-- DESC indexes for efficient range queries
-- ------------------------------------------
-- date DESC means the index is sorted with the newest dates first.
-- This is optimal for queries like: "give me the last 30 days of snapshots"
--   SELECT * FROM daily_snapshots ORDER BY date DESC LIMIT 30;
-- The database reads the first 30 entries from the index without scanning further.
--
-- The composite index (date DESC, account_id) on account_snapshots supports:
--   SELECT * FROM account_snapshots WHERE account_id = ? ORDER BY date DESC LIMIT 30;
CREATE INDEX IF NOT EXISTS idx_daily_snapshots_date ON daily_snapshots (date DESC);
CREATE INDEX IF NOT EXISTS idx_account_snapshots_date ON account_snapshots (date DESC, account_id);
