-- Restore original unique constraints.
ALTER TABLE daily_snapshots DROP CONSTRAINT IF EXISTS daily_snapshots_user_date_key;
ALTER TABLE daily_snapshots ADD CONSTRAINT daily_snapshots_date_key UNIQUE(date);

ALTER TABLE budgets DROP CONSTRAINT IF EXISTS budgets_user_category_currency_key;
ALTER TABLE budgets ADD CONSTRAINT budgets_category_id_currency_key UNIQUE(category_id, currency);

-- Drop composite indexes.
DROP INDEX IF EXISTS idx_transactions_user_account;
DROP INDEX IF EXISTS idx_transactions_user_date;

-- Drop user_id indexes.
DROP INDEX IF EXISTS idx_institutions_user;
DROP INDEX IF EXISTS idx_accounts_user;
DROP INDEX IF EXISTS idx_categories_user;
DROP INDEX IF EXISTS idx_persons_user;
DROP INDEX IF EXISTS idx_transactions_user;
DROP INDEX IF EXISTS idx_recurring_rules_user;
DROP INDEX IF EXISTS idx_investments_user;
DROP INDEX IF EXISTS idx_installment_plans_user;
DROP INDEX IF EXISTS idx_virtual_accounts_user;
DROP INDEX IF EXISTS idx_budgets_user;
DROP INDEX IF EXISTS idx_daily_snapshots_user;
DROP INDEX IF EXISTS idx_account_snapshots_user;

-- Drop user_id columns from all tables.
ALTER TABLE institutions DROP COLUMN IF EXISTS user_id;
ALTER TABLE accounts DROP COLUMN IF EXISTS user_id;
ALTER TABLE categories DROP COLUMN IF EXISTS user_id;
ALTER TABLE persons DROP COLUMN IF EXISTS user_id;
ALTER TABLE transactions DROP COLUMN IF EXISTS user_id;
ALTER TABLE recurring_rules DROP COLUMN IF EXISTS user_id;
ALTER TABLE investments DROP COLUMN IF EXISTS user_id;
ALTER TABLE installment_plans DROP COLUMN IF EXISTS user_id;
ALTER TABLE virtual_accounts DROP COLUMN IF EXISTS user_id;
ALTER TABLE budgets DROP COLUMN IF EXISTS user_id;
ALTER TABLE daily_snapshots DROP COLUMN IF EXISTS user_id;
ALTER TABLE account_snapshots DROP COLUMN IF EXISTS user_id;
