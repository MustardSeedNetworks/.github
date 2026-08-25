# MustardSeedNetworks — shared CI & automation infrastructure

The **one place** for cross-repo policy shared by `seed`, `stem`, and `niac-go`.
The goal: make a fleet-wide change by editing **one file here**, not three repos.

## What lives here

| File | Purpose |
|------|---------|
| `default.json` | Renovate policy preset. Repos extend it with `{ "extends": ["github>MustardSeedNetworks/.github"] }`. Edit dependency/lockstep policy here. |
| `.github/workflows/*.yml` (reusable) | Shared `workflow_call` CI gates, build, and release logic (added in Phase 3). Repos call them via `uses: MustardSeedNetworks/.github/.github/workflows/<name>.yml@<sha>`. |
| `.github/actions/*` (composite) | Shared job steps. Repos call them via `uses: MustardSeedNetworks/.github/.github/actions/<name>@<sha>`. |
| `scripts/i18n/` | The fleet i18n gate — one canonical copy of the checks; each repo keeps only its own glossary, banned vocabulary and locales. See `scripts/i18n/README.md`. |

## Discipline

Share **undifferentiated plumbing** only (dependency versions, CI gates, build
contract, release pipeline, security-crypto policy). **Never** share product
code — UI/brand tokens, product features, and authz wrappers stay per-repo,
each repo owning its own implementation.

See the remediation plan for the full rationale and the duplication scorecard.
