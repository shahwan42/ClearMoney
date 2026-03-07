-- Investment portfolio tracking.
-- Each row is a fund holding on a platform like Thndr.
-- Units * last_unit_price = last_valuation (computed on read, not stored).
CREATE TABLE IF NOT EXISTS investments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform VARCHAR(100) NOT NULL DEFAULT 'Thndr',
    fund_name VARCHAR(100) NOT NULL,
    units NUMERIC(15,4) NOT NULL DEFAULT 0,
    last_unit_price NUMERIC(15,4) NOT NULL DEFAULT 0,
    currency VARCHAR(3) NOT NULL DEFAULT 'EGP',
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
