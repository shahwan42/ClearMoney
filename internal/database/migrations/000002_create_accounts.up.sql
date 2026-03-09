-- =============================================================================
-- Migration 000002: Create Accounts Table
-- =============================================================================
--
-- This migration demonstrates several PostgreSQL-specific features:
-- multiple ENUM types, JSONB columns, array columns, foreign keys with CASCADE,
-- and multiple indexes.
--
-- MULTIPLE ENUM TYPES
-- --------------------
-- We define two separate enums here. Each creates a reusable type in the database.
-- Once defined, these types can be referenced in any table (e.g., currency_type
-- is also used in the transactions table later).
--
-- account_type: the kind of financial account
-- currency_type: supported currencies (EGP = Egyptian Pound, USD = US Dollar)
-- =============================================================================

-- Laravel: No direct equivalent — would use $table->enum() with CHECK constraint.
-- Django: Would use TextChoices classes for each.
CREATE TYPE account_type AS ENUM ('checking', 'savings', 'current', 'prepaid', 'credit_card', 'credit_limit');
CREATE TYPE currency_type AS ENUM ('EGP', 'USD');

CREATE TABLE accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- FOREIGN KEY with ON DELETE CASCADE
    -- ------------------------------------
    -- REFERENCES institutions(id): links each account to an institution.
    -- ON DELETE CASCADE: if the parent institution is deleted, all its accounts
    -- are automatically deleted too. This is like a database-level "cascading delete."
    --
    -- Laravel: $table->foreignUuid('institution_id')->constrained()->cascadeOnDelete();
    -- Django:  institution = models.ForeignKey(Institution, on_delete=models.CASCADE)
    --
    -- Other options: ON DELETE SET NULL (nullify the FK), ON DELETE RESTRICT (prevent deletion).
    -- Docs: https://www.postgresql.org/docs/current/ddl-constraints.html#DDL-CONSTRAINTS-FK
    institution_id UUID NOT NULL REFERENCES institutions(id) ON DELETE CASCADE,

    name TEXT NOT NULL,
    type account_type NOT NULL,
    currency currency_type NOT NULL DEFAULT 'EGP',

    -- NUMERIC(15, 2) — Exact Decimal Type
    -- -------------------------------------
    -- NUMERIC(precision, scale): stores exact decimal numbers with no floating-point errors.
    -- 15 total digits, 2 after the decimal point. Max value: 9,999,999,999,999.99
    -- CRITICAL for money: never use FLOAT/DOUBLE for currency (0.1 + 0.2 ≠ 0.3 in floats).
    --
    -- Laravel: $table->decimal('current_balance', 15, 2)->default(0);
    -- Django:  current_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    --
    -- Docs: https://www.postgresql.org/docs/current/datatype-numeric.html#DATATYPE-NUMERIC-DECIMAL
    current_balance NUMERIC(15, 2) NOT NULL DEFAULT 0,
    initial_balance NUMERIC(15, 2) NOT NULL DEFAULT 0,

    -- NULLABLE column (no NOT NULL constraint)
    -- -----------------------------------------
    -- credit_limit is nullable because only credit card accounts have a limit.
    -- NULL means "not applicable" — different from 0, which means "zero limit."
    --
    -- Laravel: $table->decimal('credit_limit', 15, 2)->nullable();
    -- Django:  credit_limit = models.DecimalField(..., null=True, blank=True)
    credit_limit NUMERIC(15, 2),

    is_dormant BOOLEAN NOT NULL DEFAULT false,

    -- TEXT[] — PostgreSQL Array Column
    -- ---------------------------------
    -- PostgreSQL supports native array columns — a single column can hold a list of values.
    -- Here, role_tags stores tags like ['salary', 'savings', 'emergency'].
    -- You can query arrays with operators: @> (contains), && (overlaps), ANY().
    -- Example: SELECT * FROM accounts WHERE 'salary' = ANY(role_tags);
    --
    -- Laravel: No native support. You'd use a JSON column or a pivot table.
    -- Django:  from django.contrib.postgres.fields import ArrayField
    --          role_tags = ArrayField(models.CharField(max_length=50), default=list)
    --
    -- DEFAULT '{}' sets an empty array (not NULL). This avoids NULL checks in queries.
    -- Docs: https://www.postgresql.org/docs/current/arrays.html
    role_tags TEXT[] DEFAULT '{}',

    display_order INTEGER NOT NULL DEFAULT 0,

    -- JSONB — Binary JSON Column
    -- ----------------------------
    -- JSONB stores JSON data in a binary format that supports indexing and querying.
    -- Unlike plain JSON, JSONB is decomposed into a binary structure on write, so
    -- reads and queries are much faster. You can query nested values:
    --   SELECT * FROM accounts WHERE metadata->>'billing_day' = '15';
    --   SELECT * FROM accounts WHERE metadata @> '{"billing_day": 15}';
    --
    -- Used here for flexible, schema-less metadata (billing cycle info for credit cards,
    -- etc.) without needing a separate table or ALTER TABLE for each new field.
    --
    -- Laravel: $table->jsonb('metadata')->default('{}');
    --          // Access in Eloquent: $account->metadata['billing_day']
    -- Django:  metadata = models.JSONField(default=dict)
    --          // Access: account.metadata.get('billing_day')
    --
    -- JSON vs JSONB:
    --   JSON: stores as-is (text), preserves whitespace/ordering. No indexing.
    --   JSONB: parsed on write, faster reads, supports GIN indexes. Always prefer JSONB.
    --
    -- Docs: https://www.postgresql.org/docs/current/datatype-json.html
    metadata JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Multiple indexes for common query patterns.
-- Each index speeds up queries that filter by that specific column.
-- Too many indexes slow down writes (each INSERT/UPDATE must update all indexes),
-- so only index columns you actually query on.
--
-- Laravel: $table->index('institution_id'); etc.
-- Django:  class Meta: indexes = [models.Index(fields=['institution_id']), ...]
CREATE INDEX idx_accounts_institution_id ON accounts (institution_id);
CREATE INDEX idx_accounts_type ON accounts (type);
CREATE INDEX idx_accounts_currency ON accounts (currency);
CREATE INDEX idx_accounts_display_order ON accounts (display_order);
