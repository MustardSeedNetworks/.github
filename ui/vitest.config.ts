import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    setupFiles: ['tests/strict-console.ts'],
    include: ['components/**/*.test.{ts,tsx}', 'tests/**/*.test.ts'],
  },
});
