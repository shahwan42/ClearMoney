import { test, expect } from '@playwright/test';
import { resetDatabase, ensureAuth } from './helpers';

test.describe('Investments (TASK-042)', () => {
  test.beforeAll(async ({ browser }) => {
    await resetDatabase();
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    await ensureAuth(page);
    await ctx.close();
  });

  test.beforeEach(async ({ page }) => {
    await ensureAuth(page);
  });

  test('investments page shows empty state', async ({ page }) => {
    await page.goto('/investments');
    await expect(page.locator('h2:has-text("Investment Portfolio")')).toBeVisible();
    await expect(page.locator('main')).toContainText('No investments yet');
  });

  test('add investment', async ({ page }) => {
    await page.goto('/investments');

    // The add form has two fund_name fields (one from add form).
    // Target the "Add Investment" section form
    const addForm = page.locator('form[hx-post="/investments/add"]');
    await addForm.locator('input[name="fund_name"]').fill('AZG');
    await addForm.locator('input[name="units"]').fill('100');
    await addForm.locator('input[name="unit_price"]').fill('15.50');
    await addForm.locator('button[type="submit"]').click();

    // HX-Redirect reloads the page
    await page.waitForURL('/investments');
    await expect(page.locator('main')).toContainText('AZG');
    await expect(page.locator('main')).toContainText('1,550');
  });

  test('update investment valuation', async ({ page }) => {
    await page.goto('/investments');
    await expect(page.locator('main')).toContainText('AZG');

    // The update form is inside each holding
    const updateForm = page.locator('form[hx-post*="/investments/"][hx-post*="/update"]').first();
    await updateForm.locator('input[name="unit_price"]').fill('16.00');
    await updateForm.locator('button:has-text("Update")').click();

    // Page reloads via HX-Redirect
    await page.waitForURL('/investments');
    await expect(page.locator('main')).toContainText('1,600');
  });

  test('delete investment', async ({ page }) => {
    await page.goto('/investments');
    page.on('dialog', dialog => dialog.accept());
    await page.locator('button:has-text("Del")').first().click();

    await page.waitForURL('/investments');
    await expect(page.locator('main')).toContainText('No investments yet');
  });
});
