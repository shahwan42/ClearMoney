import { test, expect } from '@playwright/test';
import { resetDatabase, ensureAuth, createInstitution, createAccount } from './helpers';

test.describe('Dashboard (TASK-016, TASK-028, TASK-035, TASK-036)', () => {
  test.beforeAll(async ({ browser }) => {
    await resetDatabase();
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    await ensureAuth(page);

    // Create institution + accounts for dashboard display
    const instId = await createInstitution(page, 'HSBC');
    await createAccount(page, { name: 'Checking', institution_id: instId, type: 'checking', currency: 'EGP', initial_balance: 50000 });
    await createAccount(page, { name: 'Credit Card', institution_id: instId, type: 'credit_card', currency: 'EGP', credit_limit: 200000 });

    await ctx.close();
  });

  test.beforeEach(async ({ page }) => {
    await ensureAuth(page);
  });

  test('shows net worth section', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('text=Net Worth')).toBeVisible();
    // Should show EGP 50,000 from checking account
    await expect(page.locator('main')).toContainText('50,000');
  });

  test('shows summary cards', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('#summary-cards')).toBeVisible();
    await expect(page.locator('main')).toContainText('Liquid Cash');
    await expect(page.locator('main')).toContainText('Credit Used');
    await expect(page.locator('main')).toContainText('Credit Available');
  });

  test('shows institution accounts section', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('text=HSBC')).toBeVisible();
    await expect(page.getByRole('link', { name: 'Manage' }).first()).toBeVisible();
  });

  test('shows recent transactions section with empty state', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('text=Recent Transactions')).toBeVisible();
    await expect(page.locator('#recent-transactions')).toContainText('No transactions yet');
  });

  test('recent transactions update after adding a transaction', async ({ page }) => {
    // Create a transaction via the form
    await page.goto('/transactions/new');
    await page.fill('input[name="amount"]', '250');
    await page.selectOption('select[name="account_id"]', { label: 'Checking (EGP)' });
    await page.fill('input[name="note"]', 'Dashboard test tx');
    await page.click('button:has-text("Save Transaction")');
    await expect(page.locator('#transaction-result')).toContainText('Transaction saved!');

    // Go to dashboard and verify
    await page.goto('/');
    await expect(page.locator('#recent-transactions')).toContainText('Dashboard test tx');
  });
});
