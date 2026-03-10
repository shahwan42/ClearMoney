import { test, expect } from '@playwright/test';
import { resetDatabase, ensureAuth, createInstitution, createAccount } from './helpers';

test.describe('Recurring Rules (TASK-041)', () => {
  test.beforeAll(async ({ browser }) => {
    await resetDatabase();
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    await ensureAuth(page);

    const instId = await createInstitution(page, 'HSBC');
    await createAccount(page, { name: 'Checking', institution_id: instId, type: 'current', currency: 'EGP', initial_balance: 50000 });

    await ctx.close();
  });

  test.beforeEach(async ({ page }) => {
    await ensureAuth(page);
  });

  test('recurring page loads', async ({ page }) => {
    await page.goto('/recurring');
    await expect(page.locator('h2:has-text("Recurring Transactions")')).toBeVisible();
  });

  test('create recurring rule', async ({ page }) => {
    await page.goto('/recurring');

    await page.fill('input[name="amount"]', '500');
    await page.selectOption('select[name="account_id"]', { label: 'Checking (EGP)' });
    await page.fill('input[name="note"]', 'Monthly insurance');
    await page.selectOption('select[name="frequency"]', 'monthly');

    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    await page.fill('input[name="next_due_date"]', tomorrow.toISOString().split('T')[0]);

    await page.click('button:has-text("Create Rule")');
    await expect(page.locator('#recurring-list')).toContainText('Monthly insurance');
  });

  test('delete recurring rule', async ({ page }) => {
    await page.goto('/recurring');
    await expect(page.locator('#recurring-list')).toContainText('Monthly insurance');

    page.on('dialog', dialog => dialog.accept());
    await page.locator('#recurring-list button:has-text("Del")').first().click();

    await expect(page.locator('#recurring-list')).not.toContainText('Monthly insurance');
  });
});
