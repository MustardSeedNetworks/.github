# Fleet lint policy

`golangci-lint` has no remote `extends`, so a shared config cannot be enforced
by the tool. These files let `check-ci-conformance.py` enforce it instead.

That script runs as a blocking gate in all four repos, via the reusable
`ci-conformance.yml` workflow (v1.3.0), called as a job inside each repo's
`ci.yml` and listed in `ci-complete`'s `needs:`. It runs the repo-local checks
only; the repo-settings and branch-protection checks need an admin-scoped token
and run on a schedule instead.

- **`golangci-linters-full.txt`** — the 77-linter set seed, stem and niac-go
  share. Verified byte-identical across all three by diffing every pair. It is
  an unmodified adoption of `maratori/golangci-lint-config`, so it is diffed
  against upstream rather than hand-maintained.

- **`golangci-linters-minimum.txt`** — the floor for younger repos. Trellis sits
  here: the `standard` preset plus the security and correctness linters whose
  absence is a real gap (gosec, bodyclose, errorlint, noctx, nilerr,
  rowserrcheck, sqlclosecheck), not a style preference.

A repo may ADD linters. Dropping below its tier fails conformance.

This exists because Trellis silently ran 5 linters with no `gosec` — no Go
security linting at all on a customer-facing product — and nothing detected it
until someone looked by hand.

## UI status vocabulary

`status-vocabulary.txt` defines the exact allowed TypeScript declarations.
Repeated names specify explicit alternatives, not unrestricted extensions.

The state layer (`RollupState`, with `RecordState` as its alias) supports the
four-state vocabulary `ok / warn / crit / unknown`. Products with an intentional
inactive state may opt into the same vocabulary plus `idle`, rendered neutrally.
Idle requires a successful observation confirming that no activity is running;
it must not imply healthy, hide an error, or stand in for loading or missing data.
Other products need no changes. Neither form may omit `unknown` or add other states.

The card-layer `Status` definition remains unchanged. Its `loading` lifecycle
state is distinct from an idle runtime and is never a successful rollup verdict.
