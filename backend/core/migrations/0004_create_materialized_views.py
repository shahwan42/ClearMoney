"""Create materialized views for reports and streak tracking.

These views exist in production (from Go era) but are not created by Django
migrations. On production, the CREATE IF NOT EXISTS is a no-op. On fresh
test DBs, this creates the views.

Views are created WITH NO DATA — the refresh_views management command
populates them on startup.
"""

from django.db import migrations

CREATE_VIEWS_SQL = """
-- Monthly category totals: powers reports page (spending by category)
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_monthly_category_totals AS
SELECT
    user_id,
    (date_trunc('month', date::timestamp with time zone))::date AS month,
    category_id,
    type,
    currency,
    account_id,
    SUM(amount) AS total_amount,
    COUNT(*) AS tx_count
FROM transactions
WHERE category_id IS NOT NULL
GROUP BY user_id, date_trunc('month', date::timestamp with time zone),
         category_id, type, currency, account_id
WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_monthly_cat_uniq
    ON mv_monthly_category_totals (user_id, month, category_id, type, currency, account_id);

-- Daily transaction counts: powers streak tracker
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_daily_tx_counts AS
SELECT
    user_id,
    date AS tx_date,
    COUNT(*) AS tx_count
FROM transactions
GROUP BY user_id, date
WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_daily_tx_date
    ON mv_daily_tx_counts (user_id, tx_date);
"""

DROP_VIEWS_SQL = """
DROP MATERIALIZED VIEW IF EXISTS mv_daily_tx_counts;
DROP MATERIALIZED VIEW IF EXISTS mv_monthly_category_totals;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0003_add_db_defaults_align_columns"),
    ]

    operations = [
        migrations.RunSQL(sql=CREATE_VIEWS_SQL, reverse_sql=DROP_VIEWS_SQL),
    ]
