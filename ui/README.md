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
| `DataTable` | Every table: sort (natural collation, configurable cycle), search, pagination, select-all (page or every row), row detail, row actions, row click, per-row test id and tone, skeleton loading, optional sticky header and virtualization, contained and keyboard-reachable scroll. | niac `DataTable`, `useVirtualScroll` |
| `Card`, `CardRow`, `CardValue`, `CardDivider` | A block of page content: header (title, subtitle, icon, action, status indicator), status bar, loading, error and empty bodies, rows, dividers, padding variants. Flat, one radius, one border. | the shared `.panel` class; seed `Card`, niac `Card`, `StatusCard`, `BaseCard` |
| `RightDrawer` | The one side panel. Help and Settings render inside it. | stem and niac drawers' focus handling |
| `SettingsTabs` | Settings and Help sections inside a `RightDrawer`; wraps, never scrolls. | niac `SettingsDrawer` tabs, niac `HelpTabs` |
| `Toggle` | An on/off setting. | stem `Toggle`, track reworked |
| `RadioGroup` | One choice from a few, as native radios in a labelled fieldset with a hint and a group error. | new, from stem's setup wizard and reflector profile |
| `RailFooter` | The bottom of the left rail, identical in all four products: status, one product control, Help, Settings, theme, sign-out, version, mark, collapse. | niac's `SidebarFooter` (see below) |
| `Select` | A choice from a short list, from an `options` array or JSX `<option>` children. Native, themed; `onValueChange(value)`. | seed `Select` |
| `Button`, `ButtonLink` | `primary`, `secondary`, `ghost`, `destructive`; `xs`, `sm`, `md`; `loading`; `disabledReason` (disabled but focusable, with the reason in a tooltip); icon-only (needs an `aria-label`); the same control as an `<a>` or a router link. | niac `Button`, `IconButton`, `LinkButton`; trellis `LinkButton` |
| `StatusPill`, `StatusIndicator` | A verdict in the status colours (`StatusPill`, optional glyph); the label-less round badge for a card header (`StatusIndicator`, with `loading`). | niac `StatusBadge` (pill), seed and niac `StatusBadge` (indicator) |
| `CategoryChip` | A neutral category label (device type, protocol, role). | new, from the audit |
| `FormField`, `FormSection`, `HelpIcon` | A label (any node, with an inline help accessory), one control, hint and error, capped width (`group`: a fieldset and legend with one group error); a titled group of fields; the "?" with a tooltip. | niac `FormField`, stem `FormSection`, `HelpIcon`, `FieldError` |
| `Input`, `Textarea`, `Checkbox` | Text, multi-line and tick controls, themed, inside a `FormField`. all pass `id`, `name`, `data-testid`, `aria-*` and `ref` through. | seed, stem, niac `Input`, `Textarea`, `Checkbox` |
| `SearchInput` | A filter box for a list or table. | seed, stem, niac `SearchInput` |
| `SegmentedControl` | One of two to five options that change a view in place. | niac and trellis `aria-pressed` groups |
| `CollapsibleSection` | A foldable block: any title, count, status, read-only reason; uncontrolled or controlled. | seed, stem, niac `CollapsibleSection` |
| `Alert` | An inline message in a status tone, `md` or in-card `sm`. | seed, stem, niac `Alert` |
| `Tooltip` | Short text on hover and focus; hoverable, persistent and dismissable (WCAG 1.4.13); optional text; element or render-prop child. Portalled to `document.body`, flips and follows scroll. | all four `Tooltip`s |
| `Modal`, `ConfirmDialog`, `InputModal` | A blocking task of any size, the confirmation every destructive action gets, a one-field prompt. | seed, stem, niac `Modal`, `ConfirmModal`, `InputModal` |
| `Skeleton` | A loading placeholder: line, paragraph, block or circle. | seed and niac `Skeleton` |
| `documentTitle` | The one `<title>` format, "Label · Product". | the four products' own formats |

