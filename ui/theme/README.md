# Shared interface theme

`msn-shared.css` here is the canonical copy of the colour half of every
product's UI. Each UI repo (`seed`, `stem`, `niac-go`, `trellis`) keeps a
**byte-identical** copy at `ui/src/theme/msn-shared.css`, and the fleet
`ci-conformance` gate compares the two by sha256.

## Why a hash check

On 2026-09-15 the four copies were three different files
([.github#69](https://github.com/MustardSeedNetworks/.github/issues/69)):
`seed` and `niac-go` identical, `stem` carrying its own darker success green,
`trellis` carrying an extra typography block. Every repo was green the whole
time — a per-repo check cannot see a fleet-wide divergence — and all four
shipped a light-mode `--color-surface-border` at 1.45:1 against WCAG 1.4.11's
3:1 for a UI edge.

The comparison is by hash, not by token, on purpose: a semantic comparison
would let the comments explaining *why* a value is what it is drift apart, and
those comments are the only record of the measurements behind them.

## Changing a colour

1. Edit `ui/theme/msn-shared.css` here.
2. Copy it verbatim into all four repos' `ui/src/theme/msn-shared.css` in one
   lockstep change.

A product-local edit fails `ci-conformance` by construction. A repo with no
`ui/src` directory is out of scope.

## Scope

Colour tokens plus the small component layer built on them (`.kicker`,
`.figure`, `.panel`, `.target`). A product's own type scale is **not** here —
`seed`, `stem` and `niac-go` define `.heading-1`, `.body-small` and the
`.gap-*` helpers in their own `index.css`, and `trellis` should too.

## Product hues (set C, owner 2026-09-15)

These are **not** in the shared file: each repo sets them in its own
`ui/src/theme/product-<name>.css`, because the brand anchor is the one thing
the products do not share. They are published here so the four stay one
family. Each dark value is at least 4.5:1 on the dark page ground `#181611`.

| Product | Light | Dark |
| --- | --- | --- |
| `seed` | `#2f7d3a` | `#34b244` |
| `stem` | `#1565c0` | `#2d81e1` |
| `niac` | `#6a3fa8` | `#9569d3` |
| `trellis` | `#b94689` | `#cd5199` |

## Dark mode

Dark is the night version of the light theme, not a second palette (owner,
2026-09-15). It used to sit at 195–208° cold steel against a 44–50° warm-cream
light theme and shared only the status hues. Every surface and text token is
now derived at hue 43–51°, and every pair is measured: text 4.5:1 or better,
UI edges 3:1 or better.
