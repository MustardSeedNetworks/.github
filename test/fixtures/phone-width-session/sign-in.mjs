#!/usr/bin/env node
// The fixture's setup-command: sign in to server.mjs and save the session as a
// Playwright storageState, which is what each product's own sign-in step does
// before the gate visits a route.
//
// It drives the gate's own Playwright. The workflow puts that driver on
// NODE_PATH, which only require() consults, so a caller need not install a
// Playwright of its own, nor a browser build to match one.

import { createRequire } from 'node:module'
import process from 'node:process'

const { chromium } = createRequire(import.meta.url)('playwright')
const { BASE_URL: baseURL, STORAGE_STATE: path } = process.env
if (!baseURL || !path) {
  process.stderr.write('BASE_URL and STORAGE_STATE are required\n')
  process.exit(2)
}

const browser = await chromium.launch()
try {
  const context = await browser.newContext({ baseURL, ignoreHTTPSErrors: true })
  const response = await context.request.post('/sign-in')
  if (!response.ok()) throw new Error(`/sign-in returned ${response.status()}`)
  await context.storageState({ path })
} finally {
  await browser.close()
}
