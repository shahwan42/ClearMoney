import { test, expect } from '@playwright/test';
import { resetDatabase, ensureAuth } from './helpers';

test.describe('Dark Mode & PWA (TASK-046, TASK-018)', () => {
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

  test('dark mode toggle exists on settings page', async ({ page }) => {
    await page.goto('/settings');
    await expect(page.locator('text=Dark Mode')).toBeVisible();
  });

  test('dark mode toggle adds dark class to html', async ({ page }) => {
    await page.goto('/settings');
    // Click the dark mode toggle button
    await page.click('button:has-text("Toggle")');

    // Check that <html> has class="dark"
    const htmlClass = await page.locator('html').getAttribute('class');
    expect(htmlClass).toContain('dark');

    // Toggle back
    await page.click('button:has-text("Toggle")');
    const htmlClassAfter = await page.locator('html').getAttribute('class');
    expect(htmlClassAfter || '').not.toContain('dark');
  });

  test('PWA manifest link exists in page head', async ({ page }) => {
    await page.goto('/');
    const manifest = await page.locator('link[rel="manifest"]');
    await expect(manifest).toHaveCount(1);
  });

  test('meta viewport is set for mobile', async ({ page }) => {
    await page.goto('/');
    const viewport = await page.locator('meta[name="viewport"]');
    await expect(viewport).toHaveCount(1);
  });
});
