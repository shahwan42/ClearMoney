import { test, expect } from '@playwright/test';
import { resetDatabase, ensureAuth, seedBasicData } from './helpers';

test.describe('Transactions (TASK-009 to TASK-015)', () => {
  let accountId: string;

  test.beforeAll(async ({ browser }) => {
    await resetDatabase();
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    await ensureAuth(page);
    const data = await seedBasicData(page);
    accountId = data.accountId;
    await ctx.close();
  });

  test.beforeEach(async ({ page }) => {
    await ensureAuth(page);
  });

  test('transaction form shows account dropdown', async ({ page }) => {
    await page.goto('/transactions/new');
    await expect(page.getByRole('heading', { name: 'New Transaction' })).toBeVisible();
    await expect(page.locator('select[name="account_id"]')).toBeVisible();
    // Account "Checking" should be in dropdown
    await expect(page.locator('select[name="account_id"]')).toContainText('Checking');
  });

  test('create expense transaction', async ({ page }) => {
    await page.goto('/transactions/new');
    // Default is expense type
    await page.fill('input[name="amount"]', '150');
    await page.selectOption('select[name="account_id"]', { label: 'Checking (EGP)' });
    await page.fill('input[name="note"]', 'Groceries');
    await page.click('button:has-text("Save Transaction")');

    // Should show success message with new balance (10000 - 150 = 9850)
    await expect(page.locator('#transaction-result')).toContainText('Transaction saved!');
    await expect(page.locator('#transaction-result')).toContainText('9,850');
  });

  test('create income transaction', async ({ page }) => {
    await page.goto('/transactions/new');
    // Click income radio label
    await page.click('#type-income-label');
    await page.fill('input[name="amount"]', '5000');
    await page.selectOption('select[name="account_id"]', { label: 'Checking (EGP)' });
    await page.fill('input[name="note"]', 'Freelance payment');
    await page.click('button:has-text("Save Transaction")');

    // Balance: 9850 + 5000 = 14850
    await expect(page.locator('#transaction-result')).toContainText('Transaction saved!');
    await expect(page.locator('#transaction-result')).toContainText('14,850');
  });

  test('transactions list shows created transactions', async ({ page }) => {
    await page.goto('/transactions');
    await expect(page.getByRole('heading', { name: 'Transactions' })).toBeVisible();
    // Both transactions should appear
    await expect(page.locator('#transaction-list')).toContainText('Groceries');
    await expect(page.locator('#transaction-list')).toContainText('Freelance payment');
  });

  test('filter transactions by type', async ({ page }) => {
    await page.goto('/transactions');
    // Filter by expense only
    await page.selectOption('select[name="type"]', 'expense');
    // Wait for HTMX reload
    await page.waitForResponse(resp => resp.url().includes('/transactions/list'));
    await expect(page.locator('#transaction-list')).toContainText('Groceries');
    // Income transaction should not be visible
    await expect(page.locator('#transaction-list')).not.toContainText('Freelance payment');
  });

  test('search transactions by note', async ({ page }) => {
    await page.goto('/transactions');
    // Set up response listener before typing (triggers keyup changed delay:300ms)
    const responsePromise = page.waitForResponse(resp => resp.url().includes('/transactions/list'));
    await page.locator('#search-input').pressSequentially('Freelance', { delay: 50 });
    await responsePromise;
    await expect(page.locator('#transaction-list')).toContainText('Freelance payment');
    await expect(page.locator('#transaction-list')).not.toContainText('Groceries');
  });

  test('dashboard shows recent transactions', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('#recent-transactions')).toContainText('Groceries');
    await expect(page.locator('#recent-transactions')).toContainText('Freelance payment');
  });

  test('account balance updates after transactions', async ({ page }) => {
    // Initial: 10000, expense -150, income +5000 = 14850
    await page.goto(`/accounts/${accountId}`);
    await expect(page.locator('text=Current Balance')).toBeVisible();
    await expect(page.locator('main')).toContainText('14,850');
  });

  test('delete transaction and verify list updates', async ({ page }) => {
    await page.goto('/transactions');
    await expect(page.locator('#transaction-list')).toContainText('Groceries');

    // Hover over the Groceries row to reveal the delete button
    const groceryRow = page.locator('[id^="tx-"]', { hasText: 'Groceries' }).first();
    await groceryRow.hover();

    // Click delete and accept confirm dialog
    page.on('dialog', dialog => dialog.accept());
    await groceryRow.locator('button:has-text("Del")').click();

    // Row should be removed
    await expect(page.locator('#transaction-list')).not.toContainText('Groceries');
  });
});
