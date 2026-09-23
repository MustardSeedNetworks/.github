#!/usr/bin/env node
// Fixture tests for the phone-width gate. A gate that stops firing is worse
// than no gate, so each fixture pins one verdict: the conformant page passes,
// each defect page fails, and — the one that keeps the gate usable — the
// deliberate horizontal scroller passes.
//
// Run from the repo root: node scripts/test-check-phone-width.mjs

import { execFileSync, spawn } from 'node:child_process'
import { mkdtempSync, rmSync } from 'node:fs'
import { createServer } from 'node:net'
import { tmpdir } from 'node:os'
import process from 'node:process'
import { fileURLToPath } from 'node:url'
import { dirname, join, resolve } from 'node:path'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const checker = join(root, 'scripts/phone-width/check-phone-width.mjs')
const fixtures = join(root, 'test/fixtures/phone-width')
const sessionFixture = join(root, 'test/fixtures/phone-width-session')

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
    // Both boxes compute `overflow-x: auto` — the panel because its overflow-y
    // is set, the page body because it scrolls vertically. Nothing here is
    // declared exempt, so nothing here is excused.
    name: 'a panel pushed off the right edge fails, undeclared scrollers notwithstanding',
    routes: ['/offscreen-panel'],
    expect: 'fail',
    because: 'div.card',
  },
  {
    name: 'one bad route fails a run of otherwise good ones',
    routes: ['/', '/scrolling-table', '/clipped-overflow'],
    expect: 'fail',
    because: '1 of 3 routes fail',
  },
  {
    // Every product daemon serves HTTPS on a certificate it minted itself.
    name: 'a signed-in session on a self-signed HTTPS daemon passes',
    routes: ['/'],
    target: 'daemon-signed-in',
    expect: 'pass',
  },
  {
    // The reason a product needs setup-command: without a session every route
    // is the sign-in screen, and the gate must say so rather than pass it.
    name: 'the same daemon without a session fails on the sign-in screen',
    routes: ['/'],
    target: 'daemon',
    expect: 'fail',
    because: 'the page header is the route',
  },
]

async function freePort() {
  const server = createServer()
  await new Promise((done) => server.listen(0, '127.0.0.1', done))
  const { port } = server.address()
  await new Promise((done) => server.close(done))
  return port
}

// Boots the session fixture the way phone-width.yml boots a product: mint the
// certificate, start the daemon, wait for it to answer, then sign in.
async function startDaemon(scratch) {
  const tls = join(scratch, 'tls')
  execFileSync('sh', [join(sessionFixture, 'make-cert.sh'), tls])
  const port = await freePort()
  const baseUrl = `https://127.0.0.1:${port}`
  const child = spawn(process.execPath, [join(sessionFixture, 'server.mjs')], {
    env: { ...process.env, TLS_DIR: tls, PORT: String(port) },
    stdio: 'inherit',
  })
  const deadline = Date.now() + 10000
  for (;;) {
    try {
      execFileSync('curl', ['-ksSf', '-o', '/dev/null', baseUrl], { stdio: 'ignore' })
      break
    } catch {
      if (Date.now() > deadline) throw new Error(`${baseUrl} did not answer`)
      await new Promise((done) => setTimeout(done, 100))
    }
  }
  const storageState = join(scratch, 'state.json')
  execFileSync(process.execPath, [join(sessionFixture, 'sign-in.mjs')], {
    env: { ...process.env, BASE_URL: baseUrl, STORAGE_STATE: storageState },
    stdio: 'inherit',
  })
  return { child, baseUrl, storageState }
}

const scratch = mkdtempSync(join(tmpdir(), 'phone-width-'))
const daemon = await startDaemon(scratch)

function targetArgs(target) {
  switch (target) {
    case 'daemon':
      return ['--base-url', daemon.baseUrl]
    case 'daemon-signed-in':
      return ['--base-url', daemon.baseUrl, '--storage-state', daemon.storageState]
    default:
      return ['--serve', fixtures]
  }
}

function run(routes, target) {
  try {
    return {
      status: 0,
      output: execFileSync(
        process.execPath,
        [
          checker,
          '--routes', JSON.stringify(routes),
          ...targetArgs(target),
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
  const { status, output } = run(testCase.routes, testCase.target)
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

daemon.child.kill()
rmSync(scratch, { recursive: true, force: true })

process.stdout.write(`\n${CASES.length - failed}/${CASES.length} phone-width fixture cases pass.\n`)
process.exit(failed === 0 ? 0 : 1)
