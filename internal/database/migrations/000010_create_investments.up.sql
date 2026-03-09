-- =============================================================================
-- Migration 000010: Create Investments Table
-- =============================================================================
--
-- Tracks investment fund holdings (e.g., mutual funds on platforms like Thndr).
--
-- COMPUTED VALUES: STORE vs CALCULATE ON READ
-- ---------------------------------------------
-- The investment's current valuation = units * last_unit_price.
-- This value is NOT stored in the database — it's computed on every read:
--   SELECT *, (units * last_unit_price) AS valuation FROM investments;
--
-- Why not store the valuation?
--   - It would be redundant data (violates normalization).
--   - If you update units OR last_unit_price but forget to update valuation,
--     the data becomes inconsistent.
--   - Computing it on read is trivial (just multiplication).
--
-- Compare this to persons.net_balance (migration 000004), which IS stored
-- because computing it requires a SUM across many transactions — expensive.
-- Simple math (multiplication) = compute on read. Complex aggregation = cache it.
--
-- Laravel equivalent:
--   // In the Model, use an accessor:
--   public function getValuationAttribute() {
--       return $this->units * $this->last_unit_price;
--   }
--   // Or append it: protected $appends = ['valuation'];
--
-- Django equivalent:
--   @property
--   def valuation(self):
--       return self.units * self.last_unit_price
--
-- NUMERIC(15,4) — FOUR DECIMAL PLACES
-- --------------------------------------
-- Units and prices use 4 decimal places (not 2 like money columns).
-- Fund units can be fractional (e.g., 3.7521 units) and prices need precision
-- (e.g., 12.3456 EGP per unit). 15,4 = up to 99,999,999,999.9999
--
-- VARCHAR(100) vs TEXT
-- ---------------------
-- Here VARCHAR(100) is used instead of TEXT to set a maximum length.
-- In PostgreSQL, performance is identical — VARCHAR just adds a length check.
-- It's a design choice: TEXT says "no limit"; VARCHAR(100) says "max 100 chars."
--
-- VARCHAR(3) for currency: exactly matches ISO 4217 currency codes (EGP, USD, EUR).
-- Note: this uses VARCHAR instead of the currency_type ENUM (from migration 000002)
-- because investments might support currencies beyond EGP/USD in the future.
-- =============================================================================

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
