import { test, expect } from '@playwright/test';
import { resetDatabase, ensureAuth, TEST_EMAIL, createAuthToken } from './helpers';

test.describe('Auth: Magic Link Login & Registration', () => {
  test.beforeAll(async () => {
    await resetDatabase();
  });

  test('redirects unauthenticated user to /login', async ({ page }) => {
    await page.context().clearCookies();
    await page.goto('/');
    await expect(page).toHaveURL(/\/login/);
  });

  test('login page shows email field and send link button', async ({ page }) => {
    await page.context().clearCookies();
    await page.goto('/login');
    await expect(page.locator('input[name="email"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toContainText('Send magic link');
    // Also verify register link is present
    await expect(page.locator('a[href="/register"]')).toBeVisible();
  });

  test('register page shows email field and create account button', async ({ page }) => {
    await page.context().clearCookies();
    await page.goto('/register');
    await expect(page.locator('input[name="email"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toContainText('Create account');
    // Also verify login link is present
    await expect(page.locator('a[href="/login"]')).toBeVisible();
  });

  test('login submit shows check-email page', async ({ page }) => {
    await page.context().clearCookies();
    await page.goto('/login');
    await expect(page.locator('input[name="email"]')).toBeVisible();
    // Wait at least 2s to pass timing check
    await page.waitForTimeout(2200);
    await page.fill('input[name="email"]', TEST_EMAIL);
    await page.click('button[type="submit"]');
    await expect(page.locator('text=Check your email')).toBeVisible({ timeout: 10000 });
  });

  test('magic link verify with valid token logs in', async ({ page }) => {
    await page.context().clearCookies();
    const token = createAuthToken(TEST_EMAIL, 'login');
    await page.goto(`/auth/verify?token=${token}`);
    await expect(page).toHaveURL('/');
    await expect(page.getByRole('heading', { name: 'Welcome to ClearMoney' })).toBeVisible();
  });

  test('magic link verify with invalid token shows link-expired', async ({ page }) => {
    await page.context().clearCookies();
    await page.goto('/auth/verify?token=invalid-token-abc123');
    await expect(page.locator('text=Link expired')).toBeVisible();
  });

  test('magic link verify with no token shows link-expired', async ({ page }) => {
    await page.context().clearCookies();
    await page.goto('/auth/verify');
    await expect(page.locator('text=Link expired')).toBeVisible();
  });

  test('logout clears session and redirects to /login', async ({ page }) => {
    await ensureAuth(page);
    await page.goto('/settings');
    await Promise.all([
      page.waitForURL(/\/login/),
      page.locator('form[action="/logout"] button[type="submit"]').click(),
    ]);
    await expect(page).toHaveURL(/\/login/);
  });

  test('cannot access protected routes without session', async ({ page }) => {
    await page.context().clearCookies();
    await page.goto('/accounts');
    await expect(page).toHaveURL(/\/login/);
  });
});
