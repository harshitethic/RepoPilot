import { test, expect } from '@playwright/test';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';

test('real ZIP imports, searches and delayed AI response cannot cross repository switch', async ({ page }, testInfo) => {
  const dir = mkdtempSync(join(tmpdir(), 'repopilot-browser-'));
  const python = process.env.REPOPILOT_PYTHON || 'python3';
  const alpha = join(dir, 'alpha.zip'), beta = join(dir, 'beta.zip');
  const zipScript = [
    'import sys,zipfile',
    'for output,name in zip(sys.argv[1:3], ["alpha","beta"]):',
    ' with zipfile.ZipFile(output,"w") as z:',
    '  z.writestr("README.md",f"# {name} repository\\n")',
    '  z.writestr(f"src/{name}.py",f"def {name}_marker():\\n    return \'{name}_marker\'\\n")',
  ].join('\n');
  try {
    execFileSync(python, ['-c', zipScript, alpha, beta]);
    await page.goto('/');
    await expect(page.getByText('RepoPilot', { exact: true }).first()).toBeVisible();
    await page.locator('input[type=file]').setInputFiles(alpha);
    await expect(page.getByText('indexed files', { exact: false })).toBeVisible();

    await page.getByRole('button', { name: 'Code Search' }).click();
    await page.getByPlaceholder('Search functions, variables, routes, imports...').fill('alpha_marker');
    await page.getByRole('button', { name: 'Search', exact: true }).click();
    await expect(page.locator('.result').first()).toContainText('src/alpha.py');
    await expect(page.locator('.result').first()).toContainText('alpha_marker');

    // Call the actual FastAPI AI route but hold its HTTP reply at the browser
    // boundary. The application must ignore this reply after switching repos.
    let deliverDelayedAnswer;
    let captureResponse;
    const captured = new Promise(resolve => { captureResponse = resolve; });
    await page.route('**/api/ask', async route => {
      const fromRealBackend = await route.fetch();
      captureResponse(true);
      await new Promise(resolve => { deliverDelayedAnswer = resolve; });
      await route.fulfill({ response: fromRealBackend });
    });
    await page.getByRole('button', { name: 'Ask AI' }).click();
    await page.locator('textarea').fill('Where is DELAYED_ALPHA used?');
    const delayedResponse = page.waitForResponse(r => r.url().endsWith('/api/ask') && r.request().method() === 'POST');
    await page.getByRole('button', { name: 'Ask RepoPilot' }).click();
    await captured;
    await expect(page.getByText('Reading code...')).toBeVisible();

    await page.getByRole('button', { name: 'New repo' }).click({ force: true });
    await page.locator('input[type=file]').setInputFiles(beta);
    await expect(page.getByText('indexed files', { exact: false })).toBeVisible();

    await page.getByRole('button', { name: 'Code Search' }).click();
    await expect(page.locator('.result')).toHaveCount(0);
    await expect(page.getByPlaceholder('Search functions, variables, routes, imports...')).toHaveValue('');
    await page.getByPlaceholder('Search functions, variables, routes, imports...').fill('beta_marker');
    await page.getByRole('button', { name: 'Search', exact: true }).click();
    await expect(page.locator('.result').first()).toContainText('src/beta.py');
    await expect(page.locator('.result')).not.toContainText(['alpha_marker']);

    deliverDelayedAnswer();
    const stale = await delayedResponse;
    expect(stale.status()).toBe(200);
    expect((await stale.json()).answer).toContain('alpha_private_answer');
    await page.getByRole('button', { name: 'Ask AI' }).click();
    await expect(page.locator('.answer pre')).toHaveCount(0);
    await expect(page.getByText('File-aware answer appears here.')).toBeVisible();
    await expect(page.locator('textarea')).toHaveValue('');
    await expect(page.locator('.error')).toHaveCount(0);
    await page.screenshot({ path: testInfo.outputPath('repository-b-after-delayed-a.png'), fullPage: true });
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
