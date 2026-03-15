-- Reverse the virtual funds → virtual accounts rename.

-- Rename category names back
UPDATE categories SET name = 'Virtual Fund' WHERE name = 'Virtual Account';

-- Rename unique constraint back
ALTER INDEX virtual_account_allocations_tx_id_virtual_account_id_key
  RENAME TO transaction_fund_allocations_transaction_id_virtual_fund_id_key;

-- Rename indexes back
ALTER INDEX idx_vaa_virtual_account_id RENAME TO idx_tfa_fund_id;
ALTER INDEX idx_vaa_transaction_id RENAME TO idx_tfa_transaction_id;

-- Rename columns back
ALTER TABLE virtual_account_allocations RENAME COLUMN virtual_account_id TO virtual_fund_id;

-- Rename tables back
ALTER TABLE virtual_account_allocations RENAME TO transaction_fund_allocations;
ALTER TABLE virtual_accounts RENAME TO virtual_funds;
