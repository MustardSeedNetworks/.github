# Conformance fixture

A minimal repo tree that satisfies every rule in
`scripts/check-ci-conformance.py`. `.github`'s own CI calls the reusable
`ci-conformance.yml` against this directory, so the gate that decides four
product repos is itself exercised on every pull request here.

Its second job is to prove the policy checkout honours the caller's pin: the
self-test asserts the workflow's `policy-sha` output equals the SHA it wrote in
`uses:`. See `.github#73`.

Nothing here is built or shipped. The workflow under `.github/workflows/` is
inert — GitHub only reads workflows from the repository root.
