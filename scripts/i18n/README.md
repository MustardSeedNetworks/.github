# Shared i18n gate

The canonical copy of the i18n gate for `seed`, `stem` and `niac-go`. It was
maintained as three near-copies until 2026-08-24; every fix had to be applied
three times and they drifted anyway — including one defect that was fixed in
`stem` and never reached the other two, leaving the gate reporting findings and
exiting 0 in both.

## What is shared, and what is not

Shared here — the checks themselves, which carry no product knowledge:

| file | |
| --- | --- |
| `validate.sh` | the gate; orchestrates every check below |
| `check-keys.py` | `t()` / `<Trans i18nKey>` ↔ locale key cross-reference |
| `check-source.py` | hardcoded English JSX text |
| `semgrep-i18n.py` + `semgrep-i18n.yml` | banned `t('key', 'fallback')` forms |
| `test-check-keys.py` | self-test for the checker |

Owned by each product repo — the data the checks read:

`scripts/i18n/glossary.txt` · `banned-vocab.txt` · `glossary-exceptions.txt` ·
`dynamic-prefixes.txt` · the locale tree · the frontend source root.

## Interface

Every path is relative to the repo being checked. A repo on the standard
Go-embedded layout needs to set nothing.

| env var | default |
| --- | --- |
| `I18N_REPO_ROOT` | `$PWD` — the repo being checked |
| `LOCALES_DIR` | `internal/i18n/locales` |
| `UI_SRC_DIR` | `ui/src` |
| `GLOSSARY_FILE` | `scripts/i18n/glossary.txt` |
| `BANNED_FILE` | `scripts/i18n/banned-vocab.txt` |
| `GLOSSARY_EXCEPTIONS` | `scripts/i18n/glossary-exceptions.txt` |
| `DYNAMIC_PREFIXES` | `scripts/i18n/dynamic-prefixes.txt` |

## Using it from CI

```yaml
  i18n:
    name: i18n Validation
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<pinned>
      # Pinned by SHA with a version comment; Renovate bumps it.
      - uses: MustardSeedNetworks/.github/.github/actions/i18n-validate@<sha>
```

A composite action rather than a reusable workflow, so the scripts arrive with
the action checkout and the job stays in the calling repo — `ci-complete`'s
`needs: [i18n]` is unchanged, and a repo with extra i18n steps (niac runs an
extractor-drift check) keeps them in the same job.

## Using it locally

Losing the pre-push run would trade one problem for a slower one, so each repo
keeps a `scripts/i18n/validate.sh` shim — copy `validate-shim.sh`. It reads the
pinned SHA from that repo's own `ci.yml`, caches a checkout under
`~/.cache/msn-shared/<sha>`, and execs the shared script:

```bash
./scripts/i18n/validate.sh
```

There is exactly **one** pin per repo — the `uses:` line CI runs — so the local
run and CI cannot disagree. Renovate bumps it; the shim follows. Once a SHA is
cached the shim never touches the network.

## Drafting the Spanish for a new key

Key parity is a blocking check, so a missing `es` value is caught while the
author is still writing the change — and the cost lands on them as "now
hand-write Spanish for this". `es-fill.py` removes that friction by making the
translation memory, the glossary and the ES style guide the default rather than
a doc someone has to remember:

```bash
python3 scripts/i18n/es-fill.py            # report what is missing
python3 scripts/i18n/es-fill.py --write    # fill what it can
python3 scripts/i18n/es-fill.py --check    # exit 1 if fillable gaps remain
```

It fills two cases and refuses the third:

| case | behaviour |
| --- | --- |
| English matches the translation memory | translated from it |
| value is only glossary terms | copied verbatim |
| anything else | **reported, not invented** |

A novel sentence needs a translator. A tool that guessed would produce Spanish
nobody checked, which is worse than an obvious gap — so `--check` passes when
only human work remains, and fails only when a gap was mechanically fillable
and someone skipped the step.

**It never edits an existing Spanish value.** Filling a gap is mechanical and
has a right answer; revising reviewed copy is neither, and the two do not
belong in one tool. `test-es-fill.py` pins that guarantee.

`translation-memory.tsv` mirrors
`msn-docs-internal/05-Engineering/I18N_TRANSLATION_MEMORY.md` the way
`glossary.txt` mirrors the glossary doc — the docs repo is private and a shared
CI action cannot read it. Refresh it with `extract-translation-memory.py`.

## Adding a repo

Add the four data files and call the action. `trellis` is the next one.
