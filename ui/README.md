# Shared UI components

The page-body half of the four product UIs (`seed`, `stem`, `niac-go`,
`trellis`). The shell, the login and the colours already match; the audit of
2026-11-22 found the bodies did not: four table patterns, nested versus flat
cards at different radii, no shared empty state, three styles of destructive
action, Help as a modal in one product and a drawer in the others, a toggle with
no visible track in dark mode. The owner's rule is that page bodies are fully
harmonised, so each of these exists once, here.

This is not an npm package. It is the same mechanism as the theme file
([`theme/README.md`](theme/README.md), [#69](https://github.com/MustardSeedNetworks/.github/issues/69)):
one canonical copy in this repo, byte-identical copies in each product, compared
by sha256 in CI. A product-local edit fails CI by construction.

| Canonical | Product copy |
| --- | --- |
| `ui/theme/msn-shared.css` | `ui/src/theme/msn-shared.css` |
| `ui/components/<name>.ts[x]` (tests included) | `ui/src/shared/<name>.ts[x]` |

Import from the file, not a barrel (the fleet's Biome config bans barrel files):
`import { PageHeader } from './shared/PageHeader'`.

## Using it

```sh
# in this repo, after changing anything under ui/
cd ui && npm ci && npm run typecheck && npm run lint && npm test
python3 scripts/ui_shared.py manifest           # rewrite ui/MANIFEST.sha256

# in each product, from a worktree of that product
python3 <path-to-.github>/scripts/ui_shared.py copy .
```

`copy` also deletes files in `ui/src/shared/` that are no longer canonical, then
verifies. Verification is by `ui/MANIFEST.sha256`, which CI here fails on when
stale (`ui_shared.py manifest --check`).

In a product's CI, `ci-conformance` (already called) verifies `ui/src/shared/`
against the pinned `.github` as soon as that directory exists; the theme keeps
its own rule. A product that has not copied the set yet is not checked, so a
change here never turns a product red before its adoption PR. The composite
action `.github/actions/ui-shared-verify` runs the full check, theme included,
for a `make` target or a separate job:

```yaml
- uses: MustardSeedNetworks/.github/.github/actions/ui-shared-verify@<sha>
```

## What each component is for

Strings arrive already translated (no i18n dependency). Colours are tokens from
`msn-shared.css`. Nothing imports a router, a store or a product module; the one
router seam is `renderLink`, which a product points at its own `Link`.

| Component | Use it for | Based on |
| --- | --- | --- |
| `PageHeader` | The one title block every page opens with: breadcrumbs, kicker, title, optional subtitle, readout, actions, inline help button. | seed `PageHeader` |
| `Breadcrumbs` | The trail above a header. `PageHeader` renders it; use directly only outside a page. | seed `PageHeader` (inner crumbs), a11y of seed `Breadcrumbs` |
| `EmptyState` | Nothing to show: icon, title, hint, one action. Neutral. | stem `ModuleEmptyState` |
| `DataTable` | Every table: sort, pagination, select-all, row actions, contained scroll. | niac `DataTable` |
| `Card` | A block of page content. Flat, one radius, one border. | the shared `.panel` class |
| `RightDrawer` | The one side panel. Help and Settings render inside it. | stem and niac drawers' focus handling |
| `SettingsTabs` | Settings sections inside a `RightDrawer`. | niac `SettingsDrawer` tabs |
| `Toggle` | An on/off setting. | stem `Toggle`, track reworked |
| `Select` | A choice from a short list. Native, themed. | seed `Select` |
| `Button` | `primary`, `secondary`, `destructive`, plus a disabled look. | niac `Button`, variants cut to three |
| `StatusPill` | A verdict in the status colours. | niac `StatusBadge` |
| `CategoryChip` | A neutral category label (device type, protocol, role). | new, from the audit |
| `FormField` | A label, one control, hint and error, capped width. | niac `FormField` |

`Help` and `Settings` content stay in the products; only the frame and the tabs
are shared. The theme store (OS default, persisted 3-way toggle in Settings plus
the rail-footer quick toggle, one store) is a product adoption item, not a
component here.

## Do and don't

**Page header.** Every page has exactly one, with a breadcrumb trail and a
kicker. The title equals the page's navigation label. The 76px header is what
three lines measure (a 10px kicker, a 24px title at `leading-tight`, a one-line
14px subtitle, 4px apart), so do not add padding, a `min-height` or a fourth
line. The help button sits on the title's line at 390px; do not move it into the
actions group, where it drops to its own row. A page with no help content passes
no `help`. `data-testid="page-header-title"` is what the phone-width gate looks
for; leave it.

**Cards.** Never nest a `Card` in a `Card`: it draws a grid of boxes and the
radii disagree. Inside a card, use a heading, a `border-t border-hairline`
divider or space. No shadows, no gradients, no per-card radius. A `DataTable` or
`EmptyState` goes inside a `Card` or stands alone; neither is a card.

**Empty states.** Say what is missing and what to do. Never green, never "All
clear" or "no problems": no data is not a verdict. One action at most. Do not
leave a blank 800px panel (trellis Coverage) or a strip that reads "No tests
running" (stem) where an `EmptyState` belongs; if a region has nothing to show
and nothing to do, drop the region.

**Tables.** One `DataTable`, not a CSS-grid list or a stack of buttons. Never let
a table widen the page: the scroll lives inside the frame at 390px. Do not fake
server paging by passing one page of rows; that is a different component.

**Buttons.** At most one `primary` per page. Every destructive action is the
filled `destructive` variant, never an outlined or text-only red, and is paired
with a confirmation. Disabled is visibly disabled; say why in a `title` or the
copy around it.

**Status versus category.** The status hues mean success, warning, error, info
or unknown, and only a `StatusPill` wears them. A device type, protocol or role
is a `CategoryChip`; niac's device-type pills used status colours for categories
(2026-11-22 audit), which makes a category read as a verdict.

**Forms.** Wrap every control in a `FormField`: it generates the id and wires the
label, hint and error. Fields are capped at 28rem (`lg` is 42rem); there is no
full-width option. Use `Select`, not a bare `<select>`, so the face and
chevron are themed. Use `Toggle`, not a bare checkbox, for on/off settings.

**Drawers.** Help and Settings are a right-hand `RightDrawer` in all four
products (owner, 2026-11-22), full width at 390px. Settings is `SettingsTabs`
inside it, with niac's sections as the reference; trellis gains Settings.

## Class vocabulary

jsdom never compiles Tailwind, so a class a product does not define renders as
nothing and every test still passes. These files therefore use only:

- raw Tailwind utilities;
- the shared theme's component classes `.kicker`, `.figure`, `.panel`,
  `.target` (never with a variant: Tailwind generates none for
  `@layer components`);
- colours from the token set every product maps. Trellis's `@theme` is the
  floor: `surface-*`, `text-*`, `status-*` (and `-strong`), `brand-primary`
  (and `-strong`), `brand-accent`, `on-brand`, `on-danger`, `hairline` (and
  `-strong`), `scrim`, `knob`.

Not allowed: product-local aliases (`bg-bg-surface`, `border-border-muted`),
spacing helpers and type classes from a product's own `index.css` (`gap-tight`,
`py-row-lg`, `mb-content`, `flex-between`, `heading-1`, `body-small`), and a bare
status-hue text colour on a status-hue wash (use `-strong`).
`tests/vocabulary.test.ts` enforces this on every component.

## What it does not do (yet)

Left out on purpose, so the first adopter knows what to ask for:

- `DataTable` has no virtual scrolling, row click, loading state or sticky
  header. niac's `DeviceTable` uses virtualization and its `ConversationList` and
  `PcapPacketList` use row click, so those need an upstream change before they
  migrate; a local fork is not an option, since the copy is hash-locked.
- `Button` has no loading state, ghost or icon-only variant, and no permission
  hook (niac's `action`); a product wraps it.
- `Select` reports the native change event; seed's `onChange(value)` callers
  adapt.

## Tests travel with the components

Each component's test file is copied with it, so the products' coverage ratchets
count them. They import from `vitest` explicitly, use `fireEvent` and clean up
after themselves, so they need no setup file, `globals` or `user-event`. The 390px
layout is asserted as classes (`flex-wrap`, `min-w-0`, `overflow-x-auto`,
`data-phone-width-exempt`), because jsdom has no layout; the phone-width gate
measures the real thing in each product.

## Toolchain

`ui/package.json` carries only what is needed to typecheck, lint and test the
components, at the versions the products already run (React 19.3.1, TypeScript
7.0.2, Vitest 5.0.5, Biome 2.6.4, `lucide-react` 1.73.0). It is a lockfile
install with `min-release-age=7`, like the other Node tools in this repo, so
Renovate can see and bump every pin. `biome.json` is seed's rule set, the
strictest of the four, so the copies pass in each product unchanged;
`tsconfig.json` carries the fleet's required flags and `exactOptionalPropertyTypes`
on top.
