import { test, expect } from '@playwright/test';
import { resetDatabase, ensureAuth, createInstitution, createAccount } from './helpers';

test.describe('Salary Wizard & Quick Entry (TASK-033, TASK-025, TASK-026)', () => {
  test.beforeAll(async ({ browser }) => {
    await resetDatabase();
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    await ensureAuth(page);

    const instId = await createInstitution(page, 'HSBC');
    await createAccount(page, { name: 'USD Salary', institution_id: instId, type: 'current', currency: 'USD', initial_balance: 0 });
    await createAccount(page, { name: 'Main EGP', institution_id: instId, type: 'current', currency: 'EGP', initial_balance: 10000 });
    await createAccount(page, { name: 'Savings', institution_id: instId, type: 'savings', currency: 'EGP', initial_balance: 5000 });

    await ctx.close();
  });

  test.beforeEach(async ({ page }) => {
    await ensureAuth(page);
  });

  // Salary wizard
  test('salary wizard step 1 loads', async ({ page }) => {
    await page.goto('/salary');
    await expect(page.locator('#salary-wizard')).toBeVisible();
    await expect(page.locator('input[name="salary_usd"]')).toBeVisible();
  });

  test('salary wizard step 2 shows exchange rate', async ({ page }) => {
    await page.goto('/salary');
    await page.fill('input[name="salary_usd"]', '3000');
    // Salary step1 uses just {{.Name}} for option labels
    await page.selectOption('select[name="usd_account_id"]', { label: 'USD Salary' });
    await page.selectOption('select[name="egp_account_id"]', { label: 'Main EGP' });
    await page.click('button:has-text("Next")');

    // Step 2 should show exchange rate input
    await expect(page.locator('input[name="exchange_rate"]')).toBeVisible();
  });

  test('salary wizard step 3 shows allocations', async ({ page }) => {
    await page.goto('/salary');
    await page.fill('input[name="salary_usd"]', '3000');
    await page.selectOption('select[name="usd_account_id"]', { label: 'USD Salary' });
    await page.selectOption('select[name="egp_account_id"]', { label: 'Main EGP' });
    await page.click('button:has-text("Next")');

    await page.fill('input[name="exchange_rate"]', '50');
    await page.click('button:has-text("Next")');

    // Step 3 should show allocation inputs and remainder
    await expect(page.locator('#salary-remainder')).toBeVisible();
    await expect(page.locator('#salary-wizard')).toContainText('150000');
  });

  // Quick Entry via FAB bottom sheet
  test('quick entry form opens from FAB', async ({ page }) => {
    await page.goto('/');
    // Click the FAB (+ button)
    await page.locator('.fab-button').click();
    // Wait for HTMX to load the form
    await expect(page.locator('#quick-entry-form')).toBeVisible();
    await expect(page.locator('#quick-entry-form input[name="amount"]')).toBeVisible();
  });

  test('quick entry creates transaction via FAB', async ({ page }) => {
    await page.goto('/');
    await page.locator('.fab-button').click();
    await expect(page.locator('#quick-entry-form')).toBeVisible();

    await page.fill('#quick-entry-form input[name="amount"]', '75');
    await page.selectOption('#qe-account-select', { label: 'Main EGP (EGP)' });
    await page.fill('#quick-entry-form input[name="note"]', 'Quick coffee');
    await page.click('#quick-entry-form button:has-text("Save")');

    await expect(page.locator('#quick-entry-result')).toContainText(/saved|success/i);
  });

  // Quick Exchange via FAB bottom sheet
  test('quick exchange tab switches form', async ({ page }) => {
    await page.goto('/');
    await page.locator('.fab-button').click();
    await expect(page.locator('#quick-entry-form')).toBeVisible();

    // Switch to Exchange tab
    await page.locator('#tab-exchange').click();
    await expect(page.locator('#exchange-src')).toBeVisible();
    await expect(page.locator('#exchange-dst')).toBeVisible();
    await expect(page.locator('#exchange-amount')).toBeVisible();
    await expect(page.locator('#exchange-rate')).toBeVisible();
  });

  test('quick exchange creates exchange via FAB', async ({ page }) => {
    await page.goto('/');
    await page.locator('.fab-button').click();
    await page.locator('#tab-exchange').click();
    await expect(page.locator('#exchange-src')).toBeVisible();

    await page.selectOption('#exchange-src', { label: 'USD Salary (USD)' });
    await page.selectOption('#exchange-dst', { label: 'Main EGP (EGP)' });
    await page.fill('#exchange-amount', '100');
    await page.fill('#exchange-rate', '50');

    // Verify auto-calculation
    await expect(page.locator('#exchange-counter')).toHaveValue('5000.00');

    await page.click('#quick-exchange-form button:has-text("Exchange")');
    await expect(page.locator('#exchange-result')).toContainText(/exchange|completed|success/i);
  });

  test('quick exchange tab resets on reopen', async ({ page }) => {
    await page.goto('/');
    await page.locator('.fab-button').click();
    await expect(page.locator('#quick-entry-form')).toBeVisible();

    // Switch to Exchange tab
    await page.locator('#tab-exchange').click();
    await expect(page.locator('#exchange-src')).toBeVisible();

    // Close sheet
    await page.locator('#quick-entry-overlay').click();

    // Reopen — should default to Transaction tab
    await page.locator('.fab-button').click();
    await expect(page.locator('#quick-entry-form')).toBeVisible();
  });
});
