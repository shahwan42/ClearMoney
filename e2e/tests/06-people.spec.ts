import { test, expect } from '@playwright/test';
import { resetDatabase, ensureAuth, createInstitution, createAccount } from './helpers';

test.describe('People & Loans (TASK-031, TASK-032)', () => {
  test.beforeAll(async ({ browser }) => {
    await resetDatabase();
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    await ensureAuth(page);

    const instId = await createInstitution(page, 'HSBC');
    await createAccount(page, { name: 'Checking', institution_id: instId, type: 'checking', currency: 'EGP', initial_balance: 50000 });

    await ctx.close();
  });

  test.beforeEach(async ({ page }) => {
    await ensureAuth(page);
  });

  test('people page shows empty state', async ({ page }) => {
    await page.goto('/people');
    await expect(page.getByRole('heading', { name: 'People' })).toBeVisible();
    await expect(page.locator('main')).toContainText('No people yet');
  });

  test('add a person', async ({ page }) => {
    await page.goto('/people');
    await page.fill('input[name="name"]', 'Ali');
    await page.click('button:has-text("Add")');
    await expect(page.locator('#people-list')).toContainText('Ali');
  });

  test('record a loan (I lent)', async ({ page }) => {
    await page.goto('/people');
    await expect(page.locator('#people-list')).toContainText('Ali');

    // Open loan form
    await page.click('button:has-text("Record Loan")');

    // Fill loan form - find the visible form
    const loanForm = page.locator('[id^="loan-form-"]').first();
    await expect(loanForm).toBeVisible();
    await loanForm.locator('input[name="amount"]').fill('1000');
    await loanForm.locator('select[name="account_id"]').selectOption({ label: 'Checking (EGP)' });
    await loanForm.locator('input[name="note"]').fill('Lent for groceries');
    await loanForm.locator('button[type="submit"]').click();

    // Balance should show the person owes you
    await expect(page.locator('#people-list')).toContainText('1,000');
  });

  test('record a repayment', async ({ page }) => {
    await page.goto('/people');
    await expect(page.locator('#people-list')).toContainText('Ali');

    // Open repay form
    await page.click('button:has-text("Repayment")');

    const repayForm = page.locator('[id^="repay-form-"]').first();
    await expect(repayForm).toBeVisible();
    await repayForm.locator('input[name="amount"]').fill('500');
    await repayForm.locator('select[name="account_id"]').selectOption({ label: 'Checking (EGP)' });
    await repayForm.locator('button[type="submit"]').click();

    // Remaining balance should be 500
    await expect(page.locator('#people-list')).toContainText('500');
  });

  test('people summary on dashboard', async ({ page }) => {
    await page.goto('/');
    // Dashboard should show people summary widget
    await expect(page.locator('#people-summary')).toBeVisible();
  });
});
