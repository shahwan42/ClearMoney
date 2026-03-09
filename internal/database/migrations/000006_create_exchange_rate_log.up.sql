-- =============================================================================
-- Migration 000006: Create Exchange Rate Log Table
-- =============================================================================
--
-- APPEND-ONLY LOG PATTERN
-- -------------------------
-- This table records exchange rates over time. It's an "append-only" table:
-- rows are only INSERT-ed, never UPDATE-d or DELETE-d.
--
-- Why append-only?
--   Exchange rates are historical facts. If USD/EGP was 30.50 on Jan 15, that's
--   a permanent record. You never "update" a past rate — you add today's new rate.
--   This pattern is also called an "event log" or "audit trail."
--
-- In Laravel/Django, you might see this pattern in:
--   - Activity logs (spatie/laravel-activitylog)
--   - Django audit trail (django-auditlog)
--   - Event sourcing systems
--
-- NO updated_at COLUMN
-- ----------------------
-- Notice there's no updated_at — because rows are never updated.
-- Only created_at records when the rate was logged.
-- This is intentional and signals to other developers: "don't update these rows."
--
-- source: where the rate came from (e.g., "CBE", "manual", "Google Finance")
-- note: optional context (e.g., "parallel market rate", "official rate")
-- =============================================================================

CREATE TABLE exchange_rate_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date DATE NOT NULL,
    rate NUMERIC(10, 4) NOT NULL,
    source TEXT,
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index on date for range queries: "show rates for the last 30 days"
-- or "find the most recent rate" (ORDER BY date DESC LIMIT 1).
CREATE INDEX idx_exchange_rate_log_date ON exchange_rate_log (date);
