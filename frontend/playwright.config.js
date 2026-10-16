import { defineConfig } from '@playwright/test';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const frontend = dirname(fileURLToPath(import.meta.url));
const root = resolve(frontend, '..');

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: 'http://127.0.0.1:5173',
    browserName: 'chromium',
    ...(process.env.CI ? {} : { channel: 'chrome' }),
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: [
    {
      command: `${process.env.REPOPILOT_PYTHON || 'python3'} examples/serve_browser_demo.py`,
      cwd: root,
      env: { PYTHONPATH: 'backend' },
      url: 'http://127.0.0.1:8000/api/health',
      reuseExistingServer: false,
      timeout: 40_000,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1',
      cwd: frontend,
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: false,
      timeout: 40_000,
    },
  ],
});
