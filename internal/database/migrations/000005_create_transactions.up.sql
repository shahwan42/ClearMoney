CREATE TYPE transaction_type AS ENUM (
    'expense', 'income', 'transfer', 'exchange',
    'loan_out', 'loan_in', 'loan_repayment'
);

CREATE TABLE transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type transaction_type NOT NULL,
    amount NUMERIC(15, 2) NOT NULL CHECK (amount > 0),
    currency currency_type NOT NULL,
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    counter_account_id UUID REFERENCES accounts(id) ON DELETE SET NULL,
    category_id UUID REFERENCES categories(id) ON DELETE SET NULL,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    time TIME,
    note TEXT,
    tags TEXT[] DEFAULT '{}',
    exchange_rate NUMERIC(10, 4),
    counter_amount NUMERIC(15, 2),
    fee_amount NUMERIC(15, 2),
    fee_account_id UUID REFERENCES accounts(id) ON DELETE SET NULL,
    person_id UUID REFERENCES persons(id) ON DELETE SET NULL,
    linked_transaction_id UUID REFERENCES transactions(id) ON DELETE SET NULL,
    is_building_fund BOOLEAN NOT NULL DEFAULT false,
    recurring_rule_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_transactions_account_id ON transactions (account_id);
CREATE INDEX idx_transactions_date ON transactions (date);
CREATE INDEX idx_transactions_category_id ON transactions (category_id);
CREATE INDEX idx_transactions_type ON transactions (type);
CREATE INDEX idx_transactions_person_id ON transactions (person_id);
CREATE INDEX idx_transactions_linked ON transactions (linked_transaction_id);
CREATE INDEX idx_transactions_building_fund ON transactions (is_building_fund) WHERE is_building_fund = true;
