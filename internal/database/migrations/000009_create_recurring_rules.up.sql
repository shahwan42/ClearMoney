-- =============================================================================
-- Migration 000009: Create Recurring Rules Table
-- =============================================================================
--
-- Recurring rules define transactions that repeat on a schedule (e.g., monthly
-- rent, weekly groceries). When the next_due_date arrives, the system either
-- auto-creates the transaction or prompts the user to confirm.
--
-- JSONB TEMPLATE PATTERN
-- ------------------------
-- template_transaction stores the full transaction data as a JSONB object:
--   {
--     "type": "expense",
--     "amount": 5000,
--     "currency": "EGP",
--     "account_id": "uuid-here",
--     "category_id": "uuid-here",
--     "note": "Monthly rent"
--   }
--
-- Why JSONB instead of separate columns?
--   1. Flexibility: the template mirrors the transactions table structure, but
--      we don't need a rigid schema for it. New transaction fields are automatically
--      supported without ALTER TABLE on recurring_rules.
--   2. Simplicity: one column instead of duplicating every transactions column.
--   3. Queries: we rarely query inside the template — we just read it whole
--      and use it to create a new transaction.
--
-- Laravel equivalent:
--   $table->jsonb('template_transaction');
--   // In the model: protected $casts = ['template_transaction' => 'array'];
--
-- Django equivalent:
--   template_transaction = models.JSONField()
--   // Access: rule.template_transaction['amount']
--
-- CHECK CONSTRAINT with IN()
-- ----------------------------
-- CHECK (frequency IN ('monthly', 'weekly')) restricts the column to specific values.
-- This is similar to an ENUM but uses VARCHAR + CHECK instead of CREATE TYPE.
--
-- Why CHECK instead of ENUM here?
--   - ENUMs are great for types used across multiple tables (like currency_type).
--   - CHECK constraints are simpler for single-table-use values.
--   - Adding values to a CHECK is easier than ALTER TYPE ... ADD VALUE for enums.
--
-- Laravel: $table->string('frequency', 20); with validation rule: Rule::in(['monthly', 'weekly'])
-- Django:  frequency = models.CharField(max_length=20, choices=[('monthly','Monthly'),('weekly','Weekly')])
--
-- auto_confirm: if true, the recurring job creates the transaction automatically.
--               if false, the transaction is created in a "pending" state for user review.
--
-- Docs: https://www.postgresql.org/docs/current/ddl-constraints.html#DDL-CONSTRAINTS-CHECK-CONSTRAINTS
-- =============================================================================

CREATE TABLE IF NOT EXISTS recurring_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_transaction JSONB NOT NULL,
    frequency VARCHAR(20) NOT NULL CHECK (frequency IN ('monthly', 'weekly')),
    day_of_month INTEGER,
    next_due_date DATE NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    auto_confirm BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
