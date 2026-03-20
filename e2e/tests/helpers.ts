import { type Page, expect } from '@playwright/test';
import { execSync } from 'child_process';
import { randomBytes } from 'crypto';

export const TEST_EMAIL = 'test@clearmoney.local';

/**
 * Get the database URL from environment or use the local dev default.
 */
function getDbUrl(): string {
  return process.env.DATABASE_URL || 'postgres://clearmoney:clearmoney@localhost:5433/clearmoney';
}

/**
 * Run a SQL command against the database via psql. Returns the first line of output trimmed.
 * Uses -t (tuples only) and -A (unaligned) to get raw values without headers.
 */
export function runSQL(sql: string): string {
  const dbUrl = getDbUrl();
  const output = execSync(`psql "${dbUrl}" -t -A -c "${sql.replace(/\n/g, ' ')}"`, {
    stdio: ['pipe', 'pipe', 'pipe'],
    encoding: 'utf-8',
  });
  // psql -t -A can include extra lines (e.g., "INSERT 0 1"), take only the first non-empty line
  return output.split('\n').filter(line => line.trim() !== '')[0]?.trim() || '';
}

/**
 * Reset the database by truncating all application tables.
 * Creates a test user and seeds system categories.
 * Returns the test user's UUID.
 */
export async function resetDatabase(): Promise<string> {
  const dbUrl = getDbUrl();
  const truncateSql = `
    TRUNCATE TABLE budgets RESTART IDENTITY CASCADE;
    TRUNCATE TABLE virtual_account_allocations RESTART IDENTITY CASCADE;
    TRUNCATE TABLE virtual_accounts RESTART IDENTITY CASCADE;
    TRUNCATE TABLE account_snapshots RESTART IDENTITY CASCADE;
    TRUNCATE TABLE daily_snapshots RESTART IDENTITY CASCADE;
    TRUNCATE TABLE transactions RESTART IDENTITY CASCADE;
    TRUNCATE TABLE accounts RESTART IDENTITY CASCADE;
    TRUNCATE TABLE institutions RESTART IDENTITY CASCADE;
    TRUNCATE TABLE categories RESTART IDENTITY CASCADE;
    TRUNCATE TABLE persons RESTART IDENTITY CASCADE;
    TRUNCATE TABLE exchange_rate_log RESTART IDENTITY CASCADE;
    TRUNCATE TABLE recurring_rules RESTART IDENTITY CASCADE;
    TRUNCATE TABLE investments RESTART IDENTITY CASCADE;
    TRUNCATE TABLE installment_plans RESTART IDENTITY CASCADE;
    TRUNCATE TABLE sessions RESTART IDENTITY CASCADE;
    TRUNCATE TABLE auth_tokens RESTART IDENTITY CASCADE;
    TRUNCATE TABLE users RESTART IDENTITY CASCADE;
    TRUNCATE TABLE user_config RESTART IDENTITY CASCADE;
  `;
  execSync(`psql "${dbUrl}" -c "${truncateSql.replace(/\n/g, ' ')}"`, { stdio: 'pipe' });

  // Create a test user and get their UUID
  const userId = runSQL(
    `INSERT INTO users (email) VALUES ('${TEST_EMAIL}') RETURNING id`,
  );

  // Re-seed system categories for this user (migration 000007 only runs once,
  // so truncating the categories table removes them permanently unless we re-insert).
  const seedSql = `
    INSERT INTO categories (user_id, name, type, icon, is_system, display_order) VALUES
      ('${userId}', 'Household',        'expense', '🏠', true, 1),
      ('${userId}', 'Food & Groceries', 'expense', '🛒', true, 2),
      ('${userId}', 'Transport',        'expense', '🚗', true, 3),
      ('${userId}', 'Health',           'expense', '🏥', true, 4),
      ('${userId}', 'Education',        'expense', '📚', true, 5),
      ('${userId}', 'Mobile',           'expense', '📱', true, 6),
      ('${userId}', 'Electricity',      'expense', '⚡', true, 7),
      ('${userId}', 'Gas',              'expense', '🔥', true, 8),
      ('${userId}', 'Internet',         'expense', '🌐', true, 9),
      ('${userId}', 'Gifts',            'expense', '🎁', true, 10),
      ('${userId}', 'Entertainment',    'expense', '🎬', true, 11),
      ('${userId}', 'Shopping',         'expense', '🛍️', true, 12),
      ('${userId}', 'Subscriptions',    'expense', '📺', true, 13),
      ('${userId}', 'Virtual Account',  'expense', '🏦', true, 14),
      ('${userId}', 'Insurance',        'expense', '🛡️', true, 15),
      ('${userId}', 'Fees & Charges',   'expense', '💳', true, 16),
      ('${userId}', 'Debt Payment',     'expense', '💰', true, 17),
      ('${userId}', 'Other',            'expense', '🔖', true, 18),
      ('${userId}', 'Salary',                    'income', '💵', true, 1),
      ('${userId}', 'Freelance',                 'income', '💻', true, 2),
      ('${userId}', 'Investment Returns',        'income', '📈', true, 3),
      ('${userId}', 'Refund',                    'income', '🔄', true, 4),
      ('${userId}', 'Virtual Account',           'income', '🏦', true, 5),
      ('${userId}', 'Loan Repayment Received',   'income', '🤝', true, 6),
      ('${userId}', 'Other',                     'income', '💎', true, 7)
    ON CONFLICT (name, type, user_id) DO NOTHING;
  `;
  execSync(`psql "${dbUrl}" -c "${seedSql.replace(/\n/g, ' ')}"`, { stdio: 'pipe' });

  return userId;
}

