-- =============================================================================
-- Migration 000007: Seed Default Categories
-- =============================================================================
--
-- DATA MIGRATION (Seeding Inside a Migration)
-- ---------------------------------------------
-- This migration inserts initial data rather than creating/altering schema.
-- It seeds the categories table with default expense and income categories.
--
-- Why seed in a migration instead of a separate seeder?
--
-- In Laravel, you'd typically put this in database/seeders/CategorySeeder.php
-- and run `php artisan db:seed`. In Django, you'd use a data migration:
--   python manage.py makemigrations --empty categories
--   // then add RunPython(seed_categories) to the migration
--
-- The PROBLEM with separate seeders:
--   - Seeders are optional — someone might forget to run them.
--   - Seeders run separately from migrations — ordering is not guaranteed.
--   - In production, seeders are often skipped entirely.
--
-- The ADVANTAGE of seeding in a migration:
--   - Data is guaranteed to exist after migrations run (any environment).
--   - Runs in the correct order (after categories table is created in 000003).
--   - Idempotent with the migration system — runs exactly once, tracked in
--     the schema_migrations table (like Laravel's migrations table).
--
-- is_system = true: marks these as built-in categories that the user cannot delete.
-- display_order: determines the order in dropdowns and lists.
-- =============================================================================

-- Default expense categories (PRD C-1)
INSERT INTO categories (name, type, is_system, display_order) VALUES
    ('Household',        'expense', true, 1),
    ('Food & Groceries', 'expense', true, 2),
    ('Transport',        'expense', true, 3),
    ('Health',           'expense', true, 4),
    ('Education',        'expense', true, 5),
    ('Mobile',           'expense', true, 6),
    ('Electricity',      'expense', true, 7),
    ('Gas',              'expense', true, 8),
    ('Internet',         'expense', true, 9),
    ('Gifts',            'expense', true, 10),
    ('Entertainment',    'expense', true, 11),
    ('Shopping',         'expense', true, 12),
    ('Subscriptions',    'expense', true, 13),
    ('Building Fund',    'expense', true, 14),
    ('Insurance',        'expense', true, 15),
    ('Fees & Charges',   'expense', true, 16),
    ('Debt Payment',     'expense', true, 17),
    ('Other',            'expense', true, 18);

-- Default income categories (PRD C-2)
INSERT INTO categories (name, type, is_system, display_order) VALUES
    ('Salary',                    'income', true, 1),
    ('Freelance',                 'income', true, 2),
    ('Investment Returns',        'income', true, 3),
    ('Refund',                    'income', true, 4),
    ('Building Fund Collection',  'income', true, 5),
    ('Loan Repayment Received',   'income', true, 6),
    ('Other',                     'income', true, 7);
