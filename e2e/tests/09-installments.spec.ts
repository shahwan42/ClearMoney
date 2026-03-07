import { test, expect } from '@playwright/test';
import { resetDatabase, ensureAuth, createInstitution, createAccount } from './helpers';

test.describe('Installments (TASK-043)', () => {
  test.beforeAll(async ({ browser }) => {
    await resetDatabase();
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    await ensureAuth(page);

    const instId = await createInstitution(page, 'HSBC');
    await createAccount(page, { name: 'Credit Card', institution_id: instId, type: 'credit_card', currency: 'EGP', credit_limit: 200000 });

    await ctx.close();
  });

  test.beforeEach(async ({ page }) => {
    await ensureAuth(page);
  });

  test('installments page shows empty state', async ({ page }) => {
    await page.goto('/installments');
    await expect(page.locator('h2:has-text("Installment Plans")')).toBeVisible();
    await expect(page.locator('main')).toContainText('No installment plans yet');
  });

  test('create installment plan', async ({ page }) => {
    await page.goto('/installments');
    await page.fill('input[name="description"]', 'iPhone 16 Pro');
    await page.fill('input[name="total_amount"]', '60000');
    await page.fill('input[name="num_installments"]', '12');
    // Account dropdown uses just the name (no currency suffix)
    await page.selectOption('select[name="account_id"]', { label: 'Credit Card' });

    const today = new Date().toISOString().split('T')[0];
    await page.fill('input[name="start_date"]', today);
    await page.click('button:has-text("Create Plan")');

    await page.waitForURL('/installments');
    await expect(page.locator('main')).toContainText('iPhone 16 Pro');
    await expect(page.locator('main')).toContainText('5,000');
  });

  test('record installment payment', async ({ page }) => {
    await page.goto('/installments');
    page.on('dialog', dialog => dialog.accept());
    await page.locator('button:has-text("Record Payment")').first().click();

    await page.waitForURL('/installments');
    // Should show 1/12 paid
    await expect(page.locator('main')).toContainText('1/12');
  });

  test('delete installment plan', async ({ page }) => {
    await page.goto('/installments');
    page.on('dialog', dialog => dialog.accept());
    await page.locator('button:has-text("Del")').first().click();

    await page.waitForURL('/installments');
    await expect(page.locator('main')).toContainText('No installment plans yet');
  });
});
