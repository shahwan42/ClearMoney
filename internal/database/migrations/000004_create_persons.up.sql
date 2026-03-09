-- =============================================================================
-- Migration 000004: Create Persons Table
-- =============================================================================
--
-- Tracks people you lend money to or borrow money from.
-- Transactions of type 'loan_out', 'loan_in', 'loan_repayment' reference a person.
--
-- CACHED BALANCE PATTERN (net_balance)
-- --------------------------------------
-- net_balance stores the computed balance for each person:
--   Positive = they owe you money (you lent to them)
--   Negative = you owe them money (you borrowed from them)
--   Zero     = all settled
--
-- This is a DENORMALIZED field — the "true" balance could be computed by summing
-- all related transactions, but that would require a JOIN + SUM on every read.
-- Instead, we cache the result and update it whenever a loan transaction is created.
--
-- This is exactly like Laravel's withCount() or Django's annotate(Sum(...)),
-- except the value is pre-computed and stored in the row for instant reads.
--
-- Trade-off:
--   PRO: Reads are instant — just SELECT net_balance (no aggregation).
--   CON: Writes must update this field — if the update is missed, data goes stale.
--        The reconciliation job (make reconcile) catches and fixes any drift.
--
-- Laravel equivalent pattern:
--   // In Person model: $person->update(['net_balance' => $person->transactions()->sum('amount')]);
-- Django equivalent pattern:
--   // person.net_balance = person.transactions.aggregate(Sum('amount'))['amount__sum']
--   // person.save()
--
-- NULLABLE vs DEFAULT
-- --------------------
-- note TEXT (no NOT NULL, no DEFAULT): can be NULL, meaning "no note provided."
-- net_balance NUMERIC DEFAULT 0: can never be NULL, starts at zero.
-- =============================================================================

CREATE TABLE persons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    note TEXT,
    net_balance NUMERIC(15, 2) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
