import { test as base } from '@playwright/test';
import * as fs from 'fs';

// This is the same "custom fixtures" pattern your real work framework
// already uses. We're not replacing @playwright/test — we're wrapping
// it, so every test that imports from HERE instead of directly from
// '@playwright/test' automatically gets this extra behavior for free.
export const test = base.extend({});

// afterEach runs after EVERY test, pass or fail. testInfo tells us
// what actually happened. If the test didn't pass, we capture the
// LIVE page HTML right now — while the browser is still open on the
// exact failing state — instead of relying on a separate, stale,
// manually-run snapshot script.
test.afterEach(async ({ page }, testInfo) => {
  if (testInfo.status !== testInfo.expectedStatus) {
    const html = await page.content();

    // Name the file after the test itself, so with 150+ tests, each
    // failure gets its own snapshot instead of overwriting one shared file.
    const safeName = testInfo.title
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '_')
      .replace(/^_|_$/g, '');

    const filename = `dom_snapshot_${safeName}.html`;
    fs.writeFileSync(filename, html);
    console.log(`📸 Live DOM captured on failure: ${filename}`);
  }
});

export { expect } from '@playwright/test';