#!/usr/bin/env node
// Resolves the fleet preset the way Renovate does and checks the grouping
// and post-upgrade behaviour the structural test cannot see: a later
// packageRule really does take the shared-workflow pins out of "github
// actions", and the opt-in generate preset really does attach its command.
//
// Run from the repo root, after `npm ci` in scripts/renovate-soak:
//   node scripts/renovate-soak/test-groups.mjs

import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..')

const { resolveConfigPresets } = await import('renovate/dist/config/presets/index.js')
const { applyPackageRules } = await import('renovate/dist/util/package-rules/index.js')
const { mergeChildConfig } = await import('renovate/dist/config/utils.js')

const failures = []

function fail(message) {
  failures.push(message)
}

const { config: resolved } = await resolveConfigPresets(
  JSON.parse(readFileSync(resolve(root, 'default.json'), 'utf8')),
)

const effective = (update) =>
  applyPackageRules({
    ...mergeChildConfig(resolved, resolved[update.manager] ?? {}),
    ...update,
  })

if (resolved.rebaseWhen !== 'conflicted') {
  fail(`resolved rebaseWhen is ${JSON.stringify(resolved.rebaseWhen)}, not "conflicted"`)
}

const behind = JSON.parse(readFileSync(resolve(root, 'presets/rebase-when-behind.json'), 'utf8'))
const optedIn = mergeChildConfig(resolved, behind)
if (optedIn.rebaseWhen !== 'behind-base-branch') {
  fail(
    `extending rebase-when-behind after the fleet preset left rebaseWhen ${JSON.stringify(optedIn.rebaseWhen)}`,
  )
}
const wrongOrder = mergeChildConfig(behind, resolved)
if (wrongOrder.rebaseWhen !== 'conflicted') {
  fail(
    `the fleet preset no longer overrides an earlier rebaseWhen (${JSON.stringify(wrongOrder.rebaseWhen)}); the opt-in must be listed after it`,
  )
}
if (resolved.timezone !== 'America/New_York') {
  fail(`resolved timezone is ${JSON.stringify(resolved.timezone)}`)
}
if (JSON.stringify(resolved.schedule).includes('at any time')) {
  fail(`resolved schedule still contains "at any time": ${JSON.stringify(resolved.schedule)}`)
}

const shared = await effective({
  manager: 'github-actions',
  depName: 'MustardSeedNetworks/.github/.github/workflows/semgrep.yml',
  packageName: 'MustardSeedNetworks/.github/.github/workflows/semgrep.yml',
  datasource: 'github-tags',
  updateType: 'digest',
})
if (shared.groupName !== 'shared workflows' || shared.groupSlug !== 'shared-workflows') {
  fail(
    `a .github workflow pin grouped as ${JSON.stringify(shared.groupName)} / ${JSON.stringify(shared.groupSlug)}, not shared workflows`,
  )
}

const action = await effective({
  manager: 'github-actions',
  depName: 'MustardSeedNetworks/.github/.github/actions/apt-install',
  packageName: 'MustardSeedNetworks/.github/.github/actions/apt-install',
  datasource: 'github-tags',
  updateType: 'digest',
})
if (action.groupName !== 'shared workflows') {
  fail(`a .github composite action grouped as ${JSON.stringify(action.groupName)}`)
}

const checkout = await effective({
  manager: 'github-actions',
  depName: 'actions/checkout',
  packageName: 'actions/checkout',
  datasource: 'github-tags',
  updateType: 'digest',
})
if (checkout.groupName !== 'github actions') {
  fail(`actions/checkout grouped as ${JSON.stringify(checkout.groupName)}, not "github actions"`)
}

const { config: generate } = await resolveConfigPresets(
  JSON.parse(readFileSync(resolve(root, 'presets/post-upgrade-generate.json'), 'utf8')),
)
const generated = await applyPackageRules({
  ...generate,
  manager: 'regex',
  depName: 'github.com/bufbuild/buf/cmd/buf',
  packageName: 'github.com/bufbuild/buf/cmd/buf',
  datasource: 'go',
  updateType: 'minor',
})
const commands = generated.postUpgradeTasks?.commands ?? []
if (commands.join('\n') !== 'make generate generate-ts') {
  fail(`buf bump postUpgradeTasks are ${JSON.stringify(generated.postUpgradeTasks)}`)
}
if (generated.postUpgradeTasks?.executionMode !== 'branch') {
  fail(`postUpgradeTasks executionMode is ${JSON.stringify(generated.postUpgradeTasks?.executionMode)}`)
}

const connect = await applyPackageRules({
  ...generate,
  manager: 'npm',
  depName: '@connectrpc/connect',
  packageName: '@connectrpc/connect',
  datasource: 'npm',
  updateType: 'minor',
})
if ((connect.postUpgradeTasks?.commands ?? []).join('\n') !== 'make generate generate-ts') {
  fail(`@connectrpc/connect did not pick up the generate command: ${JSON.stringify(connect.postUpgradeTasks)}`)
}

const unrelated = await applyPackageRules({
  ...generate,
  manager: 'npm',
  depName: 'react',
  packageName: 'react',
  datasource: 'npm',
  updateType: 'patch',
})
if (unrelated.postUpgradeTasks?.commands?.length) {
  fail(`react picked up a generate command: ${JSON.stringify(unrelated.postUpgradeTasks)}`)
}

if (failures.length > 0) {
  console.error('FAIL: renovate grouping did not survive preset resolution')
  for (const message of failures) console.error(`  - ${message}`)
  process.exit(1)
}

console.log('OK: shared workflow pins group together; buf and Connect bumps carry make generate generate-ts')