`Help` and `Settings` content stay in the products; only the frame and the tabs
are shared. The theme store (OS default, persisted 3-way toggle in Settings plus
the rail-footer quick toggle, one store) is a product adoption item, not a
component here.

## Do and don't

**Page header.** Every page has exactly one, with a breadcrumb trail and a
kicker. The title equals the page's navigation label. The header measures
**104px** with its breadcrumb row (trellis measured it; the 2026-09-17 density
pass's 76px is the three title lines alone, without the trail). Those three
lines are a 10px kicker, a 24px title at `leading-tight` and a one-line 14px
subtitle, 4px apart, so do not add padding, a `min-height` or a fourth line;
density ratchets should assert 104, not 76. The help button sits on the title's line at 390px; do not move it into the
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
a table widen the page: the scroll lives inside the frame at 390px. Show
`loading` with skeleton rows, not a bare "Loading". Use `virtualize` only for
hundreds of rows (rows then must stay one height). Do not fake server paging by
passing one page of rows; that is a different component.

**Buttons.** At most one `primary` per page. Every destructive action is the
filled `destructive` variant, never an outlined or text-only red, and goes
through a `ConfirmDialog`. An icon-only button needs an `aria-label` (the type
enforces it); put a `Tooltip` on it. Use `loading` for an action in flight. An action that navigates is a
`ButtonLink` (an `<a>`, or a router `Link` through `renderLink`), not a `Button`
wrapped in a link. Disabled is visibly disabled; say why with
`disabledReason`, which keeps the button focusable (`aria-disabled`) and shows the
reason in a `Tooltip`, or in the copy around it.

**Status versus category.** The status hues mean success, warning, error, info
or unknown, and only a `StatusPill` wears them. A device type, protocol or role
is a `CategoryChip`; niac's device-type pills used status colours for categories
(2026-11-22 audit), which makes a category read as a verdict.

**Forms.** Wrap every control in a `FormField`: it generates the id and wires the
label, hint and error. Fields are capped at 28rem (`lg` is 42rem); there is no
full-width option. Use `Select` (it reports `onValueChange(value)`, one way to
listen), not a bare `<select>`, so the face and chevron are themed; `Input`,
`Textarea` and `Checkbox` likewise. Use `Toggle`, not a bare checkbox, for on/off settings. A label that needs
explaining gets a `HelpIcon` in `labelAccessory`, never inside the `<label>`.
With react-hook-form, `{...register('name')}` spreads onto `Input`, `Select` and
`Textarea` (they pass `ref`, `name`, `onChange` and `onBlur` through); `Checkbox`
and `Toggle` go through `Controller`, whose `onChange` takes the boolean. Put the
message from `formState.errors` in the field's `error`.

**Drawers.** Help and Settings are a right-hand `RightDrawer` in all four
products (owner, 2026-11-22), full width at 390px. Settings is `SettingsTabs`
inside it, with niac's sections as the reference; trellis gains Settings.

**Titles.** The browser tab reads `Label · Product`, one format fleet-wide: the
page's navigation label (the same translated string as the `PageHeader` title and
the rail), a middle dot (U+00B7), the bare product name. "Devices · NIAC",
"History · Stem", "Surveys · Trellis", "Dashboard · Seed"; a page with no label of
its own (sign-in) is the product alone. Not `Label | Product` (screen readers
read the pipe aloud) and not Title Case drift between products. Build it with
`documentTitle(label, product)` so the format has one definition; the products'
current "Label · Seed", "Label | Stem", "page | NIAC" and "Page | Trellis" all
move to it.

**Tooltips.** The text must also be reachable without hover (the control's
`aria-label`, a hint, the surrounding copy): touch has no hover, and iOS taps do
not focus a button. The bubble is for explanation, not the only home of required
information. WCAG 1.4.13 is met by the component (hoverable, persistent,
dismissable with Escape); do not wrap one around something that opens a menu.

