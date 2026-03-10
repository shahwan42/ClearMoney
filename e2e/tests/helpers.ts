import { type Page, expect } from '@playwright/test';

export const TEST_PIN = '1234';

/**
 * Reset the database by truncating all application tables.
 * Runs via psql against the test database.
 */
export async function resetDatabase(): Promise<void> {
  const { execSync } = await import('child_process');
  const dbUrl = 'postgres://clearmoney:clearmoney@localhost:5433/clearmoney';
  const sql = `
    TRUNCATE TABLE budgets RESTART IDENTITY CASCADE;
    TRUNCATE TABLE transaction_fund_allocations RESTART IDENTITY CASCADE;
    TRUNCATE TABLE virtual_funds RESTART IDENTITY CASCADE;
    TRUNCATE TABLE account_snapshots RESTART IDENTITY CASCADE;
    TRUNCATE TABLE daily_snapshots RESTART IDENTITY CASCADE;
    TRUNCATE TABLE transactions RESTART IDENTITY CASCADE;
    TRUNCATE TABLE accounts RESTART IDENTITY CASCADE;
    TRUNCATE TABLE institutions RESTART IDENTITY CASCADE;
    TRUNCATE TABLE categories RESTART IDENTITY CASCADE;
    TRUNCATE TABLE persons RESTART IDENTITY CASCADE;
    TRUNCATE TABLE exchange_rate_log RESTART IDENTITY CASCADE;
    TRUNCATE TABLE user_config RESTART IDENTITY CASCADE;
    TRUNCATE TABLE recurring_rules RESTART IDENTITY CASCADE;
    TRUNCATE TABLE investments RESTART IDENTITY CASCADE;
    TRUNCATE TABLE installment_plans RESTART IDENTITY CASCADE;
  `;
  execSync(`psql "${dbUrl}" -c "${sql.replace(/\n/g, ' ')}"`, { stdio: 'pipe' });

  // Re-seed system categories (migration 000007 only runs once, so truncating
  // the categories table removes them permanently unless we re-insert).
  const seedSql = `
    INSERT INTO categories (name, type, is_system, display_order) VALUES
      ('Household',        'expense', true, 1),
      ('Food & Groceries', 'expense', true, 2),
      ('Transport',        'expense', true, 3),
      ('Health',           'expense', true, 4),
      ('Education',        'expense', true, 5),
      ('Mobile',           'expense', true, 6),
      ('Electricity',      'expense', true, 7),
      ('Gas',              'expense', true, 8),
      ('Internet',         'expense', true, 9),
      ('Gifts',            'expense', true, 10),
      ('Entertainment',    'expense', true, 11),
      ('Shopping',         'expense', true, 12),
      ('Subscriptions',    'expense', true, 13),
      ('Building Fund',    'expense', true, 14),
      ('Insurance',        'expense', true, 15),
      ('Fees & Charges',   'expense', true, 16),
      ('Debt Payment',     'expense', true, 17),
      ('Other',            'expense', true, 18),
      ('Salary',                    'income', true, 1),
      ('Freelance',                 'income', true, 2),
      ('Investment Returns',        'income', true, 3),
      ('Refund',                    'income', true, 4),
      ('Building Fund Collection',  'income', true, 5),
      ('Loan Repayment Received',   'income', true, 6),
      ('Other',                     'income', true, 7)
    ON CONFLICT DO NOTHING;
  `;
  execSync(`psql "${dbUrl}" -c "${seedSql.replace(/\n/g, ' ')}"`, { stdio: 'pipe' });
}

/**
 * Set up the PIN via the /setup page. Must be called on a fresh database.
 */
export async function setupPIN(page: Page, pin = TEST_PIN): Promise<void> {
  await page.goto('/setup');
  await page.fill('input[name="pin"]', pin);
  await page.fill('input[name="confirm_pin"]', pin);
  await page.click('button[type="submit"]');
  // Should redirect to dashboard
  await page.waitForURL('/');
}

/**
 * Log in with the PIN via the /login page.
 */
export async function login(page: Page, pin = TEST_PIN): Promise<void> {
  await page.goto('/login');
  await page.fill('input[name="pin"]', pin);
  await page.click('button[type="submit"]');
  await page.waitForURL('/');
}

/**
 * Ensure the page is authenticated. If redirected to /setup or /login, handle it.
 */
export async function ensureAuth(page: Page): Promise<void> {
  await page.goto('/');
  const url = page.url();
  if (url.includes('/setup')) {
    await setupPIN(page);
  } else if (url.includes('/login')) {
    await login(page);
  }
  // Now we should be on /
  await expect(page).toHaveURL('/');
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