/**
 * Create a DB session for the test user and set the cookie on the browser context.
 * Call resetDatabase() first to ensure the test user exists.
 */
export async function ensureAuth(page: Page): Promise<void> {
  const userId = runSQL(
    `SELECT id FROM users WHERE LOWER(email) = LOWER('${TEST_EMAIL}') LIMIT 1`,
  );

  if (!userId) {
    throw new Error('Test user not found — call resetDatabase() first.');
  }

  // Create a session token directly in the DB (bypasses magic link flow)
  const token = randomBytes(32).toString('base64url');
  runSQL(
    `INSERT INTO sessions (user_id, token, expires_at) VALUES ('${userId}', '${token}', NOW() + INTERVAL '30 days')`,
  );

  // Set the session cookie on the browser context (no HTTP request needed)
  await page.context().addCookies([{
    name: 'clearmoney_session',
    value: token,
    domain: 'localhost',
    path: '/',
    httpOnly: true,
    sameSite: 'Lax',
  }]);
}

/**
 * Create an institution via the API.
 */
export async function createInstitution(page: Page, name: string, type = 'bank'): Promise<string> {
  const resp = await page.request.post('/api/institutions', {
    data: { name, type },
  });
  const body = await resp.json();
  return body.id;
}

/**
 * Create an account via the API.
 */
export async function createAccount(
  page: Page,
  opts: {
    name: string;
    institution_id: string;
    type?: string;
    currency?: string;
    initial_balance?: number;
    credit_limit?: number;
  },
): Promise<string> {
  const resp = await page.request.post('/api/accounts', {
    data: {
      name: opts.name,
      institution_id: opts.institution_id,
      type: opts.type || 'current',
      currency: opts.currency || 'EGP',
      initial_balance: opts.initial_balance || 0,
      credit_limit: opts.credit_limit,
    },
  });
  const body = await resp.json();
  return body.id;
}

/**
 * Seed common test data: an institution with a current account.
 * Returns { institutionId, accountId }.
 */
export async function seedBasicData(page: Page): Promise<{ institutionId: string; accountId: string }> {
  const institutionId = await createInstitution(page, 'Test Bank');
  const accountId = await createAccount(page, {
    name: 'Current',
    institution_id: institutionId,
    initial_balance: 10000,
  });
  return { institutionId, accountId };
}

/**
 * Insert a magic link auth token directly in the DB for testing the verify flow.
 * Returns the token string to use with /auth/verify?token=xxx.
 */
export function createAuthToken(email: string, purpose = 'login'): string {
  const token = randomBytes(32).toString('base64url');
  runSQL(
    `INSERT INTO auth_tokens (email, token, purpose, expires_at) VALUES (LOWER('${email}'), '${token}', '${purpose}', NOW() + INTERVAL '15 minutes')`,
  );
  return token;
}

/**
 * Create a transaction via the Go JSON API.
 * Returns the transaction ID.
 */
export async function createTransaction(
  page: Page,
  opts: {
    account_id: string;
    category_id: string;
    amount: number;
    type: 'expense' | 'income';
    currency?: string;
    note?: string;
    date?: string;
  },
): Promise<string> {
  const dateStr = opts.date || new Date().toISOString().split('T')[0];

  const data: Record<string, unknown> = {
    account_id: opts.account_id,
    category_id: opts.category_id,
    amount: opts.amount,
    type: opts.type,
    currency: opts.currency || 'EGP',
    date: dateStr,
  };
  if (opts.note) data.note = opts.note;

  const resp = await page.request.post('/api/transactions', { data });
  const body = await resp.json();
  return body.transaction.id;
}

/**
 * Get the first category ID of a given type (expense or income) via SQL.
 * Requires categories to be seeded (resetDatabase does this).
 */
export function getCategoryId(type: 'expense' | 'income', userId: string): string {
  return runSQL(
    `SELECT id FROM categories WHERE user_id = '${userId}' AND type = '${type}' LIMIT 1`,
  );
}

/**
 * Create an expired session cookie value in the DB.
 * Used to test that Django rejects expired sessions.
 */
export function createExpiredSession(userId: string): string {
  const token = randomBytes(32).toString('base64url');
  runSQL(
    `INSERT INTO sessions (user_id, token, expires_at) VALUES ('${userId}', '${token}', NOW() - INTERVAL '1 day')`,
  );
  return token;
}
