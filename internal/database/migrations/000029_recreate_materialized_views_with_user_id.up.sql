-- =============================================================================
-- Migration 000029: Recreate Materialized Views with user_id
-- =============================================================================
--
-- The materialized views mv_monthly_category_totals and mv_daily_tx_counts
-- were created in migration 000013 without user_id. Now that transactions
-- have user_id (from migration 000028), we need to recreate these views
-- with user_id in the GROUP BY so per-user aggregation works correctly.
--
-- DROP + CREATE is required because ALTER MATERIALIZED VIEW doesn't support
-- adding columns. CONCURRENTLY refresh requires unique indexes, which we
-- recreate with user_id included.
-- =============================================================================

-- Drop existing views and their indexes.
DROP MATERIALIZED VIEW IF EXISTS mv_monthly_category_totals;
DROP MATERIALIZED VIEW IF EXISTS mv_daily_tx_counts;

-- Recreate with user_id in SELECT and GROUP BY.
CREATE MATERIALIZED VIEW mv_monthly_category_totals AS
SELECT
    user_id,
    date_trunc('month', date)::date AS month,
    category_id,
    type,
    currency,
    account_id,
    SUM(amount) AS total_amount,
    COUNT(*) AS tx_count
FROM transactions
WHERE category_id IS NOT NULL
GROUP BY user_id, date_trunc('month', date), category_id, type, currency, account_id;

-- Unique index for REFRESH MATERIALIZED VIEW CONCURRENTLY.
CREATE UNIQUE INDEX idx_mv_monthly_cat_uniq
    ON mv_monthly_category_totals (user_id, month, category_id, type, currency, account_id);

CREATE MATERIALIZED VIEW mv_daily_tx_counts AS
SELECT
    user_id,
    date::date AS tx_date,
    COUNT(*) AS tx_count
FROM transactions
GROUP BY user_id, date::date;

-- Unique index for concurrent refresh.
CREATE UNIQUE INDEX idx_mv_daily_tx_date ON mv_daily_tx_counts (user_id, tx_date);
