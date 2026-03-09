-- =============================================================================
-- Migration 000013: Performance Indexes and Materialized Views
-- =============================================================================
--
-- This migration adds performance optimizations: a PostgreSQL extension (pg_trgm),
-- additional indexes (including partial and GIN indexes), and materialized views.
-- These don't change the data model — they make queries faster.
--
-- IMPORTANT: IF NOT EXISTS
-- -------------------------
-- Many indexes here use IF NOT EXISTS because some were already created in earlier
-- migrations (000001-000005). This is a consolidation — gathering all performance
-- indexes in one place. IF NOT EXISTS makes this idempotent (safe to re-run).
-- =============================================================================

-- Performance indexes for common query patterns.

-- =============================================================================
-- pg_trgm EXTENSION — Trigram-Based Text Search
-- =============================================================================
-- CREATE EXTENSION loads a PostgreSQL extension — like installing a package/plugin.
-- pg_trgm enables fast fuzzy text search using trigrams (3-character sequences).
--
-- Example: the word "hello" produces trigrams: "  h", " he", "hel", "ell", "llo", "lo "
-- PostgreSQL compares trigram sets to find similar strings, even with typos.
--
-- This powers ILIKE (case-insensitive LIKE) queries with index support:
--   SELECT * FROM transactions WHERE note ILIKE '%grocery%';
-- Without pg_trgm, ILIKE '%text%' does a full table scan (very slow on large tables).
-- With pg_trgm + GIN index, it uses the index for fast lookups.
--
-- Laravel: You'd use DB::statement('CREATE EXTENSION IF NOT EXISTS pg_trgm');
--          Laravel Scout (full-text search) uses a different approach (external engines).
-- Django:  from django.contrib.postgres.operations import TrigramExtension
--          // In a migration: operations = [TrigramExtension()]
--          // Then use TrigramSimilarity in querysets.
--
-- Docs: https://www.postgresql.org/docs/current/pgtrgm.html
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Transactions: frequently filtered/sorted by account, date, type
CREATE INDEX IF NOT EXISTS idx_transactions_account_id ON transactions (account_id);

-- DESC index: queries that ORDER BY date DESC (most recent first) benefit from
-- a descending index. Without DESC, PG can still read the index backwards, but
-- DESC is slightly more efficient for the dominant query pattern.
CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions (date DESC);

-- COMPOSITE INDEX: covers queries that filter by account AND sort by date.
-- Example: SELECT * FROM transactions WHERE account_id = ? ORDER BY date DESC;
-- A composite index (account_id, date DESC) is much faster than two separate indexes
-- because PG can satisfy both the WHERE and ORDER BY from a single index scan.
--
-- Laravel: $table->index(['account_id', 'date']);  // but can't specify DESC per column
-- Django:  models.Index(fields=['account_id', '-date'])  // the '-' means DESC
CREATE INDEX IF NOT EXISTS idx_transactions_account_date ON transactions (account_id, date DESC);

CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions (type);

-- PARTIAL INDEXES (WHERE clause)
-- --------------------------------
-- These indexes only include rows matching the WHERE condition.
-- They're smaller and faster than full indexes when you only query a subset of data.
--
-- Example: idx_transactions_category only indexes rows where category_id IS NOT NULL.
-- Transfers and exchanges don't have categories, so they're excluded from this index.
-- Result: smaller index → fits in memory → faster lookups.
--
-- Laravel: Not supported natively. Use DB::statement() with raw SQL.
-- Django:  models.Index(fields=['category_id'], condition=Q(category_id__isnull=False))
--
-- Docs: https://www.postgresql.org/docs/current/indexes-partial.html
CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions (category_id) WHERE category_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_transactions_person ON transactions (person_id) WHERE person_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_transactions_building_fund ON transactions (is_building_fund) WHERE is_building_fund = true;
CREATE INDEX IF NOT EXISTS idx_transactions_recurring ON transactions (recurring_rule_id) WHERE recurring_rule_id IS NOT NULL;

