"""Drop Go-era PostgreSQL enum types and convert columns to varchar.

Production has 5 enum types (account_type, currency_type, transaction_type,
institution_type, category_type) from the Go migration era. Django uses
CharField (varchar) for these columns. This migration converts production's
enum columns to varchar and drops the enum types.

On a fresh DB (tests), columns are already varchar and types don't exist,
so all operations are conditional no-ops.
"""

from django.db import migrations

DROP_ENUMS_SQL = """
-- Convert enum columns to varchar (conditional: only if column is USER-DEFINED)
DO $$
BEGIN
    -- accounts.type: account_type → varchar(20)
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'accounts' AND column_name = 'type'
        AND data_type = 'USER-DEFINED'
    ) THEN
        ALTER TABLE accounts ALTER COLUMN type TYPE varchar(20) USING type::text;
    END IF;

    -- accounts.currency: currency_type → varchar(3)
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'accounts' AND column_name = 'currency'
        AND data_type = 'USER-DEFINED'
    ) THEN
        ALTER TABLE accounts ALTER COLUMN currency TYPE varchar(3) USING currency::text;
    END IF;

    -- transactions.type: transaction_type → varchar(30)
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'transactions' AND column_name = 'type'
        AND data_type = 'USER-DEFINED'
    ) THEN
        ALTER TABLE transactions ALTER COLUMN type TYPE varchar(30) USING type::text;
    END IF;

    -- transactions.currency: currency_type → varchar(3)
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'transactions' AND column_name = 'currency'
        AND data_type = 'USER-DEFINED'
    ) THEN
        ALTER TABLE transactions ALTER COLUMN currency TYPE varchar(3) USING currency::text;
    END IF;

    -- institutions.type: institution_type → varchar(20)
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'institutions' AND column_name = 'type'
        AND data_type = 'USER-DEFINED'
    ) THEN
        ALTER TABLE institutions ALTER COLUMN type TYPE varchar(20) USING type::text;
    END IF;

    -- categories.type: category_type → varchar(20)
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'categories' AND column_name = 'type'
        AND data_type = 'USER-DEFINED'
    ) THEN
        ALTER TABLE categories ALTER COLUMN type TYPE varchar(20) USING type::text;
    END IF;
END $$;

-- Drop enum types (safe: IF EXISTS handles fresh DBs)
DROP TYPE IF EXISTS account_type;
DROP TYPE IF EXISTS currency_type;
DROP TYPE IF EXISTS transaction_type;
DROP TYPE IF EXISTS institution_type;
DROP TYPE IF EXISTS category_type;
"""

# Reverse: recreate enum types and convert back (for rollback safety)
REVERSE_SQL = migrations.RunSQL.noop


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(sql=DROP_ENUMS_SQL, reverse_sql=REVERSE_SQL),
    ]
