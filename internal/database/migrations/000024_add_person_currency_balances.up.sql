-- Add per-currency balance columns to persons table.
-- Existing net_balance is kept (production safety — no drops) but new code uses per-currency columns.
ALTER TABLE persons ADD COLUMN IF NOT EXISTS net_balance_egp NUMERIC(15,2) NOT NULL DEFAULT 0;
ALTER TABLE persons ADD COLUMN IF NOT EXISTS net_balance_usd NUMERIC(15,2) NOT NULL DEFAULT 0;

-- Migrate existing data: all existing balances assumed EGP
UPDATE persons SET net_balance_egp = net_balance WHERE net_balance != 0;
