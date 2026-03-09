-- Daily balance snapshots for historical tracking.
-- Captures net worth and per-account balances daily for sparklines and trend indicators.

-- daily_snapshots: one row per day with aggregate net worth + spending/income totals.
-- UNIQUE on date ensures idempotent UPSERT (INSERT ... ON CONFLICT DO UPDATE).
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
-- UNIQUE on (date, account_id) enables UPSERT and efficient range queries.
CREATE TABLE IF NOT EXISTS account_snapshots (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date        DATE NOT NULL,
    account_id  UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    balance     NUMERIC(15,2) NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(date, account_id)
);

-- Indexes for efficient range queries (e.g., "last 30 days of net worth")
CREATE INDEX IF NOT EXISTS idx_daily_snapshots_date ON daily_snapshots (date DESC);
CREATE INDEX IF NOT EXISTS idx_account_snapshots_date ON account_snapshots (date DESC, account_id);
