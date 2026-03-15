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
    // FAB button to add institution should be visible
    await expect(page.locator('button[onclick="openCreateSheet()"]')).toBeVisible();
  });

  test('create institution via bottom sheet shows success toast', async ({ page }) => {
    await page.goto('/accounts');
    // Open the create institution bottom sheet
    await page.locator('button[onclick="openCreateSheet()"]').click();
    await expect(page.locator('#create-sheet-content form')).toBeVisible();

    // Fill the institution form
    await page.locator('#create-sheet-content input[name="name"]').fill('HSBC');
    await page.locator('#create-sheet-content select[name="type"]').selectOption('bank');
    await page.locator('#create-sheet-content button[type="submit"]').click();

    // Success toast should appear in the sheet
    await expect(page.locator('#create-sheet-content')).toContainText('Institution added!');
    // Institution list should update via OOB swap
    await expect(page.locator('#institution-list')).toContainText('HSBC');
  });

  test('create account shows success toast and updates list', async ({ page }) => {
    // Ensure institution exists via API
    const instId = await createInstitution(page, 'TestBank');

    await page.goto('/accounts');
    await expect(page.locator('#institution-list')).toContainText('TestBank');

    // Click "+ Account" button
    await page.click('button:has-text("+ Account")');
    await expect(page.locator('#account-form-area input[name="name"]')).toBeVisible();

    // Fill account form
    await page.fill('#account-form-area input[name="name"]', 'Checking');
    await page.selectOption('#account-form-area select[name="type"]', 'current');
    await page.selectOption('#account-form-area select[name="currency"]', 'EGP');
    await page.fill('#account-form-area input[name="initial_balance"]', '50000');
    await page.click('#account-form-area button[type="submit"]');

    // Success toast should appear in the form area
    await expect(page.locator('#account-form-area')).toContainText('Account added!');
    // Account should appear in institution list via OOB swap
    await expect(page.locator('#institution-list')).toContainText('Checking');
  });

  test('account form shows error for credit card without limit', async ({ page }) => {
    // Ensure institution exists via API
    await createInstitution(page, 'ErrorTestBank');

    await page.goto('/accounts');
    await page.click('button:has-text("+ Account")');
    await expect(page.locator('#account-form-area input[name="name"]')).toBeVisible();

    // Fill credit card without credit limit
    await page.fill('#account-form-area input[name="name"]', 'Bad Card');
    await page.selectOption('#account-form-area select[name="type"]', 'credit_card');
    // Deliberately skip filling credit_limit
    await page.click('#account-form-area button[type="submit"]');

    // Error message should appear in the form area
    await expect(page.locator('#account-form-area .bg-red-50')).toBeVisible();
    await expect(page.locator('#account-form-area')).toContainText('credit_limit is required');

    // The form should be re-rendered so user can fix and retry
    await expect(page.locator('#account-form-area input[name="name"]')).toBeVisible();

    // The account should NOT appear in the institution list
    await expect(page.locator('#institution-list')).not.toContainText('Bad Card');
  });

  test('account form error allows retry with fix', async ({ page }) => {
    // Ensure institution exists via API
    await createInstitution(page, 'RetryTestBank');

    await page.goto('/accounts');
    await page.click('button:has-text("+ Account")');

    // Submit credit card without limit → error
    await page.fill('#account-form-area input[name="name"]', 'Visa Gold');
    await page.selectOption('#account-form-area select[name="type"]', 'credit_card');
    await page.click('#account-form-area button[type="submit"]');
    await expect(page.locator('#account-form-area .bg-red-50')).toBeVisible();

    // Now fix: re-fill name, select type, fill credit limit, and resubmit
    await page.fill('#account-form-area input[name="name"]', 'Visa Gold');
    await page.selectOption('#account-form-area select[name="type"]', 'credit_card');
    await expect(page.locator('#credit-limit-field')).toBeVisible();
    await page.fill('#account-form-area input[name="credit_limit"]', '200000');
    await page.click('#account-form-area button[type="submit"]');

    // Should succeed now
    await expect(page.locator('#account-form-area')).toContainText('Account added!');
    await expect(page.locator('#institution-list')).toContainText('Visa Gold');
  });

  test('create credit card account shows credit limit field', async ({ page }) => {
    // Ensure institution exists via API
    await createInstitution(page, 'CCTestBank');

    await page.goto('/accounts');
    await page.click('button:has-text("+ Account")');

    // Select credit card type — credit limit field should appear
    await page.selectOption('#account-form-area select[name="type"]', 'credit_card');
    await expect(page.locator('#credit-limit-field')).toBeVisible();

    await page.fill('#account-form-area input[name="name"]', 'Mastercard');
    await page.fill('#account-form-area input[name="credit_limit"]', '300000');
    await page.click('#account-form-area button[type="submit"]');

    await expect(page.locator('#institution-list')).toContainText('Mastercard');
  });

  test('account detail page shows balance and info', async ({ page }) => {
    // Create institution and account via API
    const instId = await createInstitution(page, 'DetailBank');
    await createAccount(page, {
      name: 'DetailChecking',
      institution_id: instId,
      initial_balance: 10000,
    });

    await page.goto('/accounts');
    // Click on the account to go to detail
    await page.click('a:has-text("DetailChecking")');
    await expect(page.getByRole('heading', { name: 'DetailChecking' })).toBeVisible();
    await expect(page.locator('text=Current Balance')).toBeVisible();
  });

  test('dormant toggle works on account detail', async ({ page }) => {
    // Create institution and account via API
    const instId = await createInstitution(page, 'DormantBank');
    await createAccount(page, {
      name: 'DormantAccount',
      institution_id: instId,
      initial_balance: 5000,
    });

    await page.goto('/accounts');
    await page.click('a:has-text("DormantAccount")');
    // Click dormant toggle button — triggers HX-Redirect (full page reload)
    await page.locator('button:has-text("Dormant")').click();
    // Wait for page to reload after HTMX redirect
    await page.waitForURL(/\/accounts\//);
    // After toggling, the button text should change to "Active"
    await expect(page.locator('button:has-text("Active")')).toBeVisible();
  });

  test('create second institution (fintech)', async ({ page }) => {
    await page.goto('/accounts');
    // Open the create institution bottom sheet
    await page.locator('button[onclick="openCreateSheet()"]').click();
    await expect(page.locator('#create-sheet-content form')).toBeVisible();

    await page.locator('#create-sheet-content input[name="name"]').fill('Fawry');
    await page.locator('#create-sheet-content select[name="type"]').selectOption('fintech');
    await page.locator('#create-sheet-content button[type="submit"]').click();
    await expect(page.locator('#institution-list')).toContainText('Fawry');
  });

  test('success toast auto-dismisses', async ({ page }) => {
    // Ensure institution exists via API
    await createInstitution(page, 'ToastTestBank');

    await page.goto('/accounts');
    await page.click('button:has-text("+ Account")');

    await page.fill('#account-form-area input[name="name"]', 'Savings');
    await page.selectOption('#account-form-area select[name="type"]', 'savings');
    await page.click('#account-form-area button[type="submit"]');

    // Toast should appear
    await expect(page.locator('#account-form-area')).toContainText('Account added!');
    // After ~1.5s the toast should auto-dismiss (form area clears)
    await expect(page.locator('#account-form-area')).toBeEmpty({ timeout: 5000 });
  });

  test('delete institution via bottom sheet confirmation', async ({ page }) => {
    // Create institution with an account via API
    const instId = await createInstitution(page, 'DeleteMe');
    await createAccount(page, {
      name: 'DeleteAccount',
      institution_id: instId,
      initial_balance: 5000,
    });

    await page.goto('/accounts');
    await expect(page.locator('#institution-list')).toContainText('DeleteMe');

    // Click the trash icon on the institution card
    await page.locator(`#institution-${instId} button[title="Delete institution"]`).click();

    // Bottom sheet should slide up with confirmation content
    await expect(page.locator('#delete-sheet-content')).toContainText('Delete Institution');
    await expect(page.locator('#delete-sheet-content')).toContainText('DeleteMe');
    await expect(page.locator('#delete-sheet-content')).toContainText('1');

    // Delete button should be disabled until name is typed
    const deleteBtn = page.locator('#delete-confirm-btn');
    await expect(deleteBtn).toBeDisabled();

    // Type wrong name — button should stay disabled
    await page.fill('#delete-confirm-input', 'WrongName');
    await expect(deleteBtn).toBeDisabled();

    // Type correct name — button should enable
    await page.fill('#delete-confirm-input', 'DeleteMe');
    await expect(deleteBtn).toBeEnabled();

    // Click delete
    await deleteBtn.click();

    // Success message should appear
    await expect(page.locator('#delete-confirm-result')).toContainText('Institution deleted');

    // After sheet closes, institution should be gone from the list
    await expect(page.locator('#institution-list')).not.toContainText('DeleteMe', { timeout: 5000 });
  });

  test('delete institution sheet can be dismissed by cancel', async ({ page }) => {
    const instId = await createInstitution(page, 'KeepMe');

    await page.goto('/accounts');
    await page.locator(`#institution-${instId} button[title="Delete institution"]`).click();

    // Sheet should appear
    await expect(page.locator('#delete-sheet-content')).toContainText('Delete Institution');

    // Click cancel
    await page.locator('#delete-sheet-content button:has-text("Cancel")').click();

    // Sheet should be hidden (translate-y-full)
    await expect(page.locator('#delete-sheet')).toHaveClass(/translate-y-full/);

    // Institution should still be in the list
    await expect(page.locator('#institution-list')).toContainText('KeepMe');
  });

  test('dashboard shows net worth with accounts', async ({ page }) => {
    // Create institution and account via API
    const instId = await createInstitution(page, 'DashBank');
    await createAccount(page, {
      name: 'DashChecking',
      institution_id: instId,
      initial_balance: 50000,
    });

    await page.goto('/');
    await expect(page.locator('text=Net Worth')).toBeVisible();
    // Should show institution from the account
    await expect(page.locator('text=DashBank')).toBeVisible();
  });
});
