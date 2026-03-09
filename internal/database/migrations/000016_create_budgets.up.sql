-- =============================================================================
-- Migration 000016: Create Budgets Table
-- =============================================================================
--
-- TASK-064: Monthly spending limits per category.
--
-- Each budget row defines: "For category X in currency Y, don't spend more than Z per month."
-- The service layer computes actual spending by querying the transactions table
-- and comparing it to monthly_limit. The budget itself doesn't store "spent so far" —
-- that's computed on-the-fly (or from the materialized view mv_monthly_category_totals).
--
-- STATUS THRESHOLDS (computed in Go, not stored):
--   Green:  spent < 80% of limit
--   Amber:  spent >= 80% and < 100% of limit (warning)
--   Red:    spent >= 100% of limit (over budget)
--
-- Laravel equivalent model:
--   class Budget extends Model {
--       public function category() { return $this->belongsTo(Category::class); }
--       public function getPercentUsedAttribute() {
--           $spent = Transaction::where('category_id', $this->category_id)
--               ->whereMonth('date', now()->month)->sum('amount');
--           return ($spent / $this->monthly_limit) * 100;
--       }
--   }
--
-- Django equivalent:
--   class Budget(models.Model):
--       category = models.ForeignKey(Category, on_delete=models.CASCADE)
--       monthly_limit = models.DecimalField(max_digits=15, decimal_places=2)
--       currency = models.CharField(max_length=3, default='EGP')
--       @property
--       def percent_used(self):
--           spent = Transaction.objects.filter(
--               category=self.category, date__month=now().month
--           ).aggregate(Sum('amount'))['amount__sum'] or 0
--           return (spent / self.monthly_limit) * 100
-- =============================================================================

-- TASK-064: Budgets — monthly spending limits per category.
--
-- Each budget sets a monthly cap for a specific category + currency combo.
-- The service layer joins budgets with actual spending to compute remaining
-- amounts and percentage used.

CREATE TABLE IF NOT EXISTS budgets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- ON DELETE CASCADE: if a category is deleted, its budget is deleted too.
    -- Makes sense because a budget without a category is meaningless.
    category_id UUID NOT NULL REFERENCES categories(id) ON DELETE CASCADE,

    monthly_limit NUMERIC(15,2) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'EGP',
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- UNIQUE CONSTRAINT on (category_id, currency)
    -- ------------------------------------------------
    -- Ensures only ONE budget per category per currency.
    -- You can have a "Food" budget in EGP AND a "Food" budget in USD,
    -- but NOT two "Food" budgets both in EGP.
    --
    -- This is a COMPOSITE UNIQUE constraint (multiple columns together must be unique).
    -- The database enforces this — INSERT or UPDATE that violates it will fail.
    --
    -- Also enables UPSERT:
    --   INSERT INTO budgets (category_id, currency, monthly_limit)
    --   VALUES (?, 'EGP', 5000)
    --   ON CONFLICT (category_id, currency) DO UPDATE SET monthly_limit = EXCLUDED.monthly_limit;
    --
    -- Laravel: $table->unique(['category_id', 'currency']);
    -- Django:  class Meta: unique_together = [['category_id', 'currency']]
    --          // Or: constraints = [models.UniqueConstraint(fields=['category_id','currency'], name='...')]
    --
    -- Docs: https://www.postgresql.org/docs/current/ddl-constraints.html#DDL-CONSTRAINTS-UNIQUE-CONSTRAINTS
    UNIQUE(category_id, currency)
);