**Wrapping versus scrolling tabs.** `SettingsTabs` wraps. At 390px an 8-tab Help
drawer is three rows and every tab is on screen; a sideways scroller hides tabs
behind an affordance a person has to notice (niac review D1). Do not add a
scroll strip or an overflow menu for more tabs; fewer, shorter labels first.

## Rail footer

The rail footer is one component, `RailFooter`, fed props by each product. Owner
rule (2026-09-15): the shell is the rail and the page header; the status pill,
the theme toggle and the account live in the rail; Help opens the current page's
section; theme is the Settings 3-way control plus a rail-footer quick toggle on
one store. The 2026-11-25 review found four different footers; this is the one.

```text
 expanded (224px, and the 390px drawer)      collapsed (64px)
+-----------------------------------+       +------+
| (a) [* Online]                    |       |  *   |   status: a dot, tooltip
| (b) [icon  Profile        ⌄ ]     |       | icon |   ONE product control
| (c)  ?     ⚙     ☾     ⎋          |       |  ?   |   Help, Settings, Theme,
|                                   |       |  ⚙   |   Sign out (icons only,
|                                   |       |  ☾   |   aria-label + tooltip;
|                                   |       |  ⎋   |   sign-out only with auth)
| (d) v0.285.3                      |       |v0.285|   "v<semver>"
| (e) ◆ Mustard Seed Net…   (f) ‹   |       |  ◆   |   mark, then collapse
|                                   |       |  ›   |
+-----------------------------------+       +------+
```

Slots, in this order, always:

| Slot | Prop | Rule |
| --- | --- | --- |
| (a) status | `status: { tone, label }` | Optional. A `StatusPill` (niac Online; seed, stem and trellis daemon reachability). Collapsed it is a dot with a tooltip. Replaces the dot that sat on the product mark at the top of the rail. |
| (b) product control | `productSlot` | Optional, ONE. `{ label, value, icon }` plus either `onClick` (a plain button) or `options` + `selected` + `onSelect` (a menu button: `role="menu"` of `menuitemradio`, arrow keys, Escape, opens upward or beside the collapsed rail). stem's role switch, seed's profile, niac's session. It cannot be drawn any other way. |
| (c) actions | `help`, `settings`, `theme`, `signOut` | Icon-only buttons, fixed order, `{ label, onClick }`. `theme` also takes `isDark` (sun or moon) and its `label` names what a click does. `signOut` is passed only by a product with auth. No text links, no per-product icon rows. |
| (d) version | `version: { value, label }` | `formatVersion(value)`: "v<semver>". |
| (e) mark | `mark: { src, name }` | The vendored company glyph's URL and the wordmark; the wordmark goes when collapsed. |
| (f) collapse | `collapse` | Same row as the mark, right-aligned; a chevron that is the expand control when collapsed. Absent in the drawer. |

**Version format.** The visible line is `v<semver>`, never a commit or `-dirty`.
`git describe` output ("v0.285.3-31-gf4194afb-dirty") shows as "v0.285.3"; the
whole string is the tooltip (and the line is keyboard-focusable when there is a
tooltip). A prerelease tag (`-rc.1`) is part of the version and stays; a value
that is not semver ("dev") shows as it is. `formatVersion` lives in
`railVersion.ts`; import it from there if a product shows a version elsewhere.

`variant="drawer"` is the same footer in the 390px mobile drawer: always
expanded, same order, no collapse control. Strings arrive translated. Test ids
are fixed: `rail-footer`, `rail-status`, `rail-product-slot` (and `-menu`),
`rail-help`, `rail-settings`, `rail-theme`, `rail-sign-out`, `rail-version`,
`rail-mark`, `rail-collapse`. The footer does not own the rail's width,
scrolling or the product mark at the top; the rail must not clip it
(`overflow-hidden`), because the product menu opens beside the collapsed rail.

Based on niac's `SidebarFooter`: the one footer that was already a single
component with a collapsed mode, a version line, the company mark and an expand
control. seed's and stem's were the same shape with more rows; trellis's lacked
Help.

