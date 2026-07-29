import { test } from '@playwright/test';
import * as fs from 'fs';

// This isn't a real test — it's a one-time capture step.
// We navigate to the real page and save its actual HTML to a file,
// so our Python agent has real DOM to reason about instead of
// guessing blind.
test('Dump login page DOM for self-healing experiment', async ({ page }) => {
  await page.goto('https://rahulshettyacademy.com/loginpagePractise/');
  const html = await page.content();
  fs.writeFileSync('dom_snapshot.html', html);
  console.log('✅ Saved dom_snapshot.html');
});