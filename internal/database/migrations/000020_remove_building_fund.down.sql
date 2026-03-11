-- Restore the legacy building fund column and index
ALTER TABLE transactions ADD COLUMN is_building_fund BOOLEAN NOT NULL DEFAULT false;
CREATE INDEX idx_transactions_building_fund ON transactions (is_building_fund) WHERE is_building_fund = true;

-- Restore category names
UPDATE categories SET name = 'Building Fund', icon = '🏗️' WHERE name = 'Virtual Fund' AND type = 'expense';
UPDATE categories SET name = 'Building Fund Collection', icon = '🏗️' WHERE name = 'Virtual Fund' AND type = 'income';
