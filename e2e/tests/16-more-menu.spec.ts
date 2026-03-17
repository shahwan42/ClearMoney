import { test, expect } from '@playwright/test';
import { resetDatabase, ensureAuth } from './helpers';

test.describe('More Menu Bottom Sheet', () => {
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

  test('more button opens bottom sheet', async ({ page }) => {
    await page.goto('/');
    await page.locator('button:has-text("More")').click();
    await expect(page.locator('[data-bottom-sheet="more-menu"]')).not.toHaveClass(/translate-y-full/);
  });

  test('more menu shows all navigation items', async ({ page }) => {
    await page.goto('/');
    await page.locator('button:has-text("More")').click();

    const sheet = page.locator('[data-bottom-sheet="more-menu"]');
    await expect(sheet.locator('a[href="/people"]')).toBeVisible();
    await expect(sheet.locator('a[href="/budgets"]')).toBeVisible();
    await expect(sheet.locator('a[href="/virtual-accounts"]')).toBeVisible();
    await expect(sheet.locator('a[href="/investments"]')).toBeVisible();
    await expect(sheet.locator('a[href="/installments"]')).toBeVisible();
    await expect(sheet.locator('a[href="/recurring"]')).toBeVisible();
    await expect(sheet.locator('a[href="/batch-entry"]')).toBeVisible();
    await expect(sheet.locator('a[href="/salary"]')).toBeVisible();
    await expect(sheet.locator('a[href="/fawry-cashout"]')).toBeVisible();
    await expect(sheet.locator('a[href="/settings"]')).toBeVisible();
  });

  test('clicking menu item navigates to correct page', async ({ page }) => {
    await page.goto('/');
    await page.locator('button:has-text("More")').click();
    await page.locator('[data-bottom-sheet="more-menu"] a[href="/people"]').click();
    await expect(page).toHaveURL('/people');
  });

  test('overlay click dismisses the sheet', async ({ page }) => {
    await page.goto('/');
    await page.locator('button:has-text("More")').click();
    await expect(page.locator('[data-bottom-sheet="more-menu"]')).not.toHaveClass(/translate-y-full/);

    // Click overlay to close
    await page.locator('#more-menu-overlay').click({ force: true });
    await expect(page.locator('[data-bottom-sheet="more-menu"]')).toHaveClass(/translate-y-full/);
  });
});
