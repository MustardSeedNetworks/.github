#!/usr/bin/env node
// The fleet declares one supply-chain soak: `minimumReleaseAge` in
// default.json, which every UI repo's `ui/.npmrc` mirrors as
// `min-release-age=7`. The two MUST stay equal — npm refuses to *resolve* a
// version younger than its own cutoff, so a Renovate PR proposing one can
// never regenerate a lockfile and can never go green (.github#60).
//
// The declaration alone does not make it so. `config:best-practices` extends
// `security:minimumReleaseAgeNpm`, and what that preset sets has moved: in
// Renovate 42 a manager-scoped `npm` object, in 44 a packageRule matching
// `datasource: npm`. A packageRule is applied per dependency after every
// config level, so it overrides the top-level soak and any `npm` object alike
// — and it also reaches the custom regex managers that read npm versions,
// such as the `biome.json` schema URL (.github#68). Reading the resolved
// top-level or `npm` value, which is what this gate did first, therefore
// reports seven days while the hosted app runs on three.
//
// So the gate resolves the real preset chain and then applies the package
// rules to one representative update per shape that matters, the way
// Renovate does for each dependency, and asserts the outcome:
//   - every npm-datasource update of a timestamped type carries the declared
//     soak with `internalChecksFilter: "strict"` (without strict Renovate
//     opens the PR anyway and only marks the age check pending);
//   - lock file maintenance does not — it has no release timestamp, so a soak
//     there means the update never arrives;
//   - the biome.json schema URL shares a group with the @biomejs/biome
//     package, so the two cannot land apart.
//
// Run from the repo root, after `npm ci` in this directory:
//   node scripts/renovate-soak/check-renovate-soak.mjs [config.json]

import { readFileSync } from 'node:fs'
import process from 'node:process'

const configPath = process.argv[2] ?? 'default.json'
const { resolveConfigPresets } = await import(
  'renovate/dist/config/presets/index.js'
)
const { applyPackageRules } = await import(
  'renovate/dist/util/package-rules/index.js'
)
const { mergeChildConfig } = await import('renovate/dist/config/utils.js')

const { config: resolved } = await resolveConfigPresets(
  JSON.parse(readFileSync(configPath, 'utf8')),
)

// Manager-scoped config is merged into the base before package rules run.
const effective = (update) =>
  applyPackageRules({
    ...mergeChildConfig(resolved, resolved[update.manager] ?? {}),
    ...update,
  })

const biome = { depName: '@biomejs/biome', packageName: '@biomejs/biome' }
const SOAKED = [
  { label: 'npm patch', manager: 'npm', datasource: 'npm', updateType: 'patch', ...biome },
  { label: 'npm minor', manager: 'npm', datasource: 'npm', updateType: 'minor', depName: 'fast-uri', packageName: 'fast-uri' },
  { label: 'npm major', manager: 'npm', datasource: 'npm', updateType: 'major', depName: 'lint-staged', packageName: 'lint-staged' },
  { label: 'biome.json schema URL (custom.regex)', manager: 'custom.regex', datasource: 'npm', updateType: 'patch', ...biome },
]

const declared = resolved.minimumReleaseAge
const failures = []

if (!declared) {
  failures.push(
    `${configPath} declares no top-level minimumReleaseAge; the fleet soak has to be stated somewhere`,
  )
} else {
  for (const update of SOAKED) {
    const got = await effective(update)
    if (got.minimumReleaseAge !== declared) {
      failures.push(
        `${update.label}: effective minimumReleaseAge is ${JSON.stringify(got.minimumReleaseAge)}, not the declared ${JSON.stringify(declared)}.\n` +
          '  A preset packageRule is overriding it. Restate it as a packageRule matching `datasource: npm`.',
      )
    }
    if (got.internalChecksFilter !== 'strict') {
      failures.push(
        `${update.label}: effective internalChecksFilter is ${JSON.stringify(got.internalChecksFilter)}, not "strict".\n` +
          '  Without strict, Renovate raises the PR and only marks the age check pending.',
      )
    }
  }
}

const lockFile = await effective({
  manager: 'npm',
  datasource: 'npm',
  updateType: 'lockFileMaintenance',
  isLockFileMaintenance: true,
})
if (lockFile.minimumReleaseAge) {
  failures.push(
    `npm lockFileMaintenance carries a soak of ${JSON.stringify(lockFile.minimumReleaseAge)}; it has no release timestamp, so it would never be raised.\n` +
      '  Scope the soak rule with matchUpdateTypes.',
  )
}

const pkgGroup = (await effective(SOAKED[0])).groupName
const schemaGroup = (await effective(SOAKED[3])).groupName
if (!pkgGroup || pkgGroup !== schemaGroup) {
  failures.push(
    `the biome.json schema URL is not grouped with the @biomejs/biome package (package ${JSON.stringify(pkgGroup)}, schema ${JSON.stringify(schemaGroup)}).\n` +
      '  Grouped apart, the schema-only PR merges while the package waits and $schema runs ahead of the installed Biome.',
  )
}

if (failures.length > 0) {
  console.error(`FAIL: the npm soak does not survive preset resolution (${configPath})`)
  for (const f of failures) console.error(`  - ${f}`)
  process.exit(1)
}

console.log(
  `OK: ${SOAKED.length} npm-datasource updates soak ${JSON.stringify(declared)} with internalChecksFilter "strict"; lockFileMaintenance unsoaked; biome.json schema grouped with the package in ${JSON.stringify(pkgGroup)}`,
)
