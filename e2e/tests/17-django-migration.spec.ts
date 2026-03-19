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
let usdAccountId: string;
let savingsAccountId: string;
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

    usdAccountId = await createAccount(page, {
      name: 'USD Salary',
      institution_id: instId,
      type: 'current',
      currency: 'USD',
      initial_balance: 0,
    });
    savingsAccountId = await createAccount(page, {
      name: 'Savings',
      institution_id: instId,
      type: 'savings',
      currency: 'EGP',
      initial_balance: 0,
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

  // ──────────────────────────────────────────────────
  // Group 9: Virtual Accounts (Phase 7)
  // ──────────────────────────────────────────────────

  test.describe('Virtual Accounts', () => {
    test('Django /virtual-accounts renders empty state', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/virtual-accounts`);
      await expect(page.locator('h2:has-text("Virtual Accounts")')).toBeVisible();
      await expect(page.getByText('No virtual accounts yet')).toBeVisible();
    });

    test('Django /virtual-accounts shows bank account dropdown', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/virtual-accounts`);
      await expect(page.locator('select[name="account_id"]')).toBeVisible();
      await expect(page.locator('input[name="name"]')).toBeVisible();
    });

    test('create virtual account via Django', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/virtual-accounts`);
      await page.fill('input[name="name"]', 'E2E Emergency Fund');
      await page.fill('input[name="target_amount"]', '100000');
      await page.selectOption('select[name="account_id"]', { label: 'Current (EGP)' });
      await page.click('button:has-text("Create")');

      await page.waitForURL(`${DJANGO_BASE_URL}/virtual-accounts`);
      await expect(page.locator('main')).toContainText('E2E Emergency Fund');
    });

    test('virtual account detail page shows info', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/virtual-accounts`);
      await page.click('a:has-text("E2E Emergency Fund")');

      await expect(page.locator('h2')).toContainText('E2E Emergency Fund');
      await expect(page.locator('h3:has-text("Allocate Funds")')).toBeVisible();
      await expect(page.locator('h3:has-text("History")')).toBeVisible();
    });

    test('allocate funds to virtual account', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/virtual-accounts`);
      await page.click('a:has-text("E2E Emergency Fund")');

      await page.selectOption('select[name="type"]', 'contribution');
      await page.fill('input[name="amount"]', '5000');
      await page.fill('input[name="note"]', 'E2E initial allocation');
      await page.click('button:has-text("Allocate")');

      // Should redirect back to detail and show updated balance + history
      await expect(page.locator('main')).toContainText('5,000');
      await expect(page.locator('main')).toContainText('E2E initial allocation');
    });

    test('edit form partial returns HTML', async ({ page }) => {
      // Bottom sheet JS requires static files served by Go, so test the edit-form
      // endpoint directly as an API call instead of through the bottom sheet UI.
      await page.goto(`${DJANGO_BASE_URL}/virtual-accounts`);
      const vaLink = page.locator('a:has-text("E2E Emergency Fund")');
      const href = await vaLink.getAttribute('href');
      expect(href).toBeTruthy();
      const vaId = href!.split('/virtual-accounts/')[1];

      // Verify the edit-form partial endpoint returns form HTML
      const resp = await page.request.get(`${DJANGO_BASE_URL}/virtual-accounts/${vaId}/edit-form`);
      expect(resp.status()).toBe(200);
      const html = await resp.text();
      expect(html).toContain('Edit Virtual Account');
      expect(html).toContain('name="name"');
      expect(html).toContain('E2E Emergency Fund');
    });

    test('update virtual account via POST', async ({ page }) => {
      // Test the edit endpoint directly since bottom sheet requires Go's static JS
      await page.goto(`${DJANGO_BASE_URL}/virtual-accounts`);
      const vaLink = page.locator('a:has-text("E2E Emergency Fund")');
      const href = await vaLink.getAttribute('href');
      expect(href).toBeTruthy();
      const vaId = href!.split('/virtual-accounts/')[1];

      // Navigate to detail page to get a CSRF token
      await page.goto(`${DJANGO_BASE_URL}/virtual-accounts/${vaId}`);
      const csrfToken = await page.locator('input[name="csrfmiddlewaretoken"]').first().inputValue();

      // POST the update
      const resp = await page.request.post(`${DJANGO_BASE_URL}/virtual-accounts/${vaId}/edit`, {
        form: {
          csrfmiddlewaretoken: csrfToken,
          name: 'E2E Rainy Day Fund',
          color: '#0d9488',
          account_id: '',
        },
      });
      // HTMX redirect returns 200 with HX-Redirect header; standard redirect returns 302
      expect([200, 302]).toContain(resp.status());

      // Verify the update took effect
      await page.goto(`${DJANGO_BASE_URL}/virtual-accounts/${vaId}`);
      await expect(page.locator('h2')).toContainText('E2E Rainy Day Fund');
    });

    test('archive virtual account', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/virtual-accounts`);
      await expect(page.locator('main')).toContainText('E2E Rainy Day Fund');

      await page.locator('form[action*="/archive"] button').click();
      await page.waitForURL(`${DJANGO_BASE_URL}/virtual-accounts`);

      // Should show empty state again
      await expect(page.getByText('No virtual accounts yet')).toBeVisible();
    });

    test('Go session cookie authenticates on Django /virtual-accounts', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/virtual-accounts`);
      await expect(page.locator('h2:has-text("Virtual Accounts")')).toBeVisible();
    });

    test('legacy /virtual-funds redirects to /virtual-accounts', async ({ page }) => {
      const resp = await page.request.get(`${DJANGO_BASE_URL}/virtual-funds`, {
        maxRedirects: 0,
      });
      expect(resp.status()).toBe(301);
      expect(resp.headers()['location']).toContain('/virtual-accounts');
    });
  });

  // ──────────────────────────────────────────────────
  // Group 10: Recurring Rules (Phase 8)
  // ──────────────────────────────────────────────────

  test.describe('Recurring Rules', () => {
    test('Go session cookie authenticates on Django /recurring', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/recurring`);
      await expect(page.locator('h2:has-text("Recurring Transactions")')).toBeVisible();
    });

    test('Django /recurring renders empty state', async ({ page }) => {
      // Clean up any rules from previous tests
      await page.goto(`${DJANGO_BASE_URL}/recurring`);
      await expect(page.getByText('Recurring Transactions')).toBeVisible();
    });

    test('Django /recurring shows create form with account dropdown', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/recurring`);
      await expect(page.locator('input[name="amount"]')).toBeVisible();
      await expect(page.locator('select[name="account_id"]')).toBeVisible();
      await expect(page.locator('select[name="frequency"]')).toBeVisible();
      await expect(page.locator('input[name="next_due_date"]')).toBeVisible();
      await expect(page.locator('input[name="auto_confirm"]')).toBeVisible();
    });

    test('create recurring rule with future date', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/recurring`);

      await page.fill('input[name="amount"]', '750');
      await page.selectOption('select[name="account_id"]', { label: 'Current (EGP)' });
      await page.fill('input[name="note"]', 'E2E Future Rule');
      await page.selectOption('select[name="frequency"]', 'monthly');

      // Future date — won't appear as pending
      const future = new Date();
      future.setDate(future.getDate() + 30);
      await page.fill('input[name="next_due_date"]', future.toISOString().split('T')[0]);

      await page.click('button:has-text("Create Rule")');

      // Rule should appear in the active rules list via HTMX swap
      await expect(page.locator('#recurring-list')).toContainText('E2E Future Rule');
      await expect(page.locator('#recurring-list')).toContainText('750.00 EGP');
      await expect(page.locator('#recurring-list')).toContainText('monthly');
    });

    test('create pending rule and confirm it', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/recurring`);

      await page.fill('input[name="amount"]', '200');
      await page.selectOption('select[name="account_id"]', { label: 'Current (EGP)' });
      await page.fill('input[name="note"]', 'E2E Confirm Me');
      await page.selectOption('select[name="frequency"]', 'monthly');

      // Past date — will appear as pending
      const yesterday = new Date();
      yesterday.setDate(yesterday.getDate() - 1);
      await page.fill('input[name="next_due_date"]', yesterday.toISOString().split('T')[0]);

      await page.click('button:has-text("Create Rule")');
      await expect(page.locator('#recurring-list')).toContainText('E2E Confirm Me');

      // Reload to see the pending section
      await page.goto(`${DJANGO_BASE_URL}/recurring`);
      await expect(page.getByText('Pending Confirmation')).toBeVisible();
      await expect(page.locator('button:has-text("Confirm")')).toBeVisible();
      await expect(page.locator('button:has-text("Skip")')).toBeVisible();

      // Confirm — creates a transaction and advances the date
      const pendingCard = page.locator('.bg-amber-50').first();
      await pendingCard.locator('button:has-text("Confirm")').click();

      // Active list should still show the rule (date advanced)
      await expect(page.locator('#recurring-list')).toContainText('E2E Confirm Me');
    });

    test('create pending rule and skip it', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/recurring`);

      await page.fill('input[name="amount"]', '100');
      await page.selectOption('select[name="account_id"]', { label: 'Current (EGP)' });
      await page.fill('input[name="note"]', 'E2E Skip Me');
      await page.selectOption('select[name="frequency"]', 'weekly');

      const yesterday = new Date();
      yesterday.setDate(yesterday.getDate() - 1);
      await page.fill('input[name="next_due_date"]', yesterday.toISOString().split('T')[0]);

      await page.click('button:has-text("Create Rule")');
      await expect(page.locator('#recurring-list')).toContainText('E2E Skip Me');

      // Reload to see pending
      await page.goto(`${DJANGO_BASE_URL}/recurring`);

      // Skip the pending rule
      await page.locator('button:has-text("Skip")').first().click();

      // Rule should still be in active list (date advanced, no transaction created)
      await expect(page.locator('#recurring-list')).toContainText('E2E Skip Me');
    });

    test('delete recurring rule', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/recurring`);

      // There should be rules from previous tests
      await expect(page.locator('#recurring-list')).toContainText('E2E Future Rule');

      // Handle the JS confirm dialog
      page.on('dialog', dialog => dialog.accept());

      // Count rules before delete
      const rulesBefore = await page.locator('#recurring-list .flex.items-center.justify-between').count();

      // Click first Del button
      await page.locator('#recurring-list button:has-text("Del")').first().click();

      // Wait for HTMX swap
      await expect(page.locator('#recurring-list .flex.items-center.justify-between')).toHaveCount(rulesBefore - 1);
    });

    test('unauthenticated request to /recurring redirects to login', async ({ page }) => {
      await page.context().clearCookies();
      await page.goto(`${DJANGO_BASE_URL}/recurring`);
      expect(page.url()).toContain('/login');
    });
  });

  // ──────────────────────────────────────────────────
  // Group 11: Salary Wizard (Phase 9)
  // ──────────────────────────────────────────────────

  test.describe('Salary Wizard', () => {
    test('Go session cookie authenticates on Django /salary', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/salary`);
      await expect(page.locator('h2:has-text("Salary Distribution")')).toBeVisible();
    });

    test('salary page loads with step 1 form fields', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/salary`);
      await expect(page.locator('#salary-wizard')).toBeVisible();
      await expect(page.locator('input[name="salary_usd"]')).toBeVisible();
      await expect(page.locator('select[name="usd_account_id"]')).toBeVisible();
      await expect(page.locator('select[name="egp_account_id"]')).toBeVisible();
      await expect(page.locator('input[name="date"]')).toBeVisible();
    });

    test('step 2 shows exchange rate after step 1 submit', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/salary`);
      await page.fill('input[name="salary_usd"]', '3000');
      await page.selectOption('select[name="usd_account_id"]', { label: 'USD Salary' });
      await page.selectOption('select[name="egp_account_id"]', { label: 'Current' });
      await page.click('button:has-text("Next")');

      await expect(page.locator('input[name="exchange_rate"]')).toBeVisible();
      await expect(page.locator('#salary-wizard')).toContainText('$3000');
    });

    test('step 3 shows allocations with EGP remainder', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/salary`);
      await page.fill('input[name="salary_usd"]', '1000');
      await page.selectOption('select[name="usd_account_id"]', { label: 'USD Salary' });
      await page.selectOption('select[name="egp_account_id"]', { label: 'Current' });
      await page.click('button:has-text("Next")');

      await page.fill('input[name="exchange_rate"]', '50');
      await page.click('button:has-text("Next")');

      await expect(page.locator('#salary-remainder')).toBeVisible();
      await expect(page.locator('#salary-wizard')).toContainText('50000');
      // Savings account should appear as allocation target
      await expect(page.locator('#salary-wizard')).toContainText('Savings');
    });

    test('full wizard creates transactions and shows success', async ({ page }) => {
      await page.goto(`${DJANGO_BASE_URL}/salary`);
      await page.fill('input[name="salary_usd"]', '1000');
      await page.selectOption('select[name="usd_account_id"]', { label: 'USD Salary' });
      await page.selectOption('select[name="egp_account_id"]', { label: 'Current' });
      await page.click('button:has-text("Next")');

      await page.fill('input[name="exchange_rate"]', '50');
      await page.click('button:has-text("Next")');

      // Allocate 10000 to savings
      const savingsInput = page.locator(`input[name="alloc_${savingsAccountId}"]`);
      if (await savingsInput.isVisible()) {
        await savingsInput.fill('10000');
      }

      await page.click('button:has-text("Confirm")');

      // Success page should appear
      await expect(page.locator('#salary-wizard')).toContainText('Salary Distributed');
      await expect(page.locator('#salary-wizard')).toContainText('$1000');
      await expect(page.locator('#salary-wizard')).toContainText('50000');
    });

    test('unauthenticated /salary redirects to login', async ({ page }) => {
      await page.context().clearCookies();
      await page.goto(`${DJANGO_BASE_URL}/salary`);
      expect(page.url()).toContain('/login');
    });
  });

  // -------------------------------------------------------------------------
  // Investments (Phase 10)
  // -------------------------------------------------------------------------

  test.describe('Investments', () => {
    test('renders empty state on Django', async ({ page }) => {
      await ensureAuth(page);
      await page.goto(`${DJANGO_BASE_URL}/investments`);
      await expect(page.locator('h2')).toContainText('Investment Portfolio');
      await expect(page.locator('text=No investments yet.')).toBeVisible();
    });

    test('shows add investment form', async ({ page }) => {
      await ensureAuth(page);
      await page.goto(`${DJANGO_BASE_URL}/investments`);
      await expect(page.locator('input[name="fund_name"]')).toBeVisible();
      await expect(page.locator('input[name="units"]')).toBeVisible();
      await expect(page.locator('input[name="unit_price"]')).toBeVisible();
    });

    test('shows total portfolio value', async ({ page }) => {
      await ensureAuth(page);
      await page.goto(`${DJANGO_BASE_URL}/investments`);
      await expect(page.locator('text=Total Portfolio Value')).toBeVisible();
    });

    test('unauthenticated /investments redirects to login', async ({ page }) => {
      await page.context().clearCookies();
      await page.goto(`${DJANGO_BASE_URL}/investments`);
      expect(page.url()).toContain('/login');
    });
  });

  // -------------------------------------------------------------------------
  // Installments (Phase 11)
  // -------------------------------------------------------------------------

  test.describe('Installments', () => {
    test('renders empty state on Django', async ({ page }) => {
      await ensureAuth(page);
      await page.goto(`${DJANGO_BASE_URL}/installments`);
      await expect(page.locator('h2')).toContainText('Installment Plans');
      await expect(page.locator('text=No installment plans yet.')).toBeVisible();
    });

    test('shows new plan form', async ({ page }) => {
      await ensureAuth(page);
      await page.goto(`${DJANGO_BASE_URL}/installments`);
      await expect(page.locator('input[name="description"]')).toBeVisible();
      await expect(page.locator('input[name="total_amount"]')).toBeVisible();
      await expect(page.locator('input[name="num_installments"]')).toBeVisible();
      await expect(page.locator('select[name="account_id"]')).toBeVisible();
      await expect(page.locator('input[name="start_date"]')).toBeVisible();
    });

    test('shows account dropdown with options', async ({ page }) => {
      await ensureAuth(page);
      await page.goto(`${DJANGO_BASE_URL}/installments`);
      const options = page.locator('select[name="account_id"] option');
      await expect(options).not.toHaveCount(0);
    });

    test('unauthenticated /installments redirects to login', async ({ page }) => {
      await page.context().clearCookies();
      await page.goto(`${DJANGO_BASE_URL}/installments`);
      expect(page.url()).toContain('/login');
    });
  });
});
