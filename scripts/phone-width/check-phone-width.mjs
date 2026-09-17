#!/usr/bin/env node
// The fleet's phone-width gate: owner decision 2026-09-15 is that everything
// works at 390x844 in all four products, not that phone width is monitored.
//
// The assertion that matters is PER ELEMENT, not the document's scroll width.
// A shell built on `h-screen` + `overflow-hidden` CLIPS an over-wide child, so
// `document.documentElement.scrollWidth` reads 390 on a page whose content is
// unreachable -- trellis UI-TRL-2 shipped with exactly that, and its own "no
// horizontal scroll" acceptance passed on the defect. So this walks the tree
// and fails on any box whose edges leave the viewport, and keeps the document
// check only as a cheap second signal.
//
// Deliberately horizontal regions (a wide data table, a carousel) are not
// defects, but they must SAY SO: put `data-phone-width-exempt` on the scroll
// container. Computed style cannot tell one from a defect -- CSS forces
// `overflow-x` to `auto` whenever `overflow-y` is set and `overflow-x` is
// `visible`, so every `overflow-y-auto` page body in the fleet computes as a
// horizontal scroller, and inferring intent from that exempted the whole page
// body on the very shells this gate exists to check.

import { createServer } from 'node:http'
import { readFile } from 'node:fs/promises'
import { existsSync, statSync } from 'node:fs'
import { extname, join, normalize, resolve } from 'node:path'
import process from 'node:process'
import { chromium } from 'playwright'

const VIEWPORT = { width: 390, height: 844 }

// Sub-pixel layout rounding puts a full-bleed element at 390.0000001 often
// enough that a zero tolerance is noise rather than signal.
const EDGE_TOLERANCE_PX = 1

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.woff2': 'font/woff2',
  '.ico': 'image/x-icon',
}

function usage(message) {
  process.stderr.write(`${message}

usage: check-phone-width.mjs --routes '["/","/settings"]' (--serve <dir> | --base-url <url>)
                             [--page-header-testid <id>] [--rail-testid <id>]
                             [--rail-max-width <px>] [--primary-action-testid <id>]
                             [--storage-state <file>] [--settle-ms <n>]
                             [--header-timeout-ms <n>]

  --routes                 JSON array of route paths to visit. Required.
  --serve                  Serve this directory as a single-page app (unknown
                           paths fall back to index.html) and check against it.
  --base-url               Check against an app the caller is already serving.
  --page-header-testid     Must be visible on every route. Default page-header-title.
  --rail-testid            If given, the rail must be hidden or at most
                           --rail-max-width wide at 390 (collapsed or drawer-based).
  --rail-max-width         Default 72.
  --primary-action-testid  If given and present on a route, must be within the
                           viewport or one scroll of it.
  --storage-state          Playwright storageState JSON, for an app behind auth.
  --settle-ms              Extra settle time after load. Default 250.
  --header-timeout-ms      How long to wait for the page header. Default 10000.
`)
  process.exit(2)
}

function parseArgs(argv) {
  const args = {
    routes: null,
    serve: null,
    baseUrl: null,
    pageHeaderTestid: 'page-header-title',
    railTestid: null,
    railMaxWidth: 72,
    primaryActionTestid: null,
    storageState: null,
    settleMs: 250,
    headerTimeoutMs: 10000,
  }
  const keys = {
    '--routes': 'routes',
    '--serve': 'serve',
    '--base-url': 'baseUrl',
    '--page-header-testid': 'pageHeaderTestid',
    '--rail-testid': 'railTestid',
    '--rail-max-width': 'railMaxWidth',
    '--primary-action-testid': 'primaryActionTestid',
    '--storage-state': 'storageState',
    '--settle-ms': 'settleMs',
    '--header-timeout-ms': 'headerTimeoutMs',
  }
  for (let i = 0; i < argv.length; i += 2) {
    const key = keys[argv[i]]
    if (!key) usage(`unknown option ${argv[i]}`)
    if (argv[i + 1] === undefined) usage(`${argv[i]} needs a value`)
    args[key] = argv[i + 1]
  }
  if (!args.routes) usage('--routes is required')
  try {
    args.routes = JSON.parse(args.routes)
  } catch {
    usage('--routes must be a JSON array')
  }
  if (!Array.isArray(args.routes) || args.routes.length === 0) {
    usage('--routes must be a non-empty JSON array')
  }
  if (!args.serve === !args.baseUrl) usage('pass exactly one of --serve or --base-url')
  args.railMaxWidth = Number(args.railMaxWidth)
  args.settleMs = Number(args.settleMs)
  args.headerTimeoutMs = Number(args.headerTimeoutMs)
  // An empty string is how a workflow passes "not configured" for an optional
  // selector; treating it as a selector would match nothing and fail every route.
  for (const key of ['railTestid', 'primaryActionTestid', 'storageState']) {
    if (args[key] === '') args[key] = null
  }
  return args
}

async function serveSpa(root) {
  const base = resolve(root)
  const index = join(base, 'index.html')
  if (!existsSync(index)) throw new Error(`${base} has no index.html to serve`)

  const server = createServer(async (request, response) => {
    const path = decodeURIComponent(new URL(request.url, 'http://localhost').pathname)
    let file = join(base, normalize(path))
    if (!file.startsWith(base)) {
      response.writeHead(403).end('forbidden')
      return
    }
    if (!existsSync(file) || statSync(file).isDirectory()) {
      const asHtml = `${file.replace(/\/$/, '')}.html`
      file = existsSync(asHtml) ? asHtml : index
    }
    response.writeHead(200, { 'content-type': MIME[extname(file)] ?? 'application/octet-stream' })
    response.end(await readFile(file))
  })
  await new Promise((done) => server.listen(0, '127.0.0.1', done))
  return { server, baseUrl: `http://127.0.0.1:${server.address().port}` }
}

