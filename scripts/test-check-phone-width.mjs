#!/usr/bin/env node
// Fixture tests for the phone-width gate. A gate that stops firing is worse
// than no gate, so each fixture pins one verdict: the conformant page passes,
// each defect page fails, and — the one that keeps the gate usable — the
// deliberate horizontal scroller passes.
//
// Run from the repo root: node scripts/test-check-phone-width.mjs

import { execFileSync } from 'node:child_process'
import process from 'node:process'
import { fileURLToPath } from 'node:url'
import { dirname, join, resolve } from 'node:path'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const checker = join(root, 'scripts/phone-width/check-phone-width.mjs')
const fixtures = join(root, 'test/fixtures/phone-width')

const CASES = [
  {
    name: 'a page that fits passes',
    routes: ['/'],
    expect: 'pass',
  },
  {
    name: 'a wide card clipped by an overflow-hidden shell fails, though the document never scrolls',
    routes: ['/clipped-overflow'],
    expect: 'fail',
    because: 'leaves the 390px viewport',
  },
  {
    name: 'a deliberate overflow-x:auto table passes',
    routes: ['/scrolling-table'],
    expect: 'pass',
  },
  {
    name: 'a route with no page header fails',
    routes: ['/no-header'],
    expect: 'fail',
    because: 'the page header is the route',
  },
  {
    name: 'a desktop-width rail fails',
    routes: ['/wide-rail'],
    expect: 'fail',
    because: 'navigation rail is 240px wide',
  },
  {
    name: 'one bad route fails a run of otherwise good ones',
    routes: ['/', '/scrolling-table', '/clipped-overflow'],
    expect: 'fail',
    because: '1 of 3 routes fail',
  },
]

function run(routes) {
  try {
    return {
      status: 0,
      output: execFileSync(
        process.execPath,
        [
          checker,
          '--routes', JSON.stringify(routes),
          '--serve', fixtures,
          '--rail-testid', 'app-rail',
          '--primary-action-testid', 'page-primary-action',
        ],
        { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] },
      ),
    }
  } catch (error) {
    if (error.status === undefined) throw error
    return { status: error.status, output: `${error.stdout ?? ''}${error.stderr ?? ''}` }
  }
}

let failed = 0
for (const testCase of CASES) {
  const { status, output } = run(testCase.routes)
  const passed = testCase.expect === 'pass' ? status === 0 : status === 1
  const explained = !testCase.because || output.includes(testCase.because)
  if (passed && explained) {
    process.stdout.write(`ok   ${testCase.name}\n`)
    continue
  }
  failed += 1
  process.stdout.write(`FAIL ${testCase.name}\n`)
  process.stdout.write(`       expected ${testCase.expect}, exit status ${status}\n`)
  if (!explained) process.stdout.write(`       expected the failure to mention "${testCase.because}"\n`)
  process.stdout.write(output.replace(/^/gm, '       | '))
}

process.stdout.write(`\n${CASES.length - failed}/${CASES.length} phone-width fixture cases pass.\n`)
process.exit(failed === 0 ? 0 : 1)
