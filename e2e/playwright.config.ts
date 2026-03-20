import { defineConfig } from '@playwright/test';

const dbUrl = process.env.DATABASE_URL || 'postgres://clearmoney:clearmoney@localhost:5433/clearmoney?sslmode=disable';

export default defineConfig({
  testDir: './tests',
  timeout: 30_000,
  retries: 0,
  workers: 1, // serial execution — shared DB state
  use: {
    baseURL: 'http://localhost:8000',
    viewport: { width: 430, height: 932 },
    locale: 'en-US',
    serviceWorkers: 'block',
  },
  projects: [
    {
      name: 'chromium',
      use: { browserName: 'chromium' },
    },
  ],
  webServer: [
    {
      command: `cd ../backend && DATABASE_URL="${dbUrl}" DISABLE_RATE_LIMIT=true uv run python manage.py runserver 0.0.0.0:8000`,
      url: 'http://localhost:8000/healthz',
      reuseExistingServer: true,
      timeout: 15_000,
    },
  ],
});
