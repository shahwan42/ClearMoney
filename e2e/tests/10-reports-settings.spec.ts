import { test, expect } from '@playwright/test';
import { resetDatabase, ensureAuth, createInstitution, createAccount } from './helpers';

test.describe('Reports, Settings, Building Fund, Fawry, Batch (TASK-039, TASK-038, TASK-034, TASK-043, TASK-047)', () => {
  test.beforeAll(async ({ browser }) => {
    await resetDatabase();
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    await ensureAuth(page);

    const instId = await createInstitution(page, 'HSBC');
    await createAccount(page, { name: 'Checking', institution_id: instId, type: 'checking', currency: 'EGP', initial_balance: 50000 });
    await createAccount(page, { name: 'Credit Card', institution_id: instId, type: 'credit_card', currency: 'EGP', credit_limit: 200000 });
    await createAccount(page, { name: 'Fawry', institution_id: instId, type: 'prepaid', currency: 'EGP', initial_balance: 0 });

    await ctx.close();
  });

  test.beforeEach(async ({ page }) => {
    await ensureAuth(page);
  });

  // Reports
  test('reports page loads with month navigation', async ({ page }) => {
    await page.goto('/reports');
    await expect(page.getByRole('heading', { name: /Reports/i }).first()).toBeVisible();
    await expect(page.locator('a:has-text("Prev")').first()).toBeVisible();
    await expect(page.locator('a:has-text("Next")').first()).toBeVisible();
  });

  // Building Fund
  test('building fund page loads', async ({ page }) => {
    await page.goto('/building-fund');
    await expect(page.locator('main')).toContainText(/Building Fund/i);
  });

  test('record building fund collection', async ({ page }) => {
    await page.goto('/building-fund');
    await page.fill('input[name="amount"]', '1000');
    await page.selectOption('select[name="account_id"]', { label: 'Checking (EGP)' });
    await page.fill('input[name="note"]', 'Monthly collection');
    await page.click('button:has-text("Record")');

    await expect(page.locator('#building-fund-result')).toContainText(/saved|success|recorded/i);
  });

  // Fawry Cashout
  test('fawry cashout page loads', async ({ page }) => {
    await page.goto('/fawry-cashout');
    await expect(page.locator('main')).toContainText(/Cash/i);
    await expect(page.locator('select[name="credit_card_id"]')).toBeVisible();
  });

  test('fawry total updates with amount + fee', async ({ page }) => {
    await page.goto('/fawry-cashout');
    await page.fill('input[name="amount"]', '5000');
    await page.fill('#fawry-fee', '50');
    await expect(page.locator('#fawry-total')).toContainText('5050.00');
  });

  // Batch Entry
  test('batch entry page loads', async ({ page }) => {
    await page.goto('/batch-entry');
    await expect(page.locator('main')).toContainText(/Batch/i);
    await expect(page.locator('.batch-row').first()).toBeVisible();
  });

  // Settings
  test('settings page loads with change PIN form', async ({ page }) => {
    await page.goto('/settings');
    await expect(page.getByRole('heading', { name: /Settings/i })).toBeVisible();
    await expect(page.locator('input[name="current_pin"]')).toBeVisible();
    await expect(page.locator('input[name="new_pin"]')).toBeVisible();
  });

  // Exchange rate history
  test('exchange rates page loads', async ({ page }) => {
    await page.goto('/exchange-rates');
    await expect(page.locator('main')).toContainText(/Exchange Rate/i);
  });

  // Export
  test('settings page has export form', async ({ page }) => {
    await page.goto('/settings');
    await expect(page.locator('button:has-text("Download CSV")')).toBeVisible();
  });

  // PIN change — last test since it modifies auth state
  test('change PIN and change back', async ({ page }) => {
    await page.goto('/settings');
    await page.fill('input[name="current_pin"]', '1234');
    await page.fill('input[name="new_pin"]', '5678');
    await page.click('button:has-text("Change PIN")');
    await expect(page.locator('#pin-result')).toContainText(/changed|updated|success/i);

    // Change back
    await page.reload();
    await page.fill('input[name="current_pin"]', '5678');
    await page.fill('input[name="new_pin"]', '1234');
    await page.click('button:has-text("Change PIN")');
    await expect(page.locator('#pin-result')).toContainText(/changed|updated|success/i);
  });
});
