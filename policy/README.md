# Fleet lint policy

`golangci-lint` has no remote `extends`, so a shared config cannot be enforced
by the tool. These files let `check-ci-conformance.py` enforce it instead.

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
