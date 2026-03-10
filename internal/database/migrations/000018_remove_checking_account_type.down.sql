-- Restore 'checking' to the account_type enum
CREATE TYPE account_type_new AS ENUM ('checking', 'savings', 'current', 'prepaid', 'credit_card', 'credit_limit');

ALTER TABLE accounts
    ALTER COLUMN type TYPE account_type_new USING type::text::account_type_new;

DROP TYPE account_type;
ALTER TYPE account_type_new RENAME TO account_type;
