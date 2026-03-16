-- Restore original materialized views without user_id.
DROP MATERIALIZED VIEW IF EXISTS mv_monthly_category_totals;
DROP MATERIALIZED VIEW IF EXISTS mv_daily_tx_counts;

CREATE MATERIALIZED VIEW mv_monthly_category_totals AS
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

CREATE UNIQUE INDEX idx_mv_monthly_cat_uniq
    ON mv_monthly_category_totals (month, category_id, type, currency, account_id);

CREATE MATERIALIZED VIEW mv_daily_tx_counts AS
SELECT
    date::date AS tx_date,
    COUNT(*) AS tx_count
FROM transactions
GROUP BY date::date;

CREATE UNIQUE INDEX idx_mv_daily_tx_date ON mv_daily_tx_counts (tx_date);
