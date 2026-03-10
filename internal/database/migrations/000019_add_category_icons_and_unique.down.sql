-- Remove icons from all system categories
UPDATE categories SET icon = NULL WHERE is_system = true;

-- Drop the unique constraint
DROP INDEX IF EXISTS idx_categories_name_type;
