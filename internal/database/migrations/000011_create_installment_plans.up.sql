-- =============================================================================
-- Migration 000011: Create Installment Plans Table
-- =============================================================================
--
-- Tracks purchase installment plans (EPP = Equal Payment Plan).
-- Common in Egyptian credit cards — you buy something expensive and the bank
-- splits it into equal monthly payments (e.g., 12,000 EGP over 12 months = 1,000/month).
--
-- FOREIGN KEY WITHOUT CASCADE
-- -----------------------------
-- account_id references accounts(id) but does NOT specify ON DELETE CASCADE or SET NULL.
-- This means PostgreSQL uses the default: ON DELETE NO ACTION (also called RESTRICT).
--
-- ON DELETE NO ACTION / RESTRICT:
--   If you try to delete an account that has installment plans, PostgreSQL will
--   REFUSE the deletion with an error. This protects data integrity — you must
--   delete or reassign the installment plans before deleting the account.
--
-- Compare with other migrations:
--   000005 (transactions): ON DELETE CASCADE  — deletes transactions with the account
--   000005 (transactions): ON DELETE SET NULL — nullifies optional FK references
--   000011 (here):         (default RESTRICT) — prevents deletion entirely
--
-- When to use each:
--   CASCADE:  child data is meaningless without parent (transactions without account)
--   SET NULL: child can exist independently (transaction can lose its category link)
--   RESTRICT: child data is too important to lose (active installment plan = real debt)
--
-- Laravel: $table->foreignUuid('account_id')->constrained();
--          // Without ->cascadeOnDelete() or ->nullOnDelete(), Laravel also defaults to RESTRICT.
-- Django:  account = models.ForeignKey(Account, on_delete=models.PROTECT)
--          // models.PROTECT is Django's equivalent of RESTRICT.
--
-- REMAINING vs TOTAL INSTALLMENTS
-- ---------------------------------
-- Both num_installments and remaining_installments are stored.
-- remaining_installments is decremented each month when a payment is recorded.
-- Progress = (num_installments - remaining_installments) / num_installments * 100
--
-- This is simpler than computing remaining from payment transactions because
-- installment payments might not always be tracked as individual transactions.
-- =============================================================================

-- Installment plans (EPP) for tracking purchases split into monthly payments.
-- Typically on credit cards like TRU.
CREATE TABLE IF NOT EXISTS installment_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES accounts(id),
    description TEXT NOT NULL,
    total_amount NUMERIC(15,2) NOT NULL,
    num_installments INTEGER NOT NULL,
    monthly_amount NUMERIC(15,2) NOT NULL,
    start_date DATE NOT NULL,
    remaining_installments INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
