-- =============================================================================
-- Migration 000001: Create Institutions Table
-- =============================================================================
--
-- This migration creates a custom PostgreSQL enum type and the institutions table.
--
-- POSTGRESQL ENUM TYPES (CREATE TYPE ... AS ENUM)
-- ------------------------------------------------
-- In PostgreSQL, you can define your own data types. An ENUM type restricts a column
-- to a fixed set of string values, enforced at the database level.
--
-- Laravel equivalent:
--   $table->enum('type', ['bank', 'fintech']);
--   // Under the hood, Laravel uses a CHECK constraint, not a real PG enum.
--   // A real PG enum is more type-safe and performs better (stored as integers internally).
--
-- Django equivalent:
--   class InstitutionType(models.TextChoices):
--       BANK = 'bank'
--       FINTECH = 'fintech'
--   type = models.CharField(max_length=10, choices=InstitutionType.choices)
--   // Django uses a VARCHAR + application-level validation, not a DB-level enum.
--
-- Advantage of PG enums: the database itself rejects invalid values — no bad data
-- can sneak in even if you bypass the app layer (e.g., manual SQL inserts).
--
-- Docs: https://www.postgresql.org/docs/current/datatype-enum.html
-- =============================================================================

CREATE TYPE institution_type AS ENUM ('bank', 'fintech');

-- CREATE TABLE institutions
-- -------------------------
-- UUID PRIMARY KEY DEFAULT gen_random_uuid()
--   PostgreSQL can auto-generate UUIDs. gen_random_uuid() is a built-in function (PG 13+).
--   Laravel: $table->uuid('id')->primary();  // or $table->id() for auto-increment
--   Django:  id = models.UUIDField(primary_key=True, default=uuid.uuid4)
--
-- TEXT vs VARCHAR
--   PostgreSQL's TEXT type has no length limit and performs identically to VARCHAR.
--   Unlike MySQL, there's no performance penalty for using TEXT in PostgreSQL.
--   Laravel: $table->string('name')  // creates VARCHAR(255)
--   Django:  name = models.CharField(max_length=255)  // requires max_length
--   In PG, TEXT is generally preferred unless you need a specific length constraint.
--
-- TIMESTAMPTZ
--   Timestamp WITH time zone. Always stores as UTC internally, converts on display.
--   Laravel: $table->timestampTz('created_at')  // or $table->timestamps() for both
--   Django:  created_at = models.DateTimeField(auto_now_add=True)  // always timezone-aware
--   Always use TIMESTAMPTZ over TIMESTAMP — avoids timezone bugs.
--
-- DEFAULT now()
--   Automatically sets the current timestamp when a row is inserted.
--   Laravel: $table->timestamp('created_at')->useCurrent()
--   Django:  auto_now_add=True does this automatically
CREATE TABLE institutions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    type institution_type NOT NULL DEFAULT 'bank',
    color TEXT,
    icon TEXT,
    display_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- CREATE INDEX
-- ------------
-- An index speeds up queries that filter or sort by display_order.
-- Without an index, PG would scan every row (sequential scan). With an index,
-- it can jump directly to the relevant rows (index scan).
--
-- Laravel: $table->index('display_order');
-- Django:  class Meta: indexes = [models.Index(fields=['display_order'])]
--
-- Naming convention: idx_<table>_<column> is a common PostgreSQL pattern.
CREATE INDEX idx_institutions_display_order ON institutions (display_order);
