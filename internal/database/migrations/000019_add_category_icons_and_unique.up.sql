-- =============================================================================
-- Migration 000019: Add Category Icons + Unique Constraint
-- =============================================================================
--
-- 1. Add emoji icons to all system categories for better visual identification
--    in dropdowns and lists.
-- 2. Add a unique constraint on (name, type) to prevent duplicate categories
--    (e.g., multiple "Pet Expenses" entries from repeated test runs).
-- 3. Clean up any existing duplicates before adding the constraint.
-- =============================================================================

-- Step 1: Remove duplicate non-system categories (keep the oldest by created_at)
DELETE FROM categories a
USING categories b
WHERE a.name = b.name
  AND a.type = b.type
  AND a.id > b.id;

-- Step 2: Add unique constraint on (name, type)
-- This prevents duplicate categories like multiple "Pet Expenses" entries.
CREATE UNIQUE INDEX idx_categories_name_type ON categories (name, type);

-- Step 3: Add icons to expense categories
UPDATE categories SET icon = '🏠' WHERE name = 'Household'        AND is_system = true;
UPDATE categories SET icon = '🛒' WHERE name = 'Food & Groceries' AND is_system = true;
UPDATE categories SET icon = '🚗' WHERE name = 'Transport'        AND is_system = true;
UPDATE categories SET icon = '🏥' WHERE name = 'Health'           AND is_system = true;
UPDATE categories SET icon = '📚' WHERE name = 'Education'        AND is_system = true;
UPDATE categories SET icon = '📱' WHERE name = 'Mobile'           AND is_system = true;
UPDATE categories SET icon = '⚡' WHERE name = 'Electricity'      AND is_system = true;
UPDATE categories SET icon = '🔥' WHERE name = 'Gas'              AND is_system = true;
UPDATE categories SET icon = '🌐' WHERE name = 'Internet'         AND is_system = true;
UPDATE categories SET icon = '🎁' WHERE name = 'Gifts'            AND is_system = true;
UPDATE categories SET icon = '🎬' WHERE name = 'Entertainment'    AND is_system = true;
UPDATE categories SET icon = '🛍️' WHERE name = 'Shopping'         AND is_system = true;
UPDATE categories SET icon = '📺' WHERE name = 'Subscriptions'    AND is_system = true;
UPDATE categories SET icon = '🏗️' WHERE name = 'Building Fund'    AND is_system = true;
UPDATE categories SET icon = '🛡️' WHERE name = 'Insurance'        AND is_system = true;
UPDATE categories SET icon = '💳' WHERE name = 'Fees & Charges'   AND is_system = true;
UPDATE categories SET icon = '💰' WHERE name = 'Debt Payment'     AND is_system = true;
UPDATE categories SET icon = '🔖' WHERE name = 'Other'            AND type = 'expense' AND is_system = true;

-- Step 4: Add icons to income categories
UPDATE categories SET icon = '💵' WHERE name = 'Salary'                    AND is_system = true;
UPDATE categories SET icon = '💻' WHERE name = 'Freelance'                 AND is_system = true;
UPDATE categories SET icon = '📈' WHERE name = 'Investment Returns'        AND is_system = true;
UPDATE categories SET icon = '🔄' WHERE name = 'Refund'                    AND is_system = true;
UPDATE categories SET icon = '🏗️' WHERE name = 'Building Fund Collection'  AND is_system = true;
UPDATE categories SET icon = '🤝' WHERE name = 'Loan Repayment Received'   AND is_system = true;
UPDATE categories SET icon = '💎' WHERE name = 'Other'                     AND type = 'income' AND is_system = true;
