-- Remove the legacy building fund feature.
-- Data was already migrated to virtual_funds in migration 000015.

-- Drop the partial index first
DROP INDEX IF EXISTS idx_transactions_building_fund;

-- Drop the column
ALTER TABLE transactions DROP COLUMN IF EXISTS is_building_fund;

-- Rename building fund categories to virtual fund
UPDATE categories SET name = 'Virtual Fund', icon = '🏦' WHERE name = 'Building Fund' AND type = 'expense';
UPDATE categories SET name = 'Virtual Fund', icon = '🏦' WHERE name = 'Building Fund Collection' AND type = 'income';
