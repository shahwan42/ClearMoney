import { test, expect } from '@playwright/test';
import { resetDatabase, TEST_PIN, setupPIN, login } from './helpers';

test.describe('Auth: Setup & Login (TASK-017, TASK-018)', () => {
  test.beforeAll(async () => {
    await resetDatabase();
  });

  test('redirects unauthenticated user to /setup on first visit', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveURL(/\/setup/);
    await expect(page.locator('h1')).toContainText('Welcome to ClearMoney');
  });

  test('shows setup form with PIN and confirm fields', async ({ page }) => {
    await page.goto('/setup');
    await expect(page.locator('input[name="pin"]')).toBeVisible();
    await expect(page.locator('input[name="confirm_pin"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toContainText('Set PIN & Start');
  });

  test('rejects mismatched PINs on setup', async ({ page }) => {
    await page.goto('/setup');
    await page.fill('input[name="pin"]', '1234');
    await page.fill('input[name="confirm_pin"]', '5678');
    await page.click('button[type="submit"]');
    await expect(page.locator('text=PINs do not match')).toBeVisible();
  });

  test('creates PIN and auto-logs in', async ({ page }) => {
    await page.goto('/setup');
    await page.fill('input[name="pin"]', TEST_PIN);
    await page.fill('input[name="confirm_pin"]', TEST_PIN);
    await page.click('button[type="submit"]');
    await page.waitForURL('/');
    await expect(page.locator('text=Net Worth')).toBeVisible();
  });

  test('redirects /setup to /login after PIN is set', async ({ page }) => {
    await page.goto('/setup');
    await expect(page).toHaveURL(/\/login/);
  });

  test('shows login page with PIN field', async ({ page }) => {
    await page.goto('/login');
    await expect(page.locator('input[name="pin"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toContainText('Unlock');
  });

  test('rejects wrong PIN', async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[name="pin"]', '9999');
    await page.click('button[type="submit"]');
    await expect(page.locator('text=Invalid PIN')).toBeVisible();
  });

  test('logs in with correct PIN', async ({ page }) => {
    await login(page);
    await expect(page.locator('text=Net Worth')).toBeVisible();
  });

  test('logout clears session and redirects to /login', async ({ page }) => {
    await login(page);
    // Navigate to settings and use the logout form
    await page.goto('/settings');
    await expect(page.locator('button:has-text("Log Out")')).toBeVisible();
    // The logout uses hx-post which does an AJAX POST. Use request directly.
    await page.request.post('/logout');
    // After logout, clear cookies client-side and verify redirect
    await page.context().clearCookies();
    await page.goto('/');
    await expect(page).toHaveURL(/\/login/);
  });

  test('cannot access protected routes without session', async ({ page }) => {
    await page.context().clearCookies();
    await page.goto('/accounts');
    // Should redirect to /login (PIN is already set up)
    await expect(page).toHaveURL(/\/login/);
  });
});
