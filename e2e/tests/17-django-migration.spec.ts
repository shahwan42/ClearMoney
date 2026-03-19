import { test, expect } from '@playwright/test';
import {
  resetDatabase,
  ensureAuth,
  createInstitution,
  createAccount,
  createTransaction,
  getCategoryId,
  createExpiredSession,
  DJANGO_BASE_URL,
  TEST_EMAIL,
} from './helpers';

/**
 * Django Migration E2E Tests
 *
 * Verifies that routes migrated from Go to Django work correctly:
 * - Cross-app session sharing (Go session cookie -> Django auth)
 * - Data created via Go appears in Django views
 * - Django UI renders all expected elements
 * - Navigation between Go and Django preserves sessions
 *
 * Tests hit Django directly on port 8000 (not through Caddy).
 */

let userId: string;
let accountId: string;
let expenseCategoryId: string;

test.describe('Django Migration - Cross-App Integration', () => {
  test.beforeAll(async ({ browser }) => {
    userId = await resetDatabase();
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    await ensureAuth(page);

    // Create test data via Go API
    const instId = await createInstitution(page, 'Test Bank');
    accountId = await createAccount(page, {
      name: 'Current',
      institution_id: instId,
      type: 'current',
      currency: 'EGP',
      initial_balance: 50000,
    });

    expenseCategoryId = getCategoryId('expense', userId);

    // Create transactions for reports/export tests
    const today = new Date().toISOString().split('T')[0];
    await createTransaction(page, {
      account_id: accountId,
      category_id: expenseCategoryId,
      amount: 500,
      type: 'expense',
      note: 'Groceries for e2e test',
      date: today,
    });
    await createTransaction(page, {
      account_id: accountId,
      category_id: expenseCategoryId,
      amount: 200,
      type: 'expense',
      note: 'Transport for e2e test',
      date: today,
    });

    await ctx.close();
  });

  test.beforeEach(async ({ page }) => {
    await ensureAuth(page);
  });

  // ──────────────────────────────────────────────────
  // Group 1: Cross-App Session Sharing
  // ──────────────────────────────────────────────────

  test.describe('Session Sharing', () => {
    test('Go session cookie authenticates on Django /settings', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/settings`);
      await expect(page.getByRole('heading', { name: /Settings/i })).toBeVisible();
    });

    test('Go session cookie authenticates on Django /reports', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/reports`);
      await expect(page.getByRole('heading', { name: /Reports/i })).toBeVisible();
    });

    test('no session cookie redirects to /login on Django', async ({ page }) => {
      // Clear all cookies so there's no session
      await page.context().clearCookies();
      const resp = await page.goto(`${DJANGO_BASE_URL}/settings`);
      // Django middleware redirects to /login — Playwright follows the redirect
      // but /login is served by Go (not Django), so we check the URL
      expect(page.url()).toContain('/login');
    });

    test('expired session redirects to /login on Django', async ({ page }) => {
      // Clear existing cookies and set an expired session
      await page.context().clearCookies();
      const expiredToken = createExpiredSession(userId);
      await page.context().addCookies([{
        name: 'clearmoney_session',
        value: expiredToken,
        domain: 'localhost',
        path: '/',
        httpOnly: true,
        sameSite: 'Lax',
      }]);

      const resp = await page.goto(`${DJANGO_BASE_URL}/reports`);
      expect(page.url()).toContain('/login');
    });
  });

  // ──────────────────────────────────────────────────
  // Group 2: Data Consistency Across Apps
  // ──────────────────────────────────────────────────

  test.describe('Data Consistency', () => {
    test('Go-created transactions appear in Django reports', async ({ page }) => {
      const now = new Date();
      const year = now.getFullYear();
      const month = now.getMonth() + 1;
      await page.goto(`${DJANGO_BASE_URL}/reports?year=${year}&month=${month}`);

      // Should show spending by category section with our test transactions
      await expect(page.locator('text=Spending by Category')).toBeVisible();
      // Total spending should be at least 700 EGP (500 + 200)
      await expect(page.locator('main')).toContainText('700');
    });

    test('Go-created transactions appear in Django CSV export', async ({ page }) => {
      const today = new Date().toISOString().split('T')[0];
      const firstOfMonth = today.substring(0, 8) + '01';

      const resp = await page.request.get(
        `${DJANGO_BASE_URL}/export/transactions?from=${firstOfMonth}&to=${today}`,
      );

      expect(resp.status()).toBe(200);
      expect(resp.headers()['content-type']).toContain('text/csv');

      const csv = await resp.text();
      expect(csv).toContain('Groceries for e2e test');
      expect(csv).toContain('Transport for e2e test');
      expect(csv).toContain('500.00');
      expect(csv).toContain('200.00');
    });

    test('Django reports currency filter works with Go data', async ({ page }) => {
      const now = new Date();
      const year = now.getFullYear();
      const month = now.getMonth() + 1;
      await page.goto(`${DJANGO_BASE_URL}/reports?year=${year}&month=${month}&currency=EGP`);

      // EGP filter should show the transactions (account is EGP)
      await expect(page.locator('text=Spending by Category')).toBeVisible();
      await expect(page.locator('main')).toContainText('700');

      // USD filter should show no spending (no USD transactions)
      await page.goto(`${DJANGO_BASE_URL}/reports?year=${year}&month=${month}&currency=USD`);
      await expect(page.locator('main')).not.toContainText('700');
    });
  });

  // ──────────────────────────────────────────────────
  // Group 3: Django UI Parity
  // ──────────────────────────────────────────────────

  test.describe('UI Parity', () => {
    test('Django /settings has dark mode, CSV export, and logout', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/settings`);

      // Dark mode toggle
      await expect(page.locator('text=Dark Mode')).toBeVisible();

      // CSV export section with Download button
      await expect(page.locator('button:has-text("Download CSV")')).toBeVisible();
      await expect(page.locator('input[name="from"]')).toBeVisible();
      await expect(page.locator('input[name="to"]')).toBeVisible();

      // Logout form that posts to Go's /logout
      await expect(page.locator('form[action="/logout"] button')).toContainText('Log Out');
    });

    test('Django /reports has month nav, donut chart, and bar chart sections', async ({ page }) => {
      const now = new Date();
      const year = now.getFullYear();
      const month = now.getMonth() + 1;
      await page.goto(`${DJANGO_BASE_URL}/reports?year=${year}&month=${month}`);

      // Month navigation
      await expect(page.locator('a:has-text("Prev")').first()).toBeVisible();
      await expect(page.locator('a:has-text("Next")').first()).toBeVisible();

      // Spending by category section (donut chart area)
      await expect(page.locator('text=Spending by Category')).toBeVisible();

      // Income vs Expenses section (bar chart area)
      await expect(page.locator('text=Income vs Expenses')).toBeVisible();
    });

    test('Django /reports month navigation works', async ({ page }) => {
      const now = new Date();
      const year = now.getFullYear();
      const month = now.getMonth() + 1;
      await page.goto(`${DJANGO_BASE_URL}/reports?year=${year}&month=${month}`);

      const prevMonth = month === 1 ? 12 : month - 1;
      const prevYear = month === 1 ? year - 1 : year;

      // Click "Prev" and wait for navigation to complete
      await Promise.all([
        page.waitForURL(`**/reports?year=${prevYear}&month=${prevMonth}`),
        page.click('a:has-text("Prev")'),
      ]);

      await expect(page.getByRole('heading', { name: /Reports/i })).toBeVisible();
      expect(page.url()).toContain(`month=${prevMonth}`);
    });

    test('Django /settings logout form targets Go /logout endpoint', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/settings`);

      // Verify the form action points to Go's /logout (cross-app form submission)
      const form = page.locator('form[action="/logout"]');
      await expect(form).toBeVisible();
      await expect(form.locator('button')).toContainText('Log Out');
    });
  });

  // ──────────────────────────────────────────────────
  // Group 4: Accounts & Institutions (Phase 3)
  // ──────────────────────────────────────────────────

  test.describe('Accounts & Institutions', () => {
    test('Go session authenticates on Django /accounts', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/accounts`);
      await expect(page.locator('text=Accounts')).toBeVisible();
    });

    test('Go-created institutions appear in Django accounts list', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/accounts`);
      await expect(page.locator('text=Test Bank')).toBeVisible();
    });

    test('Go-created accounts appear under their institutions', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/accounts`);
      await expect(page.locator('text=Current')).toBeVisible();
    });

    test('Account detail page shows balance and transactions', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/accounts/${accountId}`);
      await expect(page.locator('text=Current Balance')).toBeVisible();
      await expect(page.locator('text=Transaction History')).toBeVisible();
    });

    test('Account detail shows institution name', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/accounts/${accountId}`);
      await expect(page.locator('text=Test Bank')).toBeVisible();
    });

    test('Dormant toggle button is visible on account detail', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/accounts/${accountId}`);
      await expect(page.locator('text=Dormant Account')).toBeVisible();
    });

    test('Health rules form is visible on account detail', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/accounts/${accountId}`);
      await expect(page.locator('text=Health Rules')).toBeVisible();
      await expect(page.locator('input[name="min_balance"]')).toBeVisible();
    });

    test('Delete Account button is visible on account detail', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/accounts/${accountId}`);
      await expect(page.locator('text=Delete Account')).toBeVisible();
    });

    test('Non-credit account returns 400 for statement page', async ({ page }) => {
      const resp = await page.request.get(`${DJANGO_BASE_URL}/accounts/${accountId}/statement`);
      expect(resp.status()).toBe(400);
    });

    test('Nonexistent account returns 404', async ({ page }) => {
      const resp = await page.request.get(`${DJANGO_BASE_URL}/accounts/00000000-0000-0000-0000-000000000000`);
      expect(resp.status()).toBe(404);
    });
  });

  // ──────────────────────────────────────────────────
  // Group 5: Cross-App Navigation
  // ──────────────────────────────────────────────────

  test.describe('Cross-App Navigation', () => {
    test('Go dashboard -> Django /reports preserves session', async ({ page }) => {
      // Start on Go dashboard
      await page.goto('/');
      await expect(page.locator('main')).toBeVisible();

      // Navigate to Django reports via header link
      // The link goes to /reports (relative), which from Go's baseURL stays on port 8080
      // In production Caddy routes this to Django, but in tests we verify the link exists
      const reportsLink = page.locator('a[href="/reports"]').first();
      await expect(reportsLink).toBeVisible();

      // Now verify Django serves it correctly with the same session
      await page.goto(`${DJANGO_BASE_URL}/reports`);
      await expect(page.getByRole('heading', { name: /Reports/i })).toBeVisible();
    });

    test('Django /settings -> Go dashboard preserves session', async ({ page }) => {
      // Start on Django settings
      await page.goto(`${DJANGO_BASE_URL}/settings`);
      await expect(page.getByRole('heading', { name: /Settings/i })).toBeVisible();

      // Navigate to Go dashboard via header logo link
      // The ClearMoney logo links to "/" which on Django would stay on port 8000
      // Verify the link exists in Django's header
      const homeLink = page.locator('header a[href="/"]');
      await expect(homeLink).toBeVisible();

      // Now verify Go serves dashboard correctly with the same session
      await page.goto('/');
      await expect(page.locator('main')).toBeVisible();
    });
  });

  // ──────────────────────────────────────────────────
  // Group 6: Transactions (Phase 4)
  // ──────────────────────────────────────────────────

  test.describe('Transactions', () => {
    test('Django /transactions renders list page', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/transactions`);
      await expect(page.getByRole('heading', { name: /Transactions/i })).toBeVisible();
      // Filter form should be present
      await expect(page.locator('#tx-filters')).toBeVisible();
    });

    test('Django /transactions/new renders form', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/transactions/new`);
      await expect(page.getByRole('heading', { name: /New Transaction/i })).toBeVisible();
      await expect(page.locator('input[name="amount"]')).toBeVisible();
    });

    test('Django /transfers/new renders transfer form', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/transfers/new`);
      await expect(page.getByText('Transfer Between Accounts')).toBeVisible();
      await expect(page.locator('select[name="source_account_id"]')).toBeVisible();
    });

    test('Django /exchange/new renders exchange form', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/exchange/new`);
      await expect(page.getByText('Currency Exchange')).toBeVisible();
    });

    test('Django /batch-entry renders batch form', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/batch-entry`);
      await expect(page.getByRole('heading', { name: /Batch Entry/i })).toBeVisible();
    });

    test('Django /fawry-cashout renders fawry form', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/fawry-cashout`);
      await expect(page.getByText('Fawry Cash-Out')).toBeVisible();
    });

    test('Django transaction list shows test transactions', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/transactions`);
      await expect(page.getByText('Groceries for e2e test')).toBeVisible();
      await expect(page.getByText('Transport for e2e test')).toBeVisible();
    });
  });

  // ──────────────────────────────────────────────────
  // Group 7: People & Loans (Phase 5)
  // ──────────────────────────────────────────────────

  test.describe('People & Loans', () => {
    test('Django /people renders empty state', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/people`);
      await expect(page.getByRole('heading', { name: /People/i })).toBeVisible();
      await expect(page.getByText('No people yet')).toBeVisible();
    });

    test('add person via Django /people', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/people`);
      await page.fill('input[name="name"]', 'E2E Ali');
      await page.click('button:has-text("Add")');
      await expect(page.locator('#people-list')).toContainText('E2E Ali');
    });

    test('record loan via Django /people', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/people`);

      // Open loan form for the first person card
      await page.click('button:has-text("Record Loan")');

      // Fill loan form (the form should now be visible)
      const loanForm = page.locator('[id^="loan-form-"]').first();
      await expect(loanForm).toBeVisible();
      await loanForm.locator('input[name="amount"]').fill('1000');
      await loanForm.locator('select[name="account_id"]').selectOption({ index: 1 });
      await loanForm.locator('button[type="submit"]').click();

      // Balance should appear on the person card
      await expect(page.locator('#people-list')).toContainText('1,000');
    });

    test('record repayment via Django /people', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/people`);

      // Open repay form (visible because balance != 0)
      await page.click('button:has-text("Repayment")');

      const repayForm = page.locator('[id^="repay-form-"]').first();
      await expect(repayForm).toBeVisible();
      await repayForm.locator('input[name="amount"]').fill('500');
      await repayForm.locator('select[name="account_id"]').selectOption({ index: 1 });
      await repayForm.locator('button[type="submit"]').click();

      // Balance should be reduced
      await expect(page.locator('#people-list')).toContainText('500');
    });

    test('person detail page shows debt summary', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/people`);

      // Click person name link to go to detail
      await page.click('a:has-text("E2E Ali")');
      await expect(page.getByRole('heading', { name: 'E2E Ali' })).toBeVisible();

      // Should show transaction history
      await expect(page.getByText('Transaction History')).toBeVisible();
      await expect(page.getByText('Lent')).toBeVisible();
      await expect(page.getByText('Repayment')).toBeVisible();
    });

    test('Go session cookie authenticates on Django /people', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/people`);
      await expect(page.getByRole('heading', { name: /People/i })).toBeVisible();
    });

    test('JSON API /api/persons returns people', async ({ page }) => {
      const resp = await page.request.get(`${DJANGO_BASE_URL}/api/persons`);
      expect(resp.status()).toBe(200);
      const persons = await resp.json();
      expect(persons.length).toBeGreaterThan(0);
      expect(persons[0].name).toBe('E2E Ali');
    });
  });

  // ──────────────────────────────────────────────────
  // Group 8: Budgets (Phase 6)
  // ──────────────────────────────────────────────────

  test.describe('Budgets', () => {
    test('Django /budgets renders empty state', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/budgets`);
      await expect(page.getByRole('heading', { name: /Budgets/i })).toBeVisible();
      await expect(page.getByText('No budgets set')).toBeVisible();
    });

    test('Django /budgets shows category dropdown', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/budgets`);
      await expect(page.locator('select[name="category_id"]')).toBeVisible();
      await expect(page.locator('input[name="monthly_limit"]')).toBeVisible();
    });

    test('create budget via Django /budgets', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/budgets`);
      await page.selectOption('select[name="category_id"]', { index: 1 });
      await page.fill('input[name="monthly_limit"]', '5000');
      await page.click('button:has-text("Create Budget")');

      await page.waitForURL(`${DJANGO_BASE_URL}/budgets`);
      await expect(page.locator('main')).toContainText('5,000');
      await expect(page.locator('main')).toContainText('remaining');
    });

    test('budget shows progress bar', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/budgets`);
      await expect(page.locator('.bg-gray-100.rounded-full').first()).toBeVisible();
    });

    test('delete budget via Django /budgets', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/budgets`);
      await page.locator('form[action*="/budgets/"] button:has-text("Delete")').first().click();
      await page.waitForURL(`${DJANGO_BASE_URL}/budgets`);
      await expect(page.getByText('No budgets set')).toBeVisible();
    });

    test('Go session cookie authenticates on Django /budgets', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/budgets`);
      await expect(page.getByRole('heading', { name: /Budgets/i })).toBeVisible();
    });
  });
});
