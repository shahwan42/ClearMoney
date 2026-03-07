-- Add balance_delta column to transactions to store the actual balance impact.
-- This makes reconciliation straightforward: expected_balance = initial_balance + SUM(balance_delta).
-- For existing transactions, we can't retroactively determine the delta for transfers/exchanges,
-- so we leave them as 0 and only populate going forward.
ALTER TABLE transactions ADD COLUMN balance_delta NUMERIC(15,2) NOT NULL DEFAULT 0;
