# The phone-width gate — every route works at 390×844

Owner decision, 2026-09-15: **everything works at phone width in all four
products.** Not "degrades gracefully", not "is monitored" — works.

`check-phone-width.mjs` is the fleet's single definition of what that means,
so seed, stem, niac-go and trellis cannot each drift their own. A repo adopts
it by calling `.github/workflows/phone-width.yml`; nothing runs until it does.

## What a route must satisfy

Always:

- No element leaves the 390 px viewport. Per element, not per document —
  see below.
- The document does not scroll horizontally. A cheap second signal; on its
  own it is not enough.
- `data-testid="page-header-title"` is visible. All four products already
  render it. Configurable.

When the caller names the test id:

- The navigation rail is collapsed or in a drawer — a visible rail may be at
  most `rail-max-width` (72) px wide.
- The primary action is inside the viewport or one scroll below it. A route
  that has no such element is not failed for it.

### Why per element, and not `scrollWidth`

A shell built on `h-screen` + `overflow-hidden` **clips** an over-wide child.
`document.documentElement.scrollWidth` then reads 390 on a page whose content
is unreachable, so a document-level check passes on the defect — trellis
UI-TRL-2 shipped with exactly that, and its own "no horizontal scroll"
acceptance was vacuous. The fixture `clipped-overflow.html` reproduces it,
and the gate reports only the element message on that page:

```text
  FAIL  /clipped-overflow
          element leaves the 390px viewport: div.card (x 72..712)
```

### What is not a defect

A wide data table inside a horizontally scrolling region is a design choice —
but it has to say so. Put `data-phone-width-exempt` on the scroll container,
and everything inside it is skipped:

```html
<div class="overflow-x-auto" data-phone-width-exempt>
  <table>…</table>
</div>
```

The gate does **not** infer this from computed style, and the first draft that
did was unusable. CSS forces `overflow-x` to `auto` whenever `overflow-y` is
set and `overflow-x` is `visible`, so every `overflow-y-auto` page body in the
fleet computes as a horizontal scroller — the inference exempted the whole page
body on the very shells this gate exists to check, and the fixtures passed
while nothing was being checked. An attribute an author writes is the only
signal that means what it says.

Reach for it rarely, and say in the markup why.

## Running it by hand

```bash
cd scripts/phone-width && npm ci && npx playwright install chromium && cd ../..
NODE_PATH=scripts/phone-width/node_modules \
  node scripts/phone-width/check-phone-width.mjs \
  --routes '["/","/settings"]' --serve internal/api/ui --rail-testid app-rail
```

Pass `--base-url` instead of `--serve` to check an app that is already
running, and `--storage-state` to hand it a Playwright session.

Which of the two a repo uses is not a preference. seed, stem and niac-go gate
every route behind a session, so a statically served build answers each one
with the login screen and the gate would report a missing page header on all of
them; those repos pass `base-url` and `start-command` and let the workflow boot
the daemon their Playwright suite already uses. A UI that renders without a
backend can take the static serve.

## Adopting it in a product repo

```yaml
  phone-width:
    permissions:
      contents: read
      id-token: write
    uses: MustardSeedNetworks/.github/.github/workflows/phone-width.yml@<sha>
    with:
      dist-dir: internal/api/ui
      routes: '["/", "/settings"]'
      rail-testid: app-rail
```

Behind authentication:

```yaml
    with:
      base-url: https://127.0.0.1:8443
      start-command: make run-e2e-daemon
      storage-state: ui/.auth/state.json
      routes: '["/", "/settings"]'
```

Add `phone-width` to `ci-complete`'s `needs:` so it can block a merge. Derive
`routes` from the repo's own `pageRegistry` — the four products do not expose
it at one path, which is why the workflow takes the list rather than guessing.

`id-token: write` is not optional: it is how the workflow learns which commit
of itself is running, so the rules ride the SHA the caller pinned
(`.github#73`).

## Changing the rules

`node scripts/test-check-phone-width.mjs` pins every verdict and runs in this
repo's CI. A new rule needs a fixture that fails without it.
