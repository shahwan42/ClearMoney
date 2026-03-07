import { test, expect } from '@playwright/test';
import { resetDatabase, ensureAuth, createInstitution, createAccount } from './helpers';

test.describe('Institutions & Accounts (TASK-001 to TASK-008)', () => {
  test.beforeAll(async () => {
    await resetDatabase();
  });

  test.beforeEach(async ({ page }) => {
    await ensureAuth(page);
  });

  test('accounts page shows empty state', async ({ page }) => {
    await page.goto('/accounts');
    await expect(page.getByRole('heading', { name: 'Accounts' })).toBeVisible();
    // Institution form should be visible
    await expect(page.locator('form input[name="name"]').first()).toBeVisible();
  });

  test('create institution via form', async ({ page }) => {
    await page.goto('/accounts');
    // Fill the institution form (first form with name field)
    await page.locator('form[hx-post="/institutions/add"] input[name="name"]').fill('HSBC');
    await page.locator('form[hx-post="/institutions/add"] select[name="type"]').selectOption('bank');
    await page.locator('form[hx-post="/institutions/add"] button[type="submit"]').click();
    // Wait for HTMX update
    await expect(page.locator('#institution-list')).toContainText('HSBC');
  });

  test('create account under institution', async ({ page }) => {
    await page.goto('/accounts');
    await expect(page.locator('#institution-list')).toContainText('HSBC');

    // Click "+ Account" button
    await page.click('button:has-text("+ Account")');
    await expect(page.locator('#account-form-area input[name="name"]')).toBeVisible();

    // Fill account form
    await page.fill('#account-form-area input[name="name"]', 'Checking');
    await page.selectOption('#account-form-area select[name="type"]', 'checking');
    await page.selectOption('#account-form-area select[name="currency"]', 'EGP');
    await page.fill('#account-form-area input[name="initial_balance"]', '50000');
    await page.click('#account-form-area button[type="submit"]');

    // Account should appear in institution list
    await expect(page.locator('#institution-list')).toContainText('Checking');
  });

  test('create credit card account shows credit limit field', async ({ page }) => {
    await page.goto('/accounts');
    await page.click('button:has-text("+ Account")');

    // Select credit card type — credit limit field should appear
    await page.selectOption('#account-form-area select[name="type"]', 'credit_card');
    await expect(page.locator('#credit-limit-field')).toBeVisible();

    await page.fill('#account-form-area input[name="name"]', 'Visa Gold');
    await page.fill('#account-form-area input[name="credit_limit"]', '200000');
    await page.click('#account-form-area button[type="submit"]');

    await expect(page.locator('#institution-list')).toContainText('Visa Gold');
  });

  test('account detail page shows balance and info', async ({ page }) => {
    await page.goto('/accounts');
    // Click on the Checking account to go to detail
    await page.click('a:has-text("Checking")');
    await expect(page.getByRole('heading', { name: 'Checking' })).toBeVisible();
    await expect(page.locator('text=Current Balance')).toBeVisible();
  });

  test('dormant toggle works on account detail', async ({ page }) => {
    await page.goto('/accounts');
    await page.click('a:has-text("Checking")');
    // Click dormant toggle button
    await page.locator('button:has-text("Dormant")').click();
    // After toggling, the button text should change to "Active"
    await expect(page.locator('button:has-text("Active")')).toBeVisible();
  });

  test('create second institution (fintech)', async ({ page }) => {
    await page.goto('/accounts');
    await page.locator('form[hx-post="/institutions/add"] input[name="name"]').fill('Fawry');
    await page.locator('form[hx-post="/institutions/add"] select[name="type"]').selectOption('fintech');
    await page.locator('form[hx-post="/institutions/add"] button[type="submit"]').click();
    await expect(page.locator('#institution-list')).toContainText('Fawry');
  });

  test('dashboard shows net worth with accounts', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('text=Net Worth')).toBeVisible();
    // Should show account balances from HSBC
    await expect(page.locator('text=HSBC')).toBeVisible();
  });
});
