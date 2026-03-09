-- TASK-061: Virtual Funds — replaces the hardcoded is_building_fund flag
-- with a flexible system of user-defined sub-accounts (savings goals).
--
-- Think of virtual funds like "buckets" or "envelopes" in envelope budgeting.
-- Each fund has a name, optional target amount, and tracks its balance
-- through transaction allocations.

CREATE TABLE IF NOT EXISTS virtual_funds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    target_amount NUMERIC(15,2),           -- optional savings goal (NULL = no target)
    current_balance NUMERIC(15,2) NOT NULL DEFAULT 0,
    icon VARCHAR(10) DEFAULT '',           -- emoji or short icon code
    color VARCHAR(20) DEFAULT '#0d9488',   -- CSS color for UI
    is_archived BOOLEAN NOT NULL DEFAULT false,
    display_order INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Links transactions to virtual funds. A transaction can be split
-- across multiple funds (partial allocations).
CREATE TABLE IF NOT EXISTS transaction_fund_allocations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id UUID NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    virtual_fund_id UUID NOT NULL REFERENCES virtual_funds(id) ON DELETE CASCADE,
    amount NUMERIC(15,2) NOT NULL,   -- positive = contribution, negative = withdrawal
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(transaction_id, virtual_fund_id)
);

CREATE INDEX idx_tfa_fund_id ON transaction_fund_allocations (virtual_fund_id);
CREATE INDEX idx_tfa_transaction_id ON transaction_fund_allocations (transaction_id);

-- Data migration: create "Building Fund" virtual fund and migrate existing
-- is_building_fund transactions to the new allocations table.
DO $$
DECLARE
    fund_id UUID;
    fund_balance NUMERIC(15,2);
BEGIN
    -- Only migrate if there are building fund transactions
    IF EXISTS (SELECT 1 FROM transactions WHERE is_building_fund = true) THEN
        -- Calculate current building fund balance
        SELECT COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE -amount END), 0)
        INTO fund_balance
        FROM transactions WHERE is_building_fund = true;

        -- Create the Building Fund virtual fund
        INSERT INTO virtual_funds (name, current_balance, icon, color, display_order)
        VALUES ('Building Fund', fund_balance, '', '#d97706', 1)
        RETURNING id INTO fund_id;

        -- Migrate all building fund transactions to allocations
        INSERT INTO transaction_fund_allocations (transaction_id, virtual_fund_id, amount)
        SELECT id, fund_id,
            CASE WHEN type = 'income' THEN amount ELSE -amount END
        FROM transactions
        WHERE is_building_fund = true;
    END IF;
END $$;
