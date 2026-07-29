import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  reporter: [['json', { outputFile: 'result.json' }], ['list']],
});