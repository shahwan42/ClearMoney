-- =============================================================================
-- Migration 000003: Create Categories Table
-- =============================================================================
--
-- Categories classify transactions as "expense" or "income" types.
-- This table has both system-defined (seeded) and user-created categories.
--
-- SYSTEM vs CUSTOM CATEGORIES PATTERN
-- -------------------------------------
-- The is_system flag distinguishes pre-loaded categories from user-created ones.
-- System categories (is_system = true) are seeded in migration 000007 and
-- cannot be deleted by the user. Custom categories (is_system = false) are
-- user-created and fully editable.
--
-- This is a common pattern in Laravel/Django apps too:
--   - Laravel: You might use a seeder (php artisan db:seed) with a `is_system` flag.
--   - Django: You might use a data migration or management command for initial data.
--
-- The difference here: we seed inside a migration (000007), not a separate seeder.
-- This guarantees the data exists in every environment (dev, staging, prod) because
-- migrations run automatically. Seeders are often forgotten or skipped.
--
-- SOFT DELETE (is_archived)
-- --------------------------
-- Instead of deleting categories, we archive them (is_archived = true).
-- Archived categories don't appear in dropdowns but still linked to old transactions.
-- Laravel: uses SoftDeletes trait with a deleted_at timestamp column.
-- Django:  no built-in soft delete — you'd add an is_active field manually or use
--          django-soft-delete package.
-- =============================================================================

CREATE TYPE category_type AS ENUM ('expense', 'income');

CREATE TABLE categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    type category_type NOT NULL,
    icon TEXT,
    is_system BOOLEAN NOT NULL DEFAULT false,
    is_archived BOOLEAN NOT NULL DEFAULT false,
    display_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index on type for filtering categories by expense/income.
-- Used on every "add transaction" page to show the relevant category dropdown.
CREATE INDEX idx_categories_type ON categories (type);