// Runs in the page. Returns every box that leaves the viewport horizontally,
// with enough identity to find it in the source.
const findOverflow = ({ width, tolerance }) => {
  const describe = (element) => {
    const id = element.id ? `#${element.id}` : ''
    const testid = element.getAttribute('data-testid')
    const classes =
      typeof element.className === 'string' && element.className
        ? `.${element.className.trim().split(/\s+/).slice(0, 3).join('.')}`
        : ''
    return `${element.tagName.toLowerCase()}${id}${testid ? `[data-testid="${testid}"]` : ''}${classes}`
  }

  const exempt = (element) => {
    for (let node = element; node && node !== document.documentElement; node = node.parentElement) {
      if (node.hasAttribute('data-phone-width-exempt')) return true
    }
    return false
  }

  const offenders = []
  for (const element of document.body.querySelectorAll('*')) {
    const style = getComputedStyle(element)
    if (style.display === 'none' || style.visibility === 'hidden') continue
    const rect = element.getBoundingClientRect()
    if (rect.width === 0 || rect.height === 0) continue
    if (rect.right <= width + tolerance && rect.left >= -tolerance) continue
    if (exempt(element)) continue
    offenders.push({
      element: describe(element),
      left: Math.round(rect.left),
      right: Math.round(rect.right),
    })
  }
  // A single over-wide container reports every descendant; the outermost box is
  // the one to fix, so keep the widest few rather than a wall of children.
  offenders.sort((a, b) => b.right - a.right || a.left - b.left)
  return {
    offenders: offenders.slice(0, 5),
    total: offenders.length,
    documentScrollWidth: document.documentElement.scrollWidth,
  }
}

async function checkRoute(page, baseUrl, route, args) {
  const failures = []
  // Not `networkidle`: a product daemon holding an SSE stream never goes idle,
  // so every route would time out instead of being judged. Wait for the page
  // header the route is asserted to have, and let its absence be reported as
  // the header failure below rather than as a crash.
  await page.goto(`${baseUrl}${route}`, { waitUntil: 'load' })
  await page
    .getByTestId(args.pageHeaderTestid)
    .first()
    .waitFor({ state: 'visible', timeout: args.headerTimeoutMs })
    .catch(() => {})
  await page.waitForTimeout(args.settleMs)

  const overflow = await page.evaluate(findOverflow, {
    width: VIEWPORT.width,
    tolerance: EDGE_TOLERANCE_PX,
  })
  for (const offender of overflow.offenders) {
    failures.push(
      `element leaves the 390px viewport: ${offender.element} (x ${offender.left}..${offender.right})`,
    )
  }
  if (overflow.total > overflow.offenders.length) {
    failures.push(`...and ${overflow.total - overflow.offenders.length} more overflowing elements`)
  }
  if (overflow.documentScrollWidth > VIEWPORT.width + EDGE_TOLERANCE_PX) {
    failures.push(`the document scrolls horizontally (scrollWidth ${overflow.documentScrollWidth})`)
  }

  const header = page.getByTestId(args.pageHeaderTestid).first()
  if (!(await header.isVisible().catch(() => false))) {
    failures.push(`no visible [data-testid="${args.pageHeaderTestid}"] — the page header is the route's title`)
  }

  if (args.railTestid) {
    const rail = page.getByTestId(args.railTestid).first()
    if (await rail.isVisible().catch(() => false)) {
      const box = await rail.boundingBox()
      if (box && box.width > args.railMaxWidth) {
        failures.push(
          `the navigation rail is ${Math.round(box.width)}px wide at 390 — collapse it or move it into a drawer (max ${args.railMaxWidth})`,
        )
      }
    }
  }

  if (args.primaryActionTestid) {
    const action = page.getByTestId(args.primaryActionTestid).first()
    if ((await action.count()) > 0) {
      const box = await action.boundingBox()
      // "within the viewport or reachable by one scroll" — one screen down.
      if (!box || box.y > VIEWPORT.height * 2 || box.x + box.width > VIEWPORT.width + EDGE_TOLERANCE_PX) {
        failures.push(
          `the primary action [data-testid="${args.primaryActionTestid}"] is not reachable within one scroll at 390x844`,
        )
      }
    }
  }

  return failures
}

async function main() {
  const args = parseArgs(process.argv.slice(2))
  const served = args.serve ? await serveSpa(args.serve) : null
  const baseUrl = (served?.baseUrl ?? args.baseUrl).replace(/\/$/, '')

  const browser = await chromium.launch()
  const context = await browser.newContext({
    viewport: VIEWPORT,
    deviceScaleFactor: 3,
    isMobile: true,
    hasTouch: true,
    ...(args.storageState ? { storageState: args.storageState } : {}),
  })
  const page = await context.newPage()

  let failed = 0
  for (const route of args.routes) {
    const failures = await checkRoute(page, baseUrl, route, args)
    if (failures.length === 0) {
      process.stdout.write(`  ok    ${route}\n`)
      continue
    }
    failed += 1
    process.stdout.write(`  FAIL  ${route}\n`)
    for (const failure of failures) process.stdout.write(`          ${failure}\n`)
  }

  await browser.close()
  served?.server.close()

  const total = args.routes.length
  if (failed > 0) {
    process.stdout.write(`\n${failed} of ${total} routes fail at 390x844.\n`)
    process.exit(1)
  }
  process.stdout.write(`\nAll ${total} routes work at 390x844.\n`)
}

await main()
