CREATE TABLE exchange_rate_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date DATE NOT NULL,
    rate NUMERIC(10, 4) NOT NULL,
    source TEXT,
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_exchange_rate_log_date ON exchange_rate_log (date);
