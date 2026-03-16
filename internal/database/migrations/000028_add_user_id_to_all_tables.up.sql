-- =============================================================================
-- Migration 000028: Add user_id to All Data Tables
-- =============================================================================
--
-- Adds a user_id foreign key to every user-scoped table, backfills existing
-- production data to the migrated user (from migration 000027), then makes
-- the column NOT NULL.
--
-- Tables modified (12):
--   institutions, accounts, categories, persons, transactions,
--   recurring_rules, investments, installment_plans, virtual_accounts,
--   budgets, daily_snapshots, account_snapshots
--
-- Tables NOT modified:
--   exchange_rate_log             — global data (rates are the same for all users)
--   virtual_account_allocations   — already scoped via virtual_account_id FK
--   user_config                   — deprecated (kept for backward compat)
--   users, sessions, auth_tokens  — already user-aware
--
-- Strategy: nullable → backfill → NOT NULL → indexes → constraint updates.
-- This is safe for production: if the migration fails midway, no data is lost
-- because we only ADD columns (never drop).
-- =============================================================================

DO $$
DECLARE default_user_id UUID;
BEGIN
    -- Get the migrated user's ID (created in migration 000027).
    SELECT id INTO default_user_id FROM users LIMIT 1;
    IF default_user_id IS NULL THEN
        RAISE EXCEPTION 'No user found in users table. Migration 000027 must run first.';
    END IF;

    -- Step 1: Add nullable user_id columns to all tables.
    ALTER TABLE institutions ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id);
    ALTER TABLE accounts ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id);
    ALTER TABLE categories ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id);
    ALTER TABLE persons ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id);
    ALTER TABLE transactions ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id);
    ALTER TABLE recurring_rules ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id);
    ALTER TABLE investments ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id);
    ALTER TABLE installment_plans ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id);
    ALTER TABLE virtual_accounts ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id);
    ALTER TABLE budgets ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id);
    ALTER TABLE daily_snapshots ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id);
    ALTER TABLE account_snapshots ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id);

    -- Step 2: Backfill — assign ALL existing production data to the migrated user.
    UPDATE institutions SET user_id = default_user_id WHERE user_id IS NULL;
    UPDATE accounts SET user_id = default_user_id WHERE user_id IS NULL;
    UPDATE categories SET user_id = default_user_id WHERE user_id IS NULL;
    UPDATE persons SET user_id = default_user_id WHERE user_id IS NULL;
    UPDATE transactions SET user_id = default_user_id WHERE user_id IS NULL;
    UPDATE recurring_rules SET user_id = default_user_id WHERE user_id IS NULL;
    UPDATE investments SET user_id = default_user_id WHERE user_id IS NULL;
    UPDATE installment_plans SET user_id = default_user_id WHERE user_id IS NULL;
    UPDATE virtual_accounts SET user_id = default_user_id WHERE user_id IS NULL;
    UPDATE budgets SET user_id = default_user_id WHERE user_id IS NULL;
    UPDATE daily_snapshots SET user_id = default_user_id WHERE user_id IS NULL;
    UPDATE account_snapshots SET user_id = default_user_id WHERE user_id IS NULL;

    -- Step 3: Make NOT NULL (all rows now have user_id from backfill).
    ALTER TABLE institutions ALTER COLUMN user_id SET NOT NULL;
    ALTER TABLE accounts ALTER COLUMN user_id SET NOT NULL;
    ALTER TABLE categories ALTER COLUMN user_id SET NOT NULL;
    ALTER TABLE persons ALTER COLUMN user_id SET NOT NULL;
    ALTER TABLE transactions ALTER COLUMN user_id SET NOT NULL;
    ALTER TABLE recurring_rules ALTER COLUMN user_id SET NOT NULL;
    ALTER TABLE investments ALTER COLUMN user_id SET NOT NULL;
    ALTER TABLE installment_plans ALTER COLUMN user_id SET NOT NULL;
    ALTER TABLE virtual_accounts ALTER COLUMN user_id SET NOT NULL;
    ALTER TABLE budgets ALTER COLUMN user_id SET NOT NULL;
    ALTER TABLE daily_snapshots ALTER COLUMN user_id SET NOT NULL;
    ALTER TABLE account_snapshots ALTER COLUMN user_id SET NOT NULL;
END $$;

-- Step 4: Indexes on user_id for every table (query performance).
CREATE INDEX idx_institutions_user ON institutions(user_id);
CREATE INDEX idx_accounts_user ON accounts(user_id);
CREATE INDEX idx_categories_user ON categories(user_id);
CREATE INDEX idx_persons_user ON persons(user_id);
CREATE INDEX idx_transactions_user ON transactions(user_id);
CREATE INDEX idx_recurring_rules_user ON recurring_rules(user_id);
CREATE INDEX idx_investments_user ON investments(user_id);
CREATE INDEX idx_installment_plans_user ON installment_plans(user_id);
CREATE INDEX idx_virtual_accounts_user ON virtual_accounts(user_id);
CREATE INDEX idx_budgets_user ON budgets(user_id);
CREATE INDEX idx_daily_snapshots_user ON daily_snapshots(user_id);
CREATE INDEX idx_account_snapshots_user ON account_snapshots(user_id);

-- Step 5: Composite indexes for common multi-user query patterns.
CREATE INDEX idx_transactions_user_date ON transactions(user_id, date DESC);
CREATE INDEX idx_transactions_user_account ON transactions(user_id, account_id);

-- Step 6: Update unique constraints to include user_id.
-- budgets: UNIQUE(category_id, currency) → UNIQUE(user_id, category_id, currency)
-- Two users can now have budgets for the same category+currency combo.
ALTER TABLE budgets DROP CONSTRAINT budgets_category_id_currency_key;
ALTER TABLE budgets ADD CONSTRAINT budgets_user_category_currency_key UNIQUE(user_id, category_id, currency);

-- daily_snapshots: UNIQUE(date) → UNIQUE(user_id, date)
-- Two users can now have snapshots for the same date.
ALTER TABLE daily_snapshots DROP CONSTRAINT daily_snapshots_date_key;
ALTER TABLE daily_snapshots ADD CONSTRAINT daily_snapshots_user_date_key UNIQUE(user_id, date);
