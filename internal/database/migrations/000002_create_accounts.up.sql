CREATE TYPE account_type AS ENUM ('checking', 'savings', 'current', 'prepaid', 'credit_card', 'credit_limit');
CREATE TYPE currency_type AS ENUM ('EGP', 'USD');

CREATE TABLE accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    institution_id UUID NOT NULL REFERENCES institutions(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    type account_type NOT NULL,
    currency currency_type NOT NULL DEFAULT 'EGP',
    current_balance NUMERIC(15, 2) NOT NULL DEFAULT 0,
    initial_balance NUMERIC(15, 2) NOT NULL DEFAULT 0,
    credit_limit NUMERIC(15, 2),
    is_dormant BOOLEAN NOT NULL DEFAULT false,
    role_tags TEXT[] DEFAULT '{}',
    display_order INTEGER NOT NULL DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_accounts_institution_id ON accounts (institution_id);
CREATE INDEX idx_accounts_type ON accounts (type);
CREATE INDEX idx_accounts_currency ON accounts (currency);
CREATE INDEX idx_accounts_display_order ON accounts (display_order);
