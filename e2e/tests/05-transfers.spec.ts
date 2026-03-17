import { test, expect } from '@playwright/test';
import { resetDatabase, ensureAuth, createInstitution, createAccount } from './helpers';

test.describe('Transfers & Exchange (TASK-022, TASK-023, TASK-029)', () => {
  test.beforeAll(async ({ browser }) => {
    await resetDatabase();
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    await ensureAuth(page);

    const instId = await createInstitution(page, 'HSBC');
    await createAccount(page, { name: 'Checking', institution_id: instId, type: 'current', currency: 'EGP', initial_balance: 50000 });
    await createAccount(page, { name: 'Savings', institution_id: instId, type: 'savings', currency: 'EGP', initial_balance: 10000 });
    await createAccount(page, { name: 'USD Wallet', institution_id: instId, type: 'current', currency: 'USD', initial_balance: 500 });

    await ctx.close();
  });

  test.beforeEach(async ({ page }) => {
    await ensureAuth(page);
  });

  test('transfer page shows source and destination dropdowns', async ({ page }) => {
    await page.goto('/transfers/new');
    await expect(page.locator('text=Transfer Between Accounts')).toBeVisible();
    await expect(page.locator('select[name="source_account_id"]')).toBeVisible();
    await expect(page.locator('select[name="dest_account_id"]')).toBeVisible();
  });

  test('create transfer between accounts', async ({ page }) => {
    await page.goto('/transfers/new');
    await page.selectOption('select[name="source_account_id"]', { label: 'Checking (EGP)' });
    await page.selectOption('select[name="dest_account_id"]', { label: 'Savings (EGP)' });
    await page.fill('#transfer-amount', '5000');
    await page.click('#transfer-form button:has-text("Transfer")');

    await expect(page.locator('#transfer-result')).toContainText(/transfer|completed|saved/i);
  });

  test('net worth unchanged after transfer', async ({ page }) => {
    await page.goto('/');
    // EGP total: 50000 + 10000 = 60000 (transfer moves within EGP, doesn't change total)
    // Dashboard now shows EGP and USD separately
    await expect(page.locator('main')).toContainText('60,000');
  });

  test('instapay toggle shows fee', async ({ page }) => {
    await page.goto('/transfers/new');
    await page.fill('#transfer-amount', '10000');
    // Click the toggle's visual element (sr-only checkbox)
    await page.locator('#instapay-toggle').click({ force: true });
    await expect(page.locator('#instapay-fee')).toBeVisible();
    // Fee: 10000 * 0.001 = 10
    await expect(page.locator('#instapay-fee-amount')).toContainText('10.00');
  });

  test('exchange page shows form fields', async ({ page }) => {
    await page.goto('/exchange/new');
    await expect(page.locator('text=Currency Exchange')).toBeVisible();
    await expect(page.locator('#exchange-src')).toBeVisible();
    await expect(page.locator('#exchange-dst')).toBeVisible();
    await expect(page.locator('#exchange-amount')).toBeVisible();
    await expect(page.locator('#exchange-rate')).toBeVisible();
  });

  test('create currency exchange', async ({ page }) => {
    await page.goto('/exchange/new');
    await page.selectOption('#exchange-src', { label: 'USD Wallet (USD)' });
    await page.selectOption('#exchange-dst', { label: 'Checking (EGP)' });
    await page.fill('#exchange-amount', '100');
    await page.fill('#exchange-rate', '50');
    await page.fill('#exchange-counter', '5000');
    await page.click('button:has-text("Exchange")');

    await expect(page.locator('#exchange-result')).toContainText(/exchange|completed|saved/i);
  });
});
