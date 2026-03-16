-- Add exclude_from_net_worth flag to virtual accounts.
-- When true, the virtual account's balance is subtracted from net worth calculations.
-- Use case: money held for others (e.g., building fund) that's in the user's bank account
-- but isn't theirs.
ALTER TABLE virtual_accounts
ADD COLUMN exclude_from_net_worth BOOLEAN NOT NULL DEFAULT false;
