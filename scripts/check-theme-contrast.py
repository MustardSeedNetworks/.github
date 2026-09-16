#!/usr/bin/env python3
"""Measure every colour pair the shared theme can actually produce.

The canonical palette shipped with `--color-text-muted` at 3.88:1 on
`--color-surface-hover` and `--color-surface-border` at 2.63:1 there
(.github#74). Neither was a wrong value so much as an unmeasured one: the
palette's comments record each token "on base, on raised", and the three
other surfaces — hover, sunken, deep — were never in the set. Nothing could
see it, exactly like the three drifted copies .github#69 found.

So this does not check the two pairs that were reported. It enumerates the
product of every text token and every surface token in both modes, which is
the set a component can compose, and fails on any pair under its floor:

    text        4.5:1   WCAG 2.2 AA, 1.4.3 (the palette carries 10px text
                        in .kicker, so the large-text 3:1 allowance never
                        applies to these tokens)
    UI edge     3.0:1   WCAG 2.2 AA, 1.4.11

A pair that genuinely cannot occur is exempt by name in EXEMPT with the
reason, so the exemption is reviewable in the diff. An exemption is not a
silenced finding — it is a claim that the composition does not exist.

Usage:
    check-theme-contrast.py [THEME]... [--product FILE]

With no argument it checks ui/theme/msn-shared.css. A product repo passes its
own product-<name>.css with --product: brand and category hues live there and
compose against these same surfaces, which is where the cat-N pill findings on
.github#74 came from.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TEXT_FLOOR = 4.5
EDGE_FLOOR = 3.0

# Surfaces anything can be painted on. rail-from/rail-to carry the navigation
# labels, so they are text grounds too.
SURFACES = [
    "surface-base",
    "surface-raised",
    "surface-hover",
    "surface-sunken",
    "surface-deep",
    "rail-from",
    "rail-to",
]

# The navigation rail holds labels and brand marks only. A log line or a
# status pill never renders there, so those roles are measured on the panel
# surfaces alone.
PANELS = [s for s in SURFACES if s.startswith("surface-")]

# Tokens used as text, each against the surfaces it can actually land on.
# The list is a claim about composition: widening it is how a pair gets
# measured, and narrowing it needs the reason written next to it.
TEXT_ROLES: dict[str, list[str]] = {
    "text-primary": SURFACES,
    "text-secondary": SURFACES,
    "text-muted": SURFACES,
    # Status text labels a row, a card or a pill — never a nav item.
    "status-success": PANELS,
    "status-warning": PANELS,
    "status-error": PANELS,
    "status-info": PANELS,
    # Log levels render only in the log viewer, which is a panel; its rows
    # hover, so surface-hover stays in the set.
    "log-trace": PANELS,
    "log-debug": PANELS,
    "log-info": PANELS,
    "log-warn": PANELS,
    "log-error": PANELS,
    "log-fatal": PANELS,
    # Eyebrows and accent icons, including .kicker at 10px.
    "accent-gold": SURFACES,
    # Product tokens, present only when --product is given.
    "brand-primary": SURFACES,
    "brand-accent": SURFACES,
    "text-accent": SURFACES,
}

# Boundaries that carry meaning: 1.4.11, not 1.4.3. A form control's edge IS
# the affordance, which is why surface-border was darkened in .github#69.
#
# Two tokens are deliberately NOT here:
#   --color-hairline / --color-hairline-strong  are decorative panel edges at
#     1.2-1.9:1 by design ("the eye counted containers instead of reading
#     content"). 1.4.11 covers components and meaningful graphics; a panel
#     boundary that conveys nothing the layout does not already convey is
#     outside it. Raising them would undo the decision they exist for.
#   --color-text-disabled  is an inactive control, which 1.4.3 and 1.4.11 both
#     exempt by name. It sits at 2.5-3.4:1 across the surfaces on purpose:
#     disabled must read AS disabled. Using it for live text is a product
#     defect, not a token one, and no gate here can see that.
EDGE_ROLES: dict[str, list[str]] = {
    "surface-border": PANELS,
}

# (mode, token, surface) -> why this composition cannot occur. Reviewed in the
# diff; each one is a design claim, not a waiver.
EXEMPT: dict[tuple[str, str, str], str] = {
    # text-inverse is defined to sit on a brand fill, never on a surface.
    # It is absent from TEXT_ROLES for that reason rather than listed here.
}


def srgb_to_linear(channel: int) -> float:
    c = channel / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def parse_colour(value: str) -> tuple[int, int, int, float] | None:
    """#rrggbb or rgba(r, g, b, a) -> (r, g, b, alpha). None if unsupported."""
    value = value.strip()
    if re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        return (int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16), 1.0)
    m = re.fullmatch(r"rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:[,/\s]+([\d.]+))?\s*\)", value)
    if m:
        r, g, b = (int(round(float(m.group(i)))) for i in (1, 2, 3))
        return (r, g, b, float(m.group(4)) if m.group(4) else 1.0)
    return None


