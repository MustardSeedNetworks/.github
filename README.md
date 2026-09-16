# MustardSeedNetworks — shared CI & automation infrastructure

The **one place** for cross-repo policy shared by `seed`, `stem`, and `niac-go`.
The goal: make a fleet-wide change by editing **one file here**, not three repos.

## What lives here

| File | Purpose |
|------|---------|
| `default.json` | Renovate policy preset. Repos extend it with `{ "extends": ["github>MustardSeedNetworks/.github"] }`. Edit dependency/lockstep policy here. |
| `.github/workflows/*.yml` (reusable) | Shared `workflow_call` CI gates, build, and release logic (added in Phase 3). Repos call them via `uses: MustardSeedNetworks/.github/.github/workflows/<name>.yml@<sha>`. |
| `.github/actions/*` (composite) | Shared job steps. Repos call them via `uses: MustardSeedNetworks/.github/.github/actions/<name>@<sha>`. |
| `profile/README.md` | The organization profile shown at <https://github.com/MustardSeedNetworks>. Logo lives beside it. |
| `SECURITY.md`, `CODE_OF_CONDUCT.md` | Org-wide defaults GitHub applies to every repo that has no file of its own. Product repos keep their own. |
| `ui/theme/msn-shared.css` | The canonical shared interface theme. Every UI repo keeps a byte-identical copy at `ui/src/theme/msn-shared.css`; `ci-conformance` compares them by sha256. See `ui/theme/README.md`. |
| `scripts/i18n/` | The fleet i18n gate — one canonical copy of the checks; each repo keeps only its own glossary, banned vocabulary and locales. See `scripts/i18n/README.md`. |

## Discipline

Share **undifferentiated plumbing** only (dependency versions, CI gates, build
contract, release pipeline, security-crypto policy). **Never** share product
code — product features and authz wrappers stay per-repo, each repo owning its
own implementation.

The shared interface theme is the one deliberate exception (owner, 2026-09-15).
It is undifferentiated by definition — the four products are meant to look like
one company — and keeping it per-repo is what let the copies drift into three
versions with every repo green. It is shared as a **checked file**, not as a
package: decision D6 (no shared TS package) stands, each repo still owns its
copy, and `ci-conformance` fails the copy that disagrees. The **brand** tokens
that make a product itself — `product-<name>.css` — stay per-repo.

See the remediation plan for the full rationale and the duplication scorecard.
