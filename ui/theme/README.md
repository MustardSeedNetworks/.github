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

The measurements themselves are no longer only comments. `scripts/check-theme-contrast.py`
enumerates every text-token × surface-token pair in both modes and fails under
4.5:1 for text (1.4.3) or 3:1 for a UI edge (1.4.11); this repo's CI runs it on
every change. It exists because of
[.github#74](https://github.com/MustardSeedNetworks/.github/issues/74): each
token's comment recorded its ratio "on base, on raised", so `surface-hover`,
`surface-sunken`, `surface-deep` and the rail were never measured, and **eleven
tokens sat under their floor on a surface nobody had looked at** — including
`--color-surface-border`, which #69 had just darkened *for* its 3:1 and which
measured 2.63:1 on hover in dark mode. A palette is only as measured as its
worst pair.

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
family.

| Product | Light | worst light | Dark | worst dark |
| --- | --- | --- | --- | --- |
| `seed` | `#2f7d3a` | 3.97 on sunken | `#34b244` | 4.91 on hover |
| `stem` | `#1565c0` | 4.47 on sunken | `#2d81e1` | 3.45 on hover |
| `niac` | `#6a3fa8` | 5.66 on sunken | `#9569d3` | 3.38 on hover |
| `trellis` | `#b94689` | 3.80 on sunken | `#cd5199` | 3.38 on hover |

**Six of those eight are under 4.5:1 as text on their worst surface.** This
table used to claim "each dark value is at least 4.5:1 on the dark page
ground", which was true and beside the point: the page ground is the *easiest*
surface, and the same token on a hovered row is a full point worse. The hues
are owner-approved (set C, 2026-09-15) and a brand anchor is not a thing a
driver re-picks, so they are recorded here as measured and left alone; the
decision is the owner's.

Until it is made, a product hue is safe as a fill, an icon or large text, and
not as small text on `surface-hover` or `surface-sunken`. Each repo can measure
its own file:

```sh
python3 scripts/check-theme-contrast.py --product ui/src/theme/product-<name>.css
```

## Dark mode

Dark is the night version of the light theme, not a second palette (owner,
2026-09-15). It used to sit at 195–208° cold steel against a 44–50° warm-cream
light theme and shared only the status hues. Every surface and text token is
now derived at hue 43–51°, and every pair is measured by the script above:
text 4.5:1 or better, UI edges 3:1 or better. Four dark tokens moved in #74 to
hold that on `surface-hover` — `text-muted`, `log-fatal`, `accent-gold` and
`surface-border` — each by the smallest same-hue lightness step that clears the
floor, so the approved character of the palette is unchanged.
