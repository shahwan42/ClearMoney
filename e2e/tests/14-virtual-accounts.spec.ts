import { test, expect } from '@playwright/test';
import { resetDatabase, ensureAuth, createInstitution, createAccount } from './helpers';

test.describe('Virtual Accounts', () => {
  let accountId: string;

  test.beforeAll(async ({ browser }) => {
    await resetDatabase();
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    await ensureAuth(page);

    const instId = await createInstitution(page, 'HSBC');
    accountId = await createAccount(page, { name: 'Checking', institution_id: instId, type: 'current', currency: 'EGP', initial_balance: 50000 });

    await ctx.close();
  });

  test.beforeEach(async ({ page }) => {
    await ensureAuth(page);
  });

  test('virtual accounts page shows empty state', async ({ page }) => {
    await page.goto('/virtual-accounts');
    await expect(page.locator('h2:has-text("Virtual Accounts")')).toBeVisible();
    await expect(page.locator('main')).toContainText('No virtual accounts yet');
  });

  test('create virtual account', async ({ page }) => {
    await page.goto('/virtual-accounts');

    await page.fill('input[name="name"]', 'Emergency Fund');
    await page.fill('input[name="target_amount"]', '100000');
    await page.selectOption('select[name="account_id"]', { label: 'Checking (EGP)' });
    await page.click('button:has-text("Create")');

    await page.waitForURL('/virtual-accounts');
    await expect(page.locator('main')).toContainText('Emergency Fund');
  });

  test('virtual account detail page shows info', async ({ page }) => {
    await page.goto('/virtual-accounts');
    await page.click('a:has-text("Emergency Fund")');

    await expect(page.locator('h2')).toContainText('Emergency Fund');
    await expect(page.locator('h3:has-text("Allocate Funds")')).toBeVisible();
    await expect(page.locator('h3:has-text("History")')).toBeVisible();
  });

  test('allocate funds to virtual account', async ({ page }) => {
    await page.goto('/virtual-accounts');
    await page.click('a:has-text("Emergency Fund")');

    await page.selectOption('select[name="type"]', 'contribution');
    await page.fill('input[name="amount"]', '5000');
    await page.fill('input[name="note"]', 'Initial allocation');
    await page.click('button:has-text("Allocate")');

    // Should redirect back and show updated balance
    await expect(page.locator('main')).toContainText('5,000');
    await expect(page.locator('main')).toContainText('Initial allocation');
  });

  test('edit virtual account via bottom sheet', async ({ page }) => {
    await page.goto('/virtual-accounts');
    await page.click('a:has-text("Emergency Fund")');

    // Open edit bottom sheet
    await page.click('button:has-text("Edit")');
    await expect(page.locator('[data-bottom-sheet="edit-virtual-account"]')).toBeVisible();

    // Edit the name
    const sheet = page.locator('[data-bottom-sheet="edit-virtual-account"]');
    await sheet.locator('input[name="name"]').fill('Rainy Day Fund');
    await sheet.locator('button[type="submit"]').click();

    // Should update the page
    await expect(page.locator('h2')).toContainText('Rainy Day Fund');
  });

  test('archive virtual account', async ({ page }) => {
    await page.goto('/virtual-accounts');
    await expect(page.locator('main')).toContainText('Rainy Day Fund');

    await page.locator('button:has-text("Archive")').click();
    await page.waitForURL('/virtual-accounts');

    // Should show empty state again
    await expect(page.locator('main')).toContainText('No virtual accounts yet');
  });
});