def composite(fg: tuple[int, int, int, float], bg: tuple[int, int, int, float]) -> tuple[int, int, int, float]:
    """Source-over. A translucent hairline is only legible against its ground."""
    a = fg[3]
    return (*(round(fg[i] * a + bg[i] * (1 - a)) for i in range(3)), 1.0)


def luminance(colour: tuple[int, int, int, float]) -> float:
    r, g, b = (srgb_to_linear(c) for c in colour[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(fg: tuple[int, int, int, float], bg: tuple[int, int, int, float]) -> float:
    """WCAG 2.2 relative-luminance ratio, fg composited over bg first."""
    lf, lb = luminance(composite(fg, bg)), luminance(bg)
    hi, lo = max(lf, lb), min(lf, lb)
    return (hi + 0.05) / (lo + 0.05)


def palettes(paths: list[Path]) -> dict[str, dict[str, tuple[int, int, int, float]]]:
    """Read :root as light and .dark as dark, merging the files in order."""
    out: dict[str, dict[str, tuple[int, int, int, float]]] = {"light": {}, "dark": {}}
    for path in paths:
        css = path.read_text(encoding="utf-8")
        for selector, mode in ((r":root", "light"), (r"\.dark", "dark")):
            for body in re.findall(rf"(?:^|\n){selector}\s*\{{(.*?)\n\}}", css, re.S):
                for name, value in re.findall(r"(--color-[a-z0-9-]+)\s*:\s*([^;]+);", body):
                    parsed = parse_colour(value)
                    if parsed:
                        out[mode][name.removeprefix("--color-")] = parsed
    return out


def check(palette: dict[str, tuple[int, int, int, float]], mode: str) -> list[str]:
    findings = []
    for roles, floor, kind in ((TEXT_ROLES, TEXT_FLOOR, "text"), (EDGE_ROLES, EDGE_FLOOR, "UI edge")):
        for role, grounds in roles.items():
            fg = palette.get(role)
            if fg is None:
                continue
            for surface in grounds:
                bg = palette.get(surface)
                if bg is None:
                    continue
                if (mode, role, surface) in EXEMPT:
                    continue
                ratio = contrast(fg, bg)
                if ratio < floor:
                    findings.append(
                        f"{mode}: --color-{role} on --color-{surface} is "
                        f"{ratio:.2f}:1, under the {floor}:1 {kind} floor"
                    )
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("theme", nargs="*", type=Path, help="theme CSS (default: ui/theme/msn-shared.css)")
    ap.add_argument("--product", type=Path, action="append", default=[],
                    help="a product-<name>.css whose brand and category hues compose against these surfaces")
    ap.add_argument("--table", action="store_true", help="print every measured pair, not just findings")
    args = ap.parse_args()

    themes = args.theme or [Path("ui/theme/msn-shared.css")]
    missing = [p for p in [*themes, *args.product] if not p.exists()]
    if missing:
        for path in missing:
            print(f"✘ {path} does not exist", file=sys.stderr)
        return 2

    palette = palettes([*themes, *args.product])
    findings = []
    for mode in ("light", "dark"):
        if not palette[mode]:
            continue
        if args.table:
            print(f"\n=== {mode} ===")
            for role, grounds in (*TEXT_ROLES.items(), *EDGE_ROLES.items()):
                if role not in palette[mode]:
                    continue
                cells = [
                    f"{surface.replace('surface-', ''):8}{contrast(palette[mode][role], palette[mode][surface]):5.2f}"
                    for surface in grounds
                    if surface in palette[mode]
                ]
                print(f"  {role:16} " + "  ".join(cells))
        findings += check(palette[mode], mode)

    for finding in findings:
        print(f"✘ {finding}")
    if findings:
        print(f"\ntheme-contrast: {len(findings)} finding(s)")
        print("Fix the token in the canonical file and re-copy it into the four "
              "repos; a product-local edit cannot pass the hash gate.")
        return 1
    print("theme-contrast: passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
