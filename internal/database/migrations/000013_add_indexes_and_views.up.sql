-- Performance indexes for common query patterns.

-- Enable trigram extension for ILIKE search optimization.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Transactions: frequently filtered/sorted by account, date, type
CREATE INDEX IF NOT EXISTS idx_transactions_account_id ON transactions (account_id);
CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions (date DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_account_date ON transactions (account_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions (type);
CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions (category_id) WHERE category_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_transactions_person ON transactions (person_id) WHERE person_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_transactions_building_fund ON transactions (is_building_fund) WHERE is_building_fund = true;
CREATE INDEX IF NOT EXISTS idx_transactions_recurring ON transactions (recurring_rule_id) WHERE recurring_rule_id IS NOT NULL;

-- Note search (for ILIKE queries)
CREATE INDEX IF NOT EXISTS idx_transactions_note_trgm ON transactions USING gin (note gin_trgm_ops);

-- Accounts: frequently joined with institutions
CREATE INDEX IF NOT EXISTS idx_accounts_institution ON accounts (institution_id);
CREATE INDEX IF NOT EXISTS idx_accounts_display_order ON accounts (display_order);

-- Materialized view: monthly spending summary by category.
-- Avoids repeated aggregation on every reports page load.
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_monthly_category_totals AS
SELECT
    date_trunc('month', date)::date AS month,
    category_id,
    type,
    currency,
    account_id,
    SUM(amount) AS total_amount,
    COUNT(*) AS tx_count
FROM transactions
WHERE category_id IS NOT NULL
GROUP BY date_trunc('month', date), category_id, type, currency, account_id;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_monthly_cat_uniq
    ON mv_monthly_category_totals (month, category_id, type, currency, account_id);

-- Materialized view: daily transaction counts (for streak computation).
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_daily_tx_counts AS
SELECT
    date::date AS tx_date,
    COUNT(*) AS tx_count
FROM transactions
GROUP BY date::date;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_daily_tx_date ON mv_daily_tx_counts (tx_date);