### Per-product footer migration

| Product | Passes | Deletes |
| --- | --- | --- |
| seed | `status` from `SidebarLayout`'s `status` (and drop the header dot); `productSlot` = the active profile (`options` = profiles, `onSelect` = `onProfileSwitch`); `help`, `settings`, `theme` (`toggleTheme`, `isDark`), `signOut` = `logout`; `version`; `mark`; `collapse`. | The local `SidebarFooter` and `FooterIconButton` in `Sidebar.tsx`, `RailControls.tsx`, `MsnMark.tsx`. "Manage Profiles" moves into Settings, and the Ethernet/Wi-Fi interface switch has no rail slot: it goes to the page that uses it (decision for the adoption PR). |
| stem | `status` from `RailStatus` (drop the header dot); `productSlot` = the Reflector / Test Master switch (`options`, `onSelect`); `help`, `settings`, `theme`, `signOut` = logout; `version`; `mark`; `collapse`. | `SidebarFooter` and `FooterIconButton` in `SidebarChrome.tsx`, `roleControl` on `SidebarLayout`, `MsnMark.tsx`. The refresh icon is not a rail action: it moves to the pages that have data to refresh. |
| niac | `status` = the connection state mapped to `success`/`warning`/`error`; `productSlot` = the session (`options` from `SessionSwitcher`'s list, or `onClick` opening it); `help`, `settings`, `theme`, `signOut` = `disconnectRuntimeAPI` (niac's disconnect is its sign-out); `version`; `mark`; `collapse`. | `RailControls.tsx`, `SidebarFooter` and `FooterIconButton` in `Sidebar.tsx`, the collapse chevron in `SidebarHeader`, `MsnMark.tsx`. |
| trellis | `status` from `useConnectionStatus`; no `productSlot`; `help` (new: opens the page's help), `settings`, `theme` (`useTheme`), `signOut` only when `useAuth().required`; `version`; `mark`; `collapse`; the `MobileNav` drawer renders `variant="drawer"`. | The inline version block, `SettingsButton`, `ThemeToggle`, `SignOutButton` and the collapse button in `Sidebar.tsx`, `MsnMark.tsx`. The "Theme: System" text goes: the 3-way control is in Settings. |

Specs that used `sidebar-help-button`, `sidebar-settings-button`, `theme-toggle`,
`rail-theme-toggle`, `rail-logout`, `disconnect`, `sidebar-expand` and
`sidebar-collapse` move to the `rail-*` ids above.

## Density specs and the help button's hit area

The `PageHeader` help button is 28px, with an `after:-inset-2` pseudo-element
that extends the touch target to 44px (WCAG 2.5.8). Because the pseudo-element is
absolutely positioned it reaches past the button's box, and a spec that walks
every element's bounding box, or `::after` geometry, and fails on anything that
leaves its parent, reports it. The button carries `data-touch-target-overflow`
for this. In a product's density or overflow spec, skip such elements and their
pseudo-elements:

```ts
const overflowing = elements.filter((el) => !el.closest('[data-touch-target-overflow]'));
// and when probing ::after, skip an element that carries the attribute
```

Only the hit area is exempt: the 28px button itself is still measured, and
`data-phone-width-exempt` (tables and nothing else) stays the marker for a
deliberate scroller. Do not add the attribute to anything else; if a new control
needs a larger target than its box, make the box larger.

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

## What it does not cover

Not here, so a product keeps its own until two products need it:

- `Combobox` (seed only), `Slider` (seed only), `InfoPopover` (niac only).
- niac's permission `action` on `Button`, `RequireScope` and the other gates:
  a product decides at the call site whether to render or disable a button.
- seed's and niac's `Tag`: use `StatusPill` when it states a verdict and
  `CategoryChip` when it names a category. Tag's colour schemes are what the
  audit found misused.
- `Toast`, `CommandPalette`, `Sidebar`, `StatusRollup`: the shell, already
  matched.
- A variable-height virtualised table (seed's discovery list measures each row
  and expands in place). `DataTable.virtualize` is fixed-height and refuses
  `expandable`. Use paging with `search`, `expandable` and `scope: 'all'` selection
  instead.
- A coloured solid button for success or info (seed's `tone="green"`/`"blue"`
  solid): the fleet has one primary, one secondary, one destructive.
- Gradients, blur and elevated card variants (niac's `elevated`, `outlined`): the
  fleet's cards are flat.

## Migration from the first set (1b2763fa)

Each change below is a re-copy and, where a prop moved, a mechanical edit. The
product adoption PRs (seed#3887, stem#2123, niac-go#3117, trellis#1083) need the
re-copy plus the items marked **edit**; everything else is additive.

| Component | Change | Action |
| --- | --- | --- |
| `Tooltip` | Hoverable bubble (no `pointer-events-none`), close delay, Escape swallowed; `text` optional; render-prop child; the wrapper is `display: contents`, no `inline-flex` span. | Delete seed's and niac's local `Tooltip`; calls are unchanged (`text`, `side`, render-prop `{aria-describedby, onClick}`). The `className` niac passes (`w-full`, `flex-1`) never applied to a `display: contents` wrapper: drop it. |
| `useDialog` | Focus in a layout effect; opener recovered from the click when focus is on the body (Safari); `returnFocusRef`; `tabindex="-1"` is not tabbable; an empty panel traps. | None. Delete the products' own "focus the opener" code (trellis) and un-`fixme` seed's "holds focus from the commit" e2e. `RightDrawer` and `Modal` accept `returnFocusRef`. |
| `PageHeader` | Help button takes focus on click; carries `data-touch-target-overflow`. | Honour the attribute in density specs (above); remove niac's `::after` special case. |
| `SettingsTabs` | Wraps instead of scrolling; no `-mb-px`; no `data-phone-width-exempt="tab-scroll"`; sticky from `sm` up. | Delete niac's `HelpTabs` (same props); remove the `tab-scroll` exemption from specs. |
| `DataTable` | Frame is `relative` and, while it scrolls, a focusable labelled group; sort buttons 24px; checkboxes 24px; `getRowProps`, `search`, `toolbar`, `expandable`, `sortCycle`, `onSortChange`, `collation`; `selection.scope: 'all'`. | Delete niac's `ContainedTable` and the `tabindex` patch. `labels.selectAll` is unchanged for page scope. Nullish sort values now sort last. |
| `Checkbox` | 24px box; `id`, `name`, `data-testid`, `aria-*`, `ref` reach the input; `label` is a ReactNode. | None. |
| `Toggle` | `id`, `name`, `data-testid`, `aria-*` reach the switch button; `label` is a ReactNode. | None. |
| `Card` | `children` optional; adds `subtitle`, `icon`, `status` + `statusLabel`, `tone`, `padding`, `loading`, `error`, `empty`, `onClick`, `liveRegion`, `headingLevel`; new `CardRow`, `CardValue`, `CardDivider`. | **edit** seed: `status`, `statusLabel` (the StatusBadge's `accessibility.status.*` string), `enableLiveRegion` becomes `liveRegion`, `ariaLabel` becomes `aria-label`, `Status` becomes `CardStatus`; `CardRow` and `CardValue` keep their props (`value` may now be a node). **edit** niac: `StatusCard` is `Card` with `status`; `Card variant="elevated"`, `outlined` and `ghost` all become the one flat card (no variants, no gradients), `hover` is implied by `onClick`; `CardContent` is the card itself (move its `className` to the `Card`, and stack children with `space-y-*`), `CardHeader` is `title` and `headerAction`; `BaseCard` is `Card loading error empty` plus a three-line `getStatus` mapping at the call site. |
| `Modal` | `closeOnBackdrop`, `closeOnEscape`, `showCloseButton`, `size` (`sm` to `full`), `header`, `footer`, `labelledBy`, `ariaLabel`, `returnFocusRef`; default size `lg`; body is focusable when it scrolls and holds nothing tabbable. | **edit** seed and niac: `isOpen` becomes `open`, `closeOnBackdropClick` becomes `closeOnBackdrop`, size `xl` becomes `lg` or `3xl`, `ModalHeader`, `ModalBody` and `ModalFooter` become `header`, children and `footer`; pass `size="md"` where the call relied on the old default; `closeLabel` is required. |
| `FormField` | `label` and `hint` accept nodes; `labelAccessory`; optional `id`; `children` may be a plain node. | **edit** niac: `htmlFor` becomes `id` (the control keeps the same id), `helpText` becomes `labelAccessory={<HelpIcon ... />}`. |
| `Input` | Documented `register()` use; every native attribute and `ref` pass through. | **edit** seed and niac: `label`, `error` and `hint` move to a wrapping `FormField`; `containerClassName` becomes the field's `className`. |
| `Select` | Native `onChange` passes through next to `onValueChange`. | **edit** niac: `onChange(value)` becomes `onValueChange(value)`. |
| `Button` | `xs` size; `buttonClass`; new `ButtonLink`. | **edit** seed: `variant="solid" tone="violet"` is `primary`, `tone="red"` is `destructive`, `outline` and `gray` are `secondary`, `leftIcon` is `icon`. niac and trellis: `LinkButton` is `ButtonLink` with `renderLink={(p) => <Link to={...} {...p} />}`. |
| `CollapsibleSection` | `title` is a node; `count`, `status` + `statusLabel`, `readOnlyReason`, `variant`, `open` + `onOpenChange`, `id`, `data-testid`. Default variant is now bordered (the old look is `compact`). | **edit** niac: `isExpanded` and `onToggle` become `open` and `onOpenChange`; its `required` chip is a `StatusPill` inside `title`. |
| `StatusPill` | `icon` prop; new `StatusIndicator`, `StatusIcon`, `statusText`, `IndicatorTone`. | seed and niac `StatusBadge` becomes `StatusIndicator` with a translated `label`. |
| `Skeleton` | `variant`, `width`, `height`, `lines`. | niac's `CardSkeleton`, `TableRowSkeleton`, `StatCardSkeleton` were unused outside stories: delete them. |
| `Alert` | `size="sm"`, `data-testid`. | seed's local `Alert` (`status`) is imported only by stories and one test now that the pages use the shared one: delete it. Its hand-rolled `role="alert"` blocks inside the dashboard cards become `<Alert tone="error" size="sm">`. `dismissLabel` is required with `onDismiss`. |
| New | `HelpIcon`, `FormSection`, `ButtonLink`, `StatusIndicator`, `documentTitle`. | Replace stem's `HelpIcon`, `FormSection`, `FieldError`; niac's `HelpTip`. |

## Migration from v2 (986e485c) to v3

A re-copy plus the **edit** items; the rest is additive. After the re-copy a
product can drop the `ui/src/shared/` skip in its file-size gate: no file under
it is over 600 lines any more (the longest is 435), so the products' own limit
now holds for the copies.

| Component | Change | Action |
| --- | --- | --- |
| `RailFooter`, `RailProductSlot`, `railVersion` | New. | See "Rail footer" above; delete each product's own footer. |
| `RadioGroup` | New: native radios in a fieldset, 24px targets, hint, group error, `name` required. | Use for stem's setup wizard and reflector profile instead of hand-built radios. |
| `FormField` | `group` renders a fieldset and legend; the error and hint attach to the fieldset (`aria-describedby`) and are announced. `labelAccessory` is ignored in a group. | Wrap a checkbox or radio group in `<FormField group label=...>`. |
| `Select` | `options` is optional and JSX `<option>` / `<optgroup>` children render after it; `children` is now allowed. | niac can build options in JSX: pass them as children. |
| `Tooltip` | Escape no longer races the render (below). | None. |
| `Card` | A clickable card is a plain `div` with a real `<button>` laid over it, not `<section role="button">`; passes axe's aria-allowed-role. The button is named by `aria-label`, else the title (one is required). `headerAction` stays clickable. | **edit** specs that focused the card via `tabindex` or sent Enter or Space to it: the overlay is a native button (`getByRole('button', { name })`). A clickable card with neither title nor `aria-label` needs one. |
| `Checkbox`, `Toggle` | `onClick` reaches the control (`Toggle` runs it before `onChange`); `hideLabel` keeps the label as the accessible name and hides it visually. | None. |
| `Modal` | `size="full"` is `h-full max-w-4xl`: as tall as the viewport allows, the body scrolls inside. | **edit** a call that used `full` for width only: use `3xl`. |
| `Button` | `disabledReason`: with `disabled`, the button is `aria-disabled` (focusable, click and Enter swallowed, so no form submit) and a Tooltip carries the reason. | Replace seed's `GatedButton` with `<Button disabled={!allowed} disabledReason={t(...)}>`; delete `GatedButton.tsx`. |
| `DataTable` | Split into `DataTable.tsx`, `DataTableTypes.ts`, `DataTableModel.ts`, `DataTableSort.ts`, `DataTableHead.tsx`, `DataTableRow.tsx`, `DataTableParts.tsx`, `DataTableStyles.ts`; tests into five files plus `DataTableTestUtils.tsx`. No API change: import `DataTable` and its types from `./shared/DataTable` as before. | Re-copy; drop the file-size skip. |

**The Tooltip Escape flake.** niac's "Escape dismisses tooltip" failed
intermittently under parallel workers. The cause was in the shared Tooltip, two
ways, both fixed:

1. The 120ms close timer reset `dismissed` when the pointer's grace period ended,
   even if focus was still on the trigger. A pointer that left within 120ms of an
   Escape brought the bubble back. `dismissed` now clears only when pointer and
   focus have both left.
2. The Escape listener was attached in an effect that ran after React rendered
   `open`. React renders a hover later than the pointer, so an Escape that
   arrived first found no listener. Hover and focus state now live in refs, and
   the listener is attached and removed by the same native events that set them,
   so it exists the moment the pointer or focus arrives.

`Tooltip.test.tsx` reproduces the first with fake timers (it fails on the old
code). The second is covered by a test that dispatches the events outside
`act()`; that one passes on the old code in jsdom, whose scheduler is too eager
to show the gap, so it is a guard, not a reproduction.

## Tests travel with the components

Each component's test file is copied with it, so the products' coverage ratchets
count them. They import from `vitest` explicitly, use `fireEvent` and clean up
after themselves, so they need no setup file, `globals` or `user-event`, and they
write nothing to the console: `ui/tests/strict-console.ts` (this repo only, not
copied) fails any test that logs, because stem's strict console hook turns an
`act()` warning in a copied test into a failed unit job (.github#288). The 390px
layout is asserted as classes (`flex-wrap`, `min-w-0`, `overflow-x-auto`,
`data-phone-width-exempt`), because jsdom has no layout; the phone-width gate
measures the real thing in each product.

## Toolchain

`ui/package.json` carries only what is needed to typecheck, lint and test the
components, at the exact versions it pins (React 19.3.1, TypeScript 7.0.2, Vitest
5.1.0, Biome 2.6.8, `lucide-react` 1.74.0; Node 26.13.1, npm 12.2.3). Read the
file, not this paragraph, for the current pin: Renovate moves it. It is a
lockfile install with `min-release-age=7`, like the other Node tools in this
repo, so Renovate can see and bump every pin. A product may run an older Biome
than this repo; the copies must format identically under both, so do not use a
construct whose layout changed between versions. `biome.json` is seed's rule set, the
strictest of the four, so the copies pass in each product unchanged;
`tsconfig.json` carries the fleet's required flags and `exactOptionalPropertyTypes`
on top.
