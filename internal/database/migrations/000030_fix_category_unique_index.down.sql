-- Revert to the old unique index without user_id.
DROP INDEX IF EXISTS idx_categories_name_type;
CREATE UNIQUE INDEX idx_categories_name_type ON categories (name, type);
