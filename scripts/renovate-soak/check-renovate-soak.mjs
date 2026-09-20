#!/usr/bin/env node
// The fleet declares one supply-chain soak: `minimumReleaseAge` in
// default.json, which every UI repo's `ui/.npmrc` mirrors as
// `min-release-age=7`. The two MUST stay equal — npm refuses to *resolve* a
// version younger than its own cutoff, so a Renovate PR proposing one can
// never regenerate a lockfile and can never go green (.github#60).
//
// The declaration alone does not make it so. `config:best-practices` extends
// `security:minimumReleaseAgeNpm`, which sets the soak inside a *manager-
// scoped* `npm` object:
//
//   "npm": { "minimumReleaseAge": "3 days", "internalChecksFilter": "strict" }
//
// Manager-scoped config beats top-level config, so the fleet's top-level
// "7 days" applies to Go, Actions and pre-commit but is silently overridden
// to three days for npm — the one manager the `.npmrc` embargo covers.
// Nothing reported this: `renovate-config-validator` checks syntax, and the
// preset is resolved only inside Renovate.
//
// So this gate resolves the real preset chain and asserts the soak survives
// it. It fails if npm's effective soak is not the declared one, and if
// `internalChecksFilter` is not `strict` — without strict, Renovate raises
// the PR anyway and only marks the internal check pending.
//
// Run from the repo root, after `npm ci` in this directory:
//   node scripts/renovate-soak/check-renovate-soak.mjs [config.json]

import { readFileSync } from 'node:fs'
import process from 'node:process'

const configPath = process.argv[2] ?? 'default.json'
const { resolveConfigPresets } = await import(
  'renovate/dist/config/presets/index.js'
)

const resolved = await resolveConfigPresets(
  JSON.parse(readFileSync(configPath, 'utf8')),
)

const declared = resolved.minimumReleaseAge
const npmSoak = resolved.npm?.minimumReleaseAge
const npmFilter = resolved.npm?.internalChecksFilter

const failures = []

if (!declared) {
  failures.push(
    `${configPath} declares no top-level minimumReleaseAge; the fleet soak has to be stated somewhere`,
  )
} else if (npmSoak !== declared) {
  failures.push(
    `npm's effective minimumReleaseAge is ${JSON.stringify(npmSoak)}, not the declared ${JSON.stringify(declared)}.\n` +
      "  A preset is overriding it through the manager-scoped `npm` object.\n" +
      `  Restate it in ${configPath}: "npm": { "minimumReleaseAge": ${JSON.stringify(declared)} }`,
  )
}

if (npmFilter !== 'strict') {
  failures.push(
    `npm's effective internalChecksFilter is ${JSON.stringify(npmFilter)}, not "strict".\n` +
      '  Without strict, Renovate raises the PR and only marks the age check pending.',
  )
}

if (failures.length > 0) {
  console.error(`FAIL: the npm soak does not survive preset resolution (${configPath})`)
  for (const f of failures) console.error(`  - ${f}`)
  process.exit(1)
}

console.log(
  `OK: npm soak ${JSON.stringify(npmSoak)} matches the declared ${JSON.stringify(declared)}, internalChecksFilter "strict"`,
)
