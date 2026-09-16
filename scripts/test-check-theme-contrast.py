#!/usr/bin/env python3
"""Tests for check-theme-contrast.py.

The value of this gate is entirely in what it REFUSES, so most of these build
a palette that is wrong in one specific way and assert the finding. The
regression each one guards is .github#74: a pair nobody measured.
"""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("contrast", REPO / "scripts/check-theme-contrast.py")
contrast = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(contrast)


def palette_css(**overrides: str) -> str:
    """A minimal two-mode theme. Defaults all clear their floors."""
    light = {
        "surface-base": "#ffffff",
        "surface-raised": "#ffffff",
        "surface-hover": "#ffffff",
        "surface-sunken": "#ffffff",
        "surface-deep": "#ffffff",
        "rail-from": "#ffffff",
        "rail-to": "#ffffff",
        "text-primary": "#000000",
        "text-muted": "#595959",
        "surface-border": "#767676",
    }
    light.update(overrides)
    body = "\n".join(f"  --color-{k}: {v};" for k, v in light.items())
    return f":root {{\n{body}\n}}\n"


def run(css: str) -> list[str]:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "theme.css"
        path.write_text(css, encoding="utf-8")
        pal = contrast.palettes([path])
        return contrast.check(pal["light"], "light")


class ContrastMath(unittest.TestCase):
    def test_known_wcag_ratios(self) -> None:
        """Black on white is 21:1 and #767676 on white is the 4.5 boundary."""
        white = contrast.parse_colour("#ffffff")
        black = contrast.parse_colour("#000000")
        grey = contrast.parse_colour("#767676")
        assert white and black and grey
        self.assertAlmostEqual(contrast.contrast(black, white), 21.0, places=2)
        self.assertAlmostEqual(contrast.contrast(grey, white), 4.54, places=2)

    def test_alpha_is_composited_not_ignored(self) -> None:
        """A translucent token is measured against the ground it sits on.

        Treating rgba() as opaque was the bug that would let a hairline or a
        tint wash claim a ratio it never has on screen.
        """
        wash = contrast.parse_colour("rgba(0, 0, 0, 0.1)")
        white = contrast.parse_colour("#ffffff")
        assert wash and white
        ratio = contrast.contrast(wash, white)
        self.assertLess(ratio, 1.3, "10% black over white is nearly white")
        self.assertGreater(ratio, 1.0)

    def test_rejects_unsupported_colour_syntax(self) -> None:
        """An unparsed value must not silently become a passing pair."""
        self.assertIsNone(contrast.parse_colour("color-mix(in oklab, red, blue)"))
        self.assertIsNone(contrast.parse_colour("var(--color-text-primary)"))


class Findings(unittest.TestCase):
    def test_clean_palette_has_no_findings(self) -> None:
        self.assertEqual(run(palette_css()), [])

    def test_text_under_the_floor_is_reported_with_its_ratio(self) -> None:
        findings = run(palette_css(**{"text-muted": "#8a8a8a"}))
        self.assertTrue(findings)
        self.assertIn("--color-text-muted", findings[0])
        self.assertIn("4.5:1 text floor", findings[0])

    def test_a_pair_failing_on_one_surface_only_is_caught(self) -> None:
        """#74 itself: base and raised pass, hover does not.

        Before this gate the palette's own comments measured base and raised,
        so exactly this shape shipped four times.
        """
        findings = run(palette_css(**{"surface-hover": "#8f8f8f", "text-muted": "#595959"}))
        muted = [f for f in findings if "--color-text-muted" in f]
        self.assertEqual(len(muted), 1, findings)
        self.assertIn("--color-surface-hover", muted[0])
        self.assertFalse(
            [f for f in findings if "surface-base" in f or "surface-raised" in f],
            "the surfaces the old measured set covered must still pass",
        )

    def test_edge_token_uses_the_3_to_1_floor_not_4_5(self) -> None:
        """surface-border at 3.2:1 passes as an edge and would fail as text."""
        findings = run(palette_css(**{"surface-border": "#949494"}))
        self.assertEqual(findings, [], "an edge at ~3.2:1 meets 1.4.11")
        findings = run(palette_css(**{"surface-border": "#aaaaaa"}))
        self.assertTrue(findings)
        self.assertIn("3.0:1 UI edge floor", findings[0])

    def test_missing_token_is_skipped_not_crashed(self) -> None:
        """A product file carries brand tokens; the canonical file does not."""
        css = ":root {\n  --color-surface-base: #ffffff;\n  --color-text-primary: #000000;\n}\n"
        self.assertEqual(run(css), [])


class Canonical(unittest.TestCase):
    def test_the_shipped_theme_passes_its_own_gate(self) -> None:
        pal = contrast.palettes([REPO / "ui/theme/msn-shared.css"])
        findings = contrast.check(pal["light"], "light") + contrast.check(pal["dark"], "dark")
        self.assertEqual(findings, [], "\n".join(findings))

    def test_both_modes_are_actually_parsed(self) -> None:
        """A regex that matched only :root would make .dark silently unchecked."""
        pal = contrast.palettes([REPO / "ui/theme/msn-shared.css"])
        self.assertIn("text-muted", pal["light"])
        self.assertIn("text-muted", pal["dark"])
        self.assertNotEqual(pal["light"]["text-muted"], pal["dark"]["text-muted"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
