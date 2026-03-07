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
      type: opts.type || 'checking',
      currency: opts.currency || 'EGP',
      initial_balance: opts.initial_balance || 0,
      credit_limit: opts.credit_limit,
    },
  });
  const body = await resp.json();
  return body.id;
}

/**
 * Seed common test data: an institution with a checking account.
 * Returns { institutionId, accountId }.
 */
export async function seedBasicData(page: Page): Promise<{ institutionId: string; accountId: string }> {
  const institutionId = await createInstitution(page, 'Test Bank');
  const accountId = await createAccount(page, {
    name: 'Checking',
    institution_id: institutionId,
    initial_balance: 10000,
  });
  return { institutionId, accountId };
}
