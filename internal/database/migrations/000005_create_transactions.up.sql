-- =============================================================================
-- Migration 000005: Create Transactions Table
-- =============================================================================
--
-- The core table of the entire application. Every financial event is a transaction.
-- This table has the most columns, foreign keys, indexes, and constraints.
--
-- TRANSACTION TYPES
-- ------------------
-- expense:        money going out (groceries, rent, etc.)
-- income:         money coming in (salary, freelance, etc.)
-- transfer:       money moving between your own accounts (current -> savings)
-- exchange:       currency conversion (EGP -> USD) with exchange_rate
-- loan_out:       you lend money to someone (person_id required)
-- loan_in:        you borrow money from someone (person_id required)
-- loan_repayment: partial or full repayment of a loan
-- =============================================================================

CREATE TYPE transaction_type AS ENUM (
    'expense', 'income', 'transfer', 'exchange',
    'loan_out', 'loan_in', 'loan_repayment'
);

CREATE TABLE transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type transaction_type NOT NULL,

    -- CHECK CONSTRAINT
    -- -----------------
    -- CHECK (amount > 0) ensures no negative or zero amounts are stored.
    -- The sign/direction is determined by the transaction type, not the amount.
    -- This is a database-level validation — even raw SQL inserts are protected.
    --
    -- Laravel: No built-in CHECK constraint. You'd use validation rules in the
    --          Form Request: 'amount' => 'required|numeric|gt:0'
    -- Django:  from django.core.validators import MinValueValidator
    --          amount = models.DecimalField(..., validators=[MinValueValidator(Decimal('0.01'))])
    --          // But Django validators only run in forms/serializers, not at DB level.
    --          // For DB-level: use models.CheckConstraint in Meta.constraints
    --
    -- Docs: https://www.postgresql.org/docs/current/ddl-constraints.html#DDL-CONSTRAINTS-CHECK-CONSTRAINTS
    amount NUMERIC(15, 2) NOT NULL CHECK (amount > 0),

    -- Reuses the currency_type enum defined in migration 000002.
    -- PostgreSQL enums are global to the database, so once created, any table can use them.
    currency currency_type NOT NULL,

    -- PRIMARY ACCOUNT: the account this transaction belongs to.
    -- ON DELETE CASCADE: if the account is deleted, all its transactions are deleted too.
    -- NOT NULL: every transaction MUST have an account.
    --
    -- Laravel: $table->foreignUuid('account_id')->constrained()->cascadeOnDelete();
    -- Django:  account = models.ForeignKey(Account, on_delete=models.CASCADE)
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,

    -- COUNTER ACCOUNT: used for transfers and exchanges.
    -- ON DELETE SET NULL: if the counter account is deleted, this field becomes NULL
    -- (the transaction is preserved but loses the link). This is different from CASCADE.
    -- NULLABLE: only transfers/exchanges have a counter account.
    --
    -- Laravel: $table->foreignUuid('counter_account_id')->nullable()->constrained('accounts')->nullOnDelete();
    -- Django:  counter_account = models.ForeignKey(Account, null=True, on_delete=models.SET_NULL)
    counter_account_id UUID REFERENCES accounts(id) ON DELETE SET NULL,

    -- Category is optional (transfers don't need categories).
    -- ON DELETE SET NULL: keeps the transaction even if the category is deleted.
    category_id UUID REFERENCES categories(id) ON DELETE SET NULL,

    -- DATE vs TIMESTAMPTZ
    -- --------------------
    -- date is DATE (no time component) — just the calendar day of the transaction.
    -- time is TIME (optional) — the clock time, if the user wants to record it.
    -- We separate them because most users only care about the date; time is optional.
    -- CURRENT_DATE returns today's date (no time). Similar to Carbon::today() in Laravel.
    --
    -- Laravel: $table->date('date')->default(DB::raw('CURRENT_DATE'));
    -- Django:  date = models.DateField(default=date.today)
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    time TIME,

    note TEXT,

    -- TEXT[] — array of tags for flexible categorization beyond the single category.
    -- Example: ['recurring', 'essential', 'shared']
    -- Query: SELECT * FROM transactions WHERE 'essential' = ANY(tags);
    tags TEXT[] DEFAULT '{}',

    -- Exchange-specific fields (only populated for 'exchange' type transactions):
    -- exchange_rate: the rate used (e.g., 30.50 for 1 USD = 30.50 EGP)
    -- counter_amount: the amount in the other currency
    exchange_rate NUMERIC(10, 4),
    counter_amount NUMERIC(15, 2),

    -- Fee tracking: some transfers/exchanges have fees charged to a different account.
    -- Example: bank charges 50 EGP fee for a wire transfer, debited from checking.
    fee_amount NUMERIC(15, 2),
    fee_account_id UUID REFERENCES accounts(id) ON DELETE SET NULL,

    -- Person link for loan transactions.
    -- ON DELETE SET NULL: if the person is deleted, the transaction stays but loses the link.
    person_id UUID REFERENCES persons(id) ON DELETE SET NULL,

    -- SELF-REFERENCING FOREIGN KEY
    -- ------------------------------
    -- A transaction can link to another transaction in the same table.
    -- Used for transfers: the "from" side links to the "to" side, and vice versa.
    -- This creates a pair of linked transactions for double-entry bookkeeping.
    --
    -- Laravel: $table->foreignUuid('linked_transaction_id')->nullable()->constrained('transactions')->nullOnDelete();
    -- Django:  linked_transaction = models.ForeignKey('self', null=True, on_delete=models.SET_NULL)
    --
    -- Docs: https://www.postgresql.org/docs/current/ddl-constraints.html#DDL-CONSTRAINTS-FK
    linked_transaction_id UUID REFERENCES transactions(id) ON DELETE SET NULL,

    -- Legacy building fund column — replaced by virtual_funds (migration 000015),
    -- then dropped entirely in migration 000020.
    is_building_fund BOOLEAN NOT NULL DEFAULT false,

    -- Links to recurring_rules table (created in migration 000009).
    -- Note: no REFERENCES constraint here — it was added without a FK to avoid
    -- circular dependency issues during migration ordering.
    recurring_rule_id UUID,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================================
-- INDEXES
-- =============================================================================
-- Each index is tuned for a specific query pattern in the application.
-- Think of indexes like a book's index — instead of reading every page (full table scan),
-- you look up the topic in the index and jump to the right page.
--
-- Laravel: $table->index('column_name');
-- Django:  class Meta: indexes = [models.Index(fields=['column_name'])]

-- Most common query: "show transactions for this account"
CREATE INDEX idx_transactions_account_id ON transactions (account_id);

-- Date filtering: "show transactions for this month"
CREATE INDEX idx_transactions_date ON transactions (date);

-- Category filtering: "show all grocery transactions"
CREATE INDEX idx_transactions_category_id ON transactions (category_id);

-- Type filtering: "show all expenses" or "show all transfers"
CREATE INDEX idx_transactions_type ON transactions (type);

-- Person filtering: "show all transactions with Ahmed"
CREATE INDEX idx_transactions_person_id ON transactions (person_id);

-- Finding linked transaction pairs (transfers/exchanges)
CREATE INDEX idx_transactions_linked ON transactions (linked_transaction_id);

-- PARTIAL INDEX (WHERE clause on an index)
-- ------------------------------------------
-- This index ONLY includes rows where is_building_fund = true.
-- It's much smaller than a full index because most transactions are NOT building fund.
-- PostgreSQL uses it when the query has WHERE is_building_fund = true.
--
-- Laravel: No built-in partial index support. You'd use raw DB::statement().
-- Django:  models.Index(fields=['is_building_fund'], condition=Q(is_building_fund=True))
--
-- Docs: https://www.postgresql.org/docs/current/indexes-partial.html
CREATE INDEX idx_transactions_building_fund ON transactions (is_building_fund) WHERE is_building_fund = true;
