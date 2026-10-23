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

    // React 19 compatibility: controlled text inputs and validation survive a
    // render cycle without accidentally initiating network operations.
    await page.getByRole('button', { name: 'Analyze repository' }).click();
    await expect(page.getByText('Paste a public GitHub repository URL.')).toBeVisible();
    const repoUrl = page.getByPlaceholder('https://github.com/owner/repository');
    await repoUrl.fill('https://github.com/example/repository');
    await expect(repoUrl).toHaveValue('https://github.com/example/repository');
    await repoUrl.fill('');

    await page.locator('input[type=file]').setInputFiles(alpha);
    await expect(page.getByText('indexed files', { exact: false })).toBeVisible();

    // Exercise the actual architecture HTTP route against the explicitly
    // synthetic model fixture. This verifies UI state, NOT real model quality.
    await page.getByRole('button', { name: 'Explain architecture' }).click();
    await expect(page.locator('.panel.wide pre')).toContainText('Synthetic LLM answer');

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
    await expect(page.locator('.panel.wide pre')).toHaveCount(0);

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

test('GitHub URL form sends the entered URL and shows a remote-import failure', async ({ page }) => {
  // Intercept only the public GitHub import request. No external clone or
  // provider network traffic is exercised by this UI contract check.
  const input = 'https://github.com/octocat/Hello-World';
  let submitted = null;
  await page.route('**/api/analyze', async route => {
    submitted = route.request().postDataJSON();
    await route.fulfill({
      status: 422,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Offline fixture: repository clone not attempted' }),
    });
  });
  await page.goto('/');
  await page.getByPlaceholder('https://github.com/owner/repository').fill(input);
  await page.getByRole('button', { name: 'Analyze repository' }).click();
  await expect(page.locator('.error')).toContainText('Offline fixture: repository clone not attempted');
  expect(submitted).toEqual({ url: input });
  await expect(page.getByRole('button', { name: 'Analyze repository' })).toBeEnabled();
});

test('architecture panel consumes the local API with deterministic model fixture', async ({ page }) => {
  const dir = mkdtempSync(join(tmpdir(), 'repopilot-architecture-'));
  const archive = join(dir, 'architecture-fixture.zip');
  const python = process.env.REPOPILOT_PYTHON || 'python3';
  const script = [
    'import sys,zipfile',
    'with zipfile.ZipFile(sys.argv[1],"w") as z:',
    ' z.writestr("README.md","# Architecture test\\n")',
    ' z.writestr("src/entry.py","def entry():\\n    return 1\\n")',
  ].join('\n');
  try {
    execFileSync(python, ['-c', script, archive]);
    await page.goto('/');
    await page.locator('input[type=file]').setInputFiles(archive);
    await expect(page.getByText('indexed files', { exact: false })).toBeVisible();
    await page.getByRole('button', { name: 'Explain architecture' }).click();
    await expect(page.locator('.panel.wide pre')).toContainText('Synthetic LLM answer');
    await expect(page.locator('.panel.wide pre')).toContainText('not a real model output');
    await expect(page.getByRole('button', { name: 'Explain architecture' })).toBeEnabled();
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
