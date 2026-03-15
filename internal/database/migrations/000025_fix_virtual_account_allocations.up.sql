-- 000025: Fix virtual account allocations for proper envelope budgeting.
--
-- Three changes:
-- 1. Link virtual accounts to a specific bank account (nullable for existing VAs)
-- 2. Allow direct allocations without a transaction (envelope earmarking)
-- 3. Add metadata columns (note, date) for direct allocations

-- 1. Link VAs to bank accounts
ALTER TABLE virtual_accounts ADD COLUMN account_id UUID REFERENCES accounts(id) ON DELETE SET NULL;
CREATE INDEX idx_va_account_id ON virtual_accounts (account_id);

-- 2. Allow direct allocations (no transaction required)
ALTER TABLE virtual_account_allocations ALTER COLUMN transaction_id DROP NOT NULL;

-- 3. Add metadata for direct allocations
ALTER TABLE virtual_account_allocations ADD COLUMN note TEXT;
ALTER TABLE virtual_account_allocations ADD COLUMN allocated_at DATE;

-- 4. Replace unique constraint with partial index (only for tx-linked allocations)
--    NULLs in transaction_id are treated as distinct by PostgreSQL, so multiple
--    direct allocations to the same VA are allowed.
ALTER TABLE virtual_account_allocations
  DROP CONSTRAINT virtual_account_allocations_tx_id_virtual_account_id_key;
CREATE UNIQUE INDEX idx_vaa_tx_va_unique
  ON virtual_account_allocations (transaction_id, virtual_account_id)
  WHERE transaction_id IS NOT NULL;
