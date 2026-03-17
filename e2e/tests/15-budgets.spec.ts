import { test, expect } from '@playwright/test';
import { resetDatabase, ensureAuth, createInstitution, createAccount } from './helpers';

test.describe('Budgets', () => {
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

  test('budgets page shows empty state', async ({ page }) => {
    await page.goto('/budgets');
    await expect(page.locator('h2:has-text("Budgets")')).toBeVisible();
    await expect(page.locator('main')).toContainText('No budgets set');
  });

  test('create budget with category and amount', async ({ page }) => {
    await page.goto('/budgets');

    await page.selectOption('select[name="category_id"]', { index: 1 }); // first category
    await page.fill('input[name="monthly_limit"]', '5000');
    await page.click('button:has-text("Create Budget")');

    await page.waitForURL('/budgets');
    // Budget should appear with its category name and limit
    await expect(page.locator('main')).toContainText('5,000');
    await expect(page.locator('main')).toContainText('remaining');
  });

  test('budget shows progress bar container', async ({ page }) => {
    await page.goto('/budgets');
    // The outer progress bar track should be visible
    await expect(page.locator('.bg-gray-100.rounded-full').first()).toBeVisible();
  });

  test('delete budget', async ({ page }) => {
    await page.goto('/budgets');
    // Delete button is a submit button inside a form
    await page.locator('form[action*="/budgets/"] button:has-text("Delete")').first().click();
    await page.waitForURL('/budgets');

    await expect(page.locator('main')).toContainText('No budgets set');
  });
});
