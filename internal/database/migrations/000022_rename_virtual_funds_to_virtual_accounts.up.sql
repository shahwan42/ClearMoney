-- Rename "virtual funds" to "virtual accounts" across all database objects.
-- PostgreSQL ALTER TABLE RENAME is atomic and non-destructive.
-- Foreign keys and constraints automatically follow the table rename.

-- Rename tables
ALTER TABLE virtual_funds RENAME TO virtual_accounts;
ALTER TABLE transaction_fund_allocations RENAME TO virtual_account_allocations;

-- Rename columns
ALTER TABLE virtual_account_allocations RENAME COLUMN virtual_fund_id TO virtual_account_id;

-- Rename indexes
ALTER INDEX idx_tfa_fund_id RENAME TO idx_vaa_virtual_account_id;
ALTER INDEX idx_tfa_transaction_id RENAME TO idx_vaa_transaction_id;

-- Rename unique constraint
ALTER INDEX transaction_fund_allocations_transaction_id_virtual_fund_id_key
  RENAME TO virtual_account_allocations_tx_id_virtual_account_id_key;

-- Rename category names in production data
UPDATE categories SET name = 'Virtual Account' WHERE name = 'Virtual Fund';
