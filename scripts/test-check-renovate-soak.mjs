#!/usr/bin/env node
// Fixture tests for the npm soak gate. The defect it exists to catch is
// invisible in the config file — the override arrives through a preset — so
// a gate that quietly stopped firing would look exactly like a healthy one.
// Each fixture pins one verdict, including both shapes default.json had while
// .github#60 was open: the bare top-level soak, and the manager-scoped `npm`
// restatement (.github#85) that a Renovate-42 resolver passed.
//
// Run from the repo root, after `npm ci` in scripts/renovate-soak:
//   node scripts/test-check-renovate-soak.mjs

import { spawnSync } from 'node:child_process'
import process from 'node:process'
import { fileURLToPath } from 'node:url'
import { dirname, join, resolve } from 'node:path'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const checker = join(root, 'scripts/renovate-soak/check-renovate-soak.mjs')
const fixtures = join(root, 'test/fixtures/renovate-soak')

const CASES = [
  {
    name: 'the real preset passes',
    config: join(root, 'default.json'),
    expect: 'pass',
  },
  {
    name: 'restating the soak as a datasource packageRule passes',
    config: join(fixtures, 'restated.json'),
    expect: 'pass',
  },
  {
    name: 'a soak declared only at the top level fails — config:best-practices overrides npm to three days',
    config: join(fixtures, 'inherited-three-days.json'),
    expect: 'fail',
    because: 'not the declared "7 days"',
  },
  {
    name: 'restating the soak under the npm manager object fails — the preset packageRule still wins (.github#85)',
    config: join(fixtures, 'manager-scoped-restatement.json'),
    expect: 'fail',
    because: 'biome.json schema URL (custom.regex): effective minimumReleaseAge is "3 days"',
  },
  {
    name: 'a relaxed internalChecksFilter fails',
    config: join(fixtures, 'filter-not-strict.json'),
    expect: 'fail',
    because: 'not "strict"',
  },
  {
    name: 'a soak that also covers lock file maintenance fails — it would never be raised',
    config: join(fixtures, 'soak-on-lockfile.json'),
    expect: 'fail',
    because: 'lockFileMaintenance carries a soak',
  },
  {
    name: 'a biome.json schema URL grouped apart from the package fails (.github#68)',
    config: join(fixtures, 'schema-ungrouped.json'),
    expect: 'fail',
    because: 'not grouped with the @biomejs/biome package',
  },
  {
    name: 'no declared soak fails rather than passing vacuously',
    config: join(fixtures, 'no-declared-soak.json'),
    expect: 'fail',
    because: 'declares no top-level minimumReleaseAge',
  },
]

let failed = 0

for (const c of CASES) {
  const run = spawnSync(process.execPath, [checker, c.config], {
    cwd: root,
    encoding: 'utf8',
  })
  const output = `${run.stdout}${run.stderr}`
  const verdict = run.status === 0 ? 'pass' : 'fail'
  const problems = []

  if (verdict !== c.expect) {
    problems.push(`expected the gate to ${c.expect}, it ${verdict}ed`)
  }
  if (c.because && !output.includes(c.because)) {
    problems.push(`expected the reason to name ${JSON.stringify(c.because)}`)
  }

  if (problems.length > 0) {
    failed += 1
    console.error(`FAIL  ${c.name}`)
    for (const p of problems) console.error(`      ${p}`)
    console.error(output.trim().replace(/^/gm, '      | '))
  } else {
    console.log(`ok    ${c.name}`)
  }
}

if (failed > 0) {
  console.error(`\n${failed} of ${CASES.length} soak-gate fixtures did not hold`)
  process.exit(1)
}

console.log(`\nall ${CASES.length} soak-gate fixtures hold`)
