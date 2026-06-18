import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:5175',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: [
    {
      command: '..\\.venv\\Scripts\\python.exe ..\\backend\\e2e_server.py',
      url: 'http://127.0.0.1:8010/health',
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: 'corepack pnpm exec vite --host 127.0.0.1 --port 5175',
      url: 'http://127.0.0.1:5175/login',
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        VITE_API_BASE_URL: '/api',
        VITE_API_PROXY_TARGET: 'http://127.0.0.1:8010',
      },
    },
  ],
})
