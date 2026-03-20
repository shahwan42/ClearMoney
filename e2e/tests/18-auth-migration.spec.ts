import { test, expect } from '@playwright/test';
import {
  resetDatabase,
  ensureAuth,
  TEST_EMAIL,
  GO_BASE_URL,
  createAuthToken,
  createExpiredSession,
  runSQL,
} from './helpers';

/**
 * Auth tests — verify Django auth routes work correctly.
 *
 * Covers login, register, verify, and logout flows including
 * anti-bot protections (honeypot, timing) and session management.
 */

test.describe('Auth: Page Rendering', () => {
  test.beforeAll(async () => {
    await resetDatabase();
  });

  test('GET /login renders login form with email input', async ({ page }) => {
    await page.context().clearCookies();
    await page.goto('/login');
    await expect(page.locator('input[name="email"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toContainText('Send magic link');
    await expect(page.locator('a[href="/register"]')).toBeVisible();
  });

  test('GET /register renders registration form', async ({ page }) => {
    await page.context().clearCookies();
    await page.goto('/register');
    await expect(page.locator('input[name="email"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toContainText('Create account');
    await expect(page.locator('a[href="/login"]')).toBeVisible();
  });

  test('login page has honeypot and timing fields', async ({ page }) => {
    await page.context().clearCookies();
    await page.goto('/login');
    // Honeypot field exists but hidden
    await expect(page.locator('input[name="website"]')).toBeAttached();
    // Timing field exists
    await expect(page.locator('input[name="_rt"]')).toBeAttached();
  });
});

test.describe('Auth: Login Flow', () => {
  test.beforeAll(async () => {
    await resetDatabase();
  });

  test('POST /login with valid email shows check-email page', async ({ page }) => {
    await page.context().clearCookies();
    await page.goto('/login');
    // Wait 2.5s to pass timing check
    await page.waitForTimeout(2500);
    await page.fill('input[name="email"]', TEST_EMAIL);
    await page.click('button[type="submit"]');
    await expect(page.locator('text=Check your email')).toBeVisible({ timeout: 10000 });
    await expect(page.locator(`text=${TEST_EMAIL}`)).toBeVisible();
  });

  test('POST /login with unknown email still shows check-email (enumeration prevention)', async ({ page }) => {
    await page.context().clearCookies();
    await page.goto('/login');
    await page.waitForTimeout(2500);
    await page.fill('input[name="email"]', 'unknown-e2e@example.com');
    await page.click('button[type="submit"]');
    await expect(page.locator('text=Check your email')).toBeVisible({ timeout: 10000 });
    // Hint should show (previously sent link message)
    await expect(page.locator('text=previously sent link')).toBeVisible();
  });

  test('POST /login with empty email shows error', async ({ page }) => {
    // HTML5 required validation will prevent form submission with empty email,
    // but we can test by submitting programmatically
    await page.context().clearCookies();
    const resp = await page.request.post('/login', {
      form: { email: '', _rt: String(Math.floor(Date.now() / 1000) - 5) },
    });
    expect(resp.status()).toBe(200);
    const text = await resp.text();
    expect(text).toContain('Email is required');
  });
});

test.describe('Auth: Registration Flow', () => {
  test.beforeAll(async () => {
    await resetDatabase();
  });

  test('POST /register with new email shows check-email page', async ({ page }) => {
    await page.context().clearCookies();
    await page.goto('/register');
    await page.waitForTimeout(2500);
    // Use unique email to avoid conflict
    const uniqueEmail = `e2e-reg-${Date.now()}@example.com`;
    await page.fill('input[name="email"]', uniqueEmail);
    await page.click('button[type="submit"]');
    await expect(page.locator('text=Check your email')).toBeVisible({ timeout: 10000 });
  });

  test('POST /register with existing email shows error', async ({ page }) => {
    await page.context().clearCookies();
    await page.goto('/register');
    await page.waitForTimeout(2500);
    await page.fill('input[name="email"]', TEST_EMAIL);
    await page.click('button[type="submit"]');
    await expect(page.locator('text=already exists')).toBeVisible({ timeout: 10000 });
  });
});

test.describe('Auth: Magic Link Verification', () => {
  test.beforeAll(async () => {
    await resetDatabase();
  });

  test('GET /auth/verify with valid login token creates session and redirects', async ({ page }) => {
    await page.context().clearCookies();
    const token = createAuthToken(TEST_EMAIL, 'login');
    await page.goto(`/auth/verify?token=${token}`);
    // Should redirect to / (dashboard)
    await expect(page).toHaveURL(/\//);
  });

  test('GET /auth/verify with expired token shows link-expired', async ({ page }) => {
    await page.context().clearCookies();
    // Create an expired token directly in DB
    const token = `expired-${Date.now()}`;
    runSQL(
      `INSERT INTO auth_tokens (email, token, purpose, expires_at) VALUES ('${TEST_EMAIL}', '${token}', 'login', NOW() - INTERVAL '1 hour')`,
    );
    await page.goto(`/auth/verify?token=${token}`);
    await expect(page.locator('text=Link expired')).toBeVisible();
  });

  test('GET /auth/verify with used token shows link-expired', async ({ page }) => {
    await page.context().clearCookies();
    const token = `used-${Date.now()}`;
    runSQL(
      `INSERT INTO auth_tokens (email, token, purpose, expires_at, used) VALUES ('${TEST_EMAIL}', '${token}', 'login', NOW() + INTERVAL '15 minutes', true)`,
    );
    await page.goto(`/auth/verify?token=${token}`);
    await expect(page.locator('text=Link expired')).toBeVisible();
  });

  test('GET /auth/verify with missing token shows link-expired', async ({ page }) => {
    await page.context().clearCookies();
    await page.goto('/auth/verify');
    await expect(page.locator('text=Link expired')).toBeVisible();
  });

  test('GET /auth/verify with invalid token shows link-expired', async ({ page }) => {
    await page.context().clearCookies();
    await page.goto('/auth/verify?token=totally-invalid-token');
    await expect(page.locator('text=Link expired')).toBeVisible();
  });

  test('registration verify seeds 25 categories for new user', async ({ page }) => {
    await page.context().clearCookies();
    const regEmail = `e2e-seed-${Date.now()}@example.com`;
    const token = createAuthToken(regEmail, 'registration');
    await page.goto(`/auth/verify?token=${token}`);
    // Should redirect to /
    await expect(page).toHaveURL(/\//);
    // Verify categories were seeded
    const count = runSQL(
      `SELECT COUNT(*) FROM categories WHERE user_id = (SELECT id FROM users WHERE LOWER(email) = LOWER('${regEmail}'))`,
    );
    expect(parseInt(count)).toBe(25);
  });
});

test.describe('Auth: Logout', () => {
  test.beforeAll(async () => {
    await resetDatabase();
  });

  test('POST /logout clears session and redirects to /login', async ({ page }) => {
    // Create a session via verify
    await page.context().clearCookies();
    const token = createAuthToken(TEST_EMAIL, 'login');
    await page.goto(`/auth/verify?token=${token}`);
    await expect(page).toHaveURL(/\//);

    // Now POST /logout
    const resp = await page.request.post('/logout');
    expect(resp.status()).toBe(200); // Follows redirect
    expect(resp.url()).toContain('/login');
  });
});

test.describe('Auth: Cross-App Session Continuity', () => {
  test.beforeAll(async () => {
    await resetDatabase();
  });

  test('session created by /auth/verify works on /settings', async ({ page }) => {
    await page.context().clearCookies();
    const token = createAuthToken(TEST_EMAIL, 'login');
    await page.goto(`/auth/verify?token=${token}`);
    await expect(page).toHaveURL(/\//);
    // Navigate to settings — should be authenticated
    await page.goto('/settings');
    await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();
  });

  test('session created by Django works on Go routes', async ({ page }) => {
    await page.context().clearCookies();
    const token = createAuthToken(TEST_EMAIL, 'login');
    // Verify via Django
    await page.goto(`/auth/verify?token=${token}`);
    await expect(page).toHaveURL(/\//);
    // Go to Go's route — session should be valid there too
    await page.goto(`${GO_BASE_URL}/`);
    // Should be authenticated (not redirected to /login)
    await expect(page).toHaveURL(`${GO_BASE_URL}/`);
  });
});
