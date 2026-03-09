-- TASK-068: Account health constraints — min balance and min monthly deposit.
-- Stored as JSONB to keep the schema flexible for future health rules.
-- Example: {"min_balance": 5000, "min_monthly_deposit": 1000}
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS health_config JSONB DEFAULT NULL;
