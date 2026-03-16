-- Fix the categories unique index to include user_id.
-- The old index (name, type) prevented different users from having the same category names.
-- The new index (user_id, name, type) allows each user to have their own set of categories.
DROP INDEX IF EXISTS idx_categories_name_type;
CREATE UNIQUE INDEX idx_categories_name_type ON categories (user_id, name, type);
