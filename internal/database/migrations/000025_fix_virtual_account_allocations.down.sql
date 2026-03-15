-- Reverse 000025: Restore original virtual account allocation behavior.

-- 4. Restore original unique constraint
DROP INDEX IF EXISTS idx_vaa_tx_va_unique;
ALTER TABLE virtual_account_allocations
  ADD CONSTRAINT virtual_account_allocations_tx_id_virtual_account_id_key
  UNIQUE (transaction_id, virtual_account_id);

-- 3. Remove direct allocation metadata
ALTER TABLE virtual_account_allocations DROP COLUMN IF EXISTS allocated_at;
ALTER TABLE virtual_account_allocations DROP COLUMN IF EXISTS note;

-- 2. Remove direct allocations and restore NOT NULL
DELETE FROM virtual_account_allocations WHERE transaction_id IS NULL;
ALTER TABLE virtual_account_allocations ALTER COLUMN transaction_id SET NOT NULL;

-- 1. Remove account link
DROP INDEX IF EXISTS idx_va_account_id;
ALTER TABLE virtual_accounts DROP COLUMN IF EXISTS account_id;
