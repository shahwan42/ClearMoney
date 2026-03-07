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
