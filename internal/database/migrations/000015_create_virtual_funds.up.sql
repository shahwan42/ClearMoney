-- =============================================================================
-- Migration 000015: Virtual Funds (Envelope Budgeting)
-- =============================================================================
--
-- TASK-061: Replaces the hardcoded is_building_fund boolean flag (from migration
-- 000005) with a flexible system of user-defined virtual funds (savings goals).
--
-- ENVELOPE BUDGETING PATTERN
-- ----------------------------
-- Think of virtual funds like physical envelopes: you divide your money into
-- labeled envelopes (Rent, Emergency Fund, Vacation) and track how much is in each.
-- The money is still in your bank account, but virtually allocated to goals.
--
-- Similar apps: YNAB (You Need A Budget), Goodbudget, Qapital
--
-- Why "virtual"? The money isn't in a separate bank account — it's a logical
-- subdivision of an existing account balance. Think of it as sub-accounts or buckets.
-- =============================================================================

-- TASK-061: Virtual Funds — replaces the hardcoded is_building_fund flag
-- with a flexible system of user-defined sub-accounts (savings goals).
--
-- Think of virtual funds like "buckets" or "envelopes" in envelope budgeting.
-- Each fund has a name, optional target amount, and tracks its balance
-- through transaction allocations.

CREATE TABLE IF NOT EXISTS virtual_funds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,

    -- target_amount is nullable: NULL means "no savings goal" (just tracking).
    -- A non-NULL value (e.g., 50000.00) means "saving toward this target."
    -- The UI shows a progress bar: current_balance / target_amount * 100%.
    --
    -- Laravel: $table->decimal('target_amount', 15, 2)->nullable();
    -- Django:  target_amount = models.DecimalField(..., null=True, blank=True)
    target_amount NUMERIC(15,2),           -- optional savings goal (NULL = no target)

    -- current_balance is a cached aggregate (like persons.net_balance in 000004).
    -- The "true" balance = SUM(amount) from transaction_fund_allocations for this fund.
    -- We cache it here for instant reads on the dashboard.
    current_balance NUMERIC(15,2) NOT NULL DEFAULT 0,

    icon VARCHAR(10) DEFAULT '',           -- emoji or short icon code
    color VARCHAR(20) DEFAULT '#0d9488',   -- CSS color for UI
    is_archived BOOLEAN NOT NULL DEFAULT false,
    display_order INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- JOIN TABLE (Many-to-Many with Extra Data)
-- =============================================================================
-- transaction_fund_allocations links transactions to virtual funds.
-- This is a JOIN TABLE (also called pivot table, junction table, or bridge table).
--
-- A transaction can be split across MULTIPLE funds (partial allocations):
--   e.g., a 5000 EGP income → 3000 to "Emergency Fund" + 2000 to "Vacation Fund"
--
-- And a fund can have MANY transactions allocated to it.
-- This is a classic many-to-many relationship with an extra column (amount).
--
-- Laravel: You'd use a pivot table with extra columns:
--   $table->foreignUuid('transaction_id')->constrained()->cascadeOnDelete();
--   $table->foreignUuid('virtual_fund_id')->constrained()->cascadeOnDelete();
--   $table->decimal('amount', 15, 2);
--   // In the model: $this->belongsToMany(VirtualFund::class)->withPivot('amount');
--
-- Django: You'd use a through model for the M2M relationship:
--   class TransactionFundAllocation(models.Model):
--       transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE)
--       virtual_fund = models.ForeignKey(VirtualFund, on_delete=models.CASCADE)
--       amount = models.DecimalField(max_digits=15, decimal_places=2)
--       class Meta:
--           unique_together = [['transaction', 'virtual_fund']]
--
-- UNIQUE(transaction_id, virtual_fund_id):
--   Prevents allocating the same transaction to the same fund twice.
--   If you need to change the amount, UPDATE the existing row instead of inserting a duplicate.
-- =============================================================================

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

-- =============================================================================
-- DATA MIGRATION with PL/pgSQL (DO $$ ... $$)
-- =============================================================================
-- This is an anonymous PL/pgSQL block — PostgreSQL's procedural language.
-- It's like writing a stored procedure inline, without giving it a name.
--
-- DO $$ ... $$;
--   $$ is a "dollar-quoted" string delimiter (avoids escaping single quotes inside).
--   The block between $$ ... $$ is PL/pgSQL code with variables, IF/THEN, loops, etc.
--
-- This data migration converts old is_building_fund transactions to the new
-- virtual funds system:
--   1. Check if any building fund transactions exist.
--   2. If yes, create a "Building Fund" virtual fund.
--   3. Create allocation records linking those transactions to the new fund.
--
-- Laravel equivalent:
--   // In the migration's up() method:
--   if (DB::table('transactions')->where('is_building_fund', true)->exists()) {
--       $fundId = DB::table('virtual_funds')->insertGetId([...]);
--       $transactions = DB::table('transactions')->where('is_building_fund', true)->get();
--       foreach ($transactions as $tx) {
--           DB::table('transaction_fund_allocations')->insert([...]);
--       }
--   }
--
-- Django equivalent:
--   // In a data migration's forwards function:
--   def forwards(apps, schema_editor):
--       Transaction = apps.get_model('app', 'Transaction')
--       VirtualFund = apps.get_model('app', 'VirtualFund')
--       if Transaction.objects.filter(is_building_fund=True).exists():
--           fund = VirtualFund.objects.create(name='Building Fund', ...)
--           ...
--
-- COALESCE(value, default):
--   Returns the first non-NULL argument. If SUM() returns NULL (no rows), COALESCE
--   converts it to 0. Essential for avoiding NULL in calculations.
--   Laravel: DB::raw('COALESCE(SUM(...), 0)')
--   Django:  from django.db.models.functions import Coalesce; .aggregate(Coalesce(Sum('amount'), 0))
--
-- RETURNING id INTO fund_id:
--   PostgreSQL can return values from INSERT statements. RETURNING id gets the
--   auto-generated UUID, and INTO fund_id stores it in a PL/pgSQL variable.
--   Laravel: $id = DB::table('virtual_funds')->insertGetId([...]);
--   Django:  fund = VirtualFund.objects.create(...)  # fund.id is auto-populated
--
-- INSERT INTO ... SELECT:
--   Combines INSERT with a SELECT query — inserts multiple rows from query results
--   in a single statement. Much faster than inserting one row at a time in a loop.
--   This is a set-based operation (SQL's strength) vs. row-by-row (loop-based).
--
-- Docs: https://www.postgresql.org/docs/current/plpgsql.html
-- =============================================================================

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