-- GIN INDEX with TRIGRAM OPS — Full-Text-Like Search on note Column
-- -------------------------------------------------------------------
-- GIN (Generalized Inverted Index) is a special index type for multi-valued data.
-- Combined with gin_trgm_ops (trigram operator class from pg_trgm), it enables
-- fast pattern matching with LIKE, ILIKE, and similarity queries.
--
-- USING gin: specifies the GIN index type (default is B-tree).
-- gin_trgm_ops: tells PG to index trigrams of the text, not the text itself.
--
-- This turns a slow O(n) full table scan for ILIKE '%search%' into a fast
-- index-assisted lookup. Essential for the transaction search feature.
--
-- Laravel: DB::statement("CREATE INDEX ... USING gin (note gin_trgm_ops)");
-- Django:  GinIndex(fields=['note'], opclasses=['gin_trgm_ops'])
--          // from django.contrib.postgres.indexes import GinIndex
--
-- Docs: https://www.postgresql.org/docs/current/gin-intro.html
CREATE INDEX IF NOT EXISTS idx_transactions_note_trgm ON transactions USING gin (note gin_trgm_ops);

-- Accounts: frequently joined with institutions
CREATE INDEX IF NOT EXISTS idx_accounts_institution ON accounts (institution_id);
CREATE INDEX IF NOT EXISTS idx_accounts_display_order ON accounts (display_order);

-- =============================================================================
-- MATERIALIZED VIEWS
-- =============================================================================
-- A materialized view is like a regular VIEW, but it stores the query results
-- physically on disk. It's essentially a "cached query" that you refresh manually.
--
-- Regular VIEW: re-runs the query every time you SELECT from it (always fresh, slower).
-- MATERIALIZED VIEW: stores results on disk (stale until refreshed, but instant reads).
--
-- Think of it like Laravel's cache:
--   Cache::remember('monthly_totals', 3600, fn() => DB::table('transactions')->...->get());
-- Or Django's cache framework:
--   cache.get_or_set('monthly_totals', lambda: Transaction.objects.aggregate(...), 3600)
--
-- Except it's built into the database and queryable with SQL (JOINs, WHERE, etc.).
--
-- REFRESH MATERIALIZED VIEW mv_monthly_category_totals;
--   ^ This command re-runs the query and updates the stored data.
--   The app calls this after processing recurring rules at startup.
--
-- Docs: https://www.postgresql.org/docs/current/sql-creatematerializedview.html
-- =============================================================================

-- Materialized view: monthly spending summary by category.
-- Avoids repeated aggregation on every reports page load.
--
-- date_trunc('month', date)::date — truncates a date to the first of its month.
--   2024-03-15 → 2024-03-01. The ::date casts TIMESTAMPTZ back to DATE.
--   Laravel: DB::raw("DATE_TRUNC('month', date)")  or Carbon methods
--   Django:  TruncMonth('date') from django.db.models.functions
--
-- GROUP BY with multiple columns: creates one row per unique combination of
-- (month, category, type, currency, account). Each row has the SUM and COUNT
-- for that specific combination.
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_monthly_category_totals AS
SELECT
    date_trunc('month', date)::date AS month,
    category_id,
    type,
    currency,
    account_id,
    SUM(amount) AS total_amount,
    COUNT(*) AS tx_count
FROM transactions
WHERE category_id IS NOT NULL
GROUP BY date_trunc('month', date), category_id, type, currency, account_id;

-- UNIQUE INDEX on materialized view
-- ------------------------------------
-- Required for REFRESH MATERIALIZED VIEW CONCURRENTLY (non-blocking refresh).
-- Without a unique index, REFRESH locks the view and blocks all reads.
-- With a unique index, CONCURRENTLY swaps in the new data without blocking.
--
-- The unique index columns must match the GROUP BY columns exactly.
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_monthly_cat_uniq
    ON mv_monthly_category_totals (month, category_id, type, currency, account_id);

-- Materialized view: daily transaction counts (for streak computation).
-- The dashboard shows a "habit streak" — how many consecutive days the user
-- has logged at least one transaction. This view makes that query fast.
--
-- date::date — casts the date column to a DATE type (removes any time component).
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_daily_tx_counts AS
SELECT
    date::date AS tx_date,
    COUNT(*) AS tx_count
FROM transactions
GROUP BY date::date;

-- Unique index for concurrent refresh support.
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_daily_tx_date ON mv_daily_tx_counts (tx_date);
