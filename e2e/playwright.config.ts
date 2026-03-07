import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 30_000,
  retries: 0,
  workers: 1, // serial execution — shared DB state
  use: {
    baseURL: 'http://localhost:8080',
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
  webServer: {
    command: 'cd .. && DATABASE_URL="postgres://clearmoney:clearmoney@localhost:5433/clearmoney?sslmode=disable" go run ./cmd/server',
    url: 'http://localhost:8080/healthz',
    reuseExistingServer: true,
    timeout: 30_000,
  },
});
