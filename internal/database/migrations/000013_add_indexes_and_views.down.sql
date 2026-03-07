DROP MATERIALIZED VIEW IF EXISTS mv_daily_tx_counts;
DROP MATERIALIZED VIEW IF EXISTS mv_monthly_category_totals;

DROP INDEX IF EXISTS idx_transactions_account_id;
DROP INDEX IF EXISTS idx_transactions_date;
DROP INDEX IF EXISTS idx_transactions_account_date;
DROP INDEX IF EXISTS idx_transactions_type;
DROP INDEX IF EXISTS idx_transactions_category;
DROP INDEX IF EXISTS idx_transactions_person;
DROP INDEX IF EXISTS idx_transactions_building_fund;
DROP INDEX IF EXISTS idx_transactions_recurring;
DROP INDEX IF EXISTS idx_transactions_note_trgm;
DROP INDEX IF EXISTS idx_accounts_institution;
DROP INDEX IF EXISTS idx_accounts_display_order;
