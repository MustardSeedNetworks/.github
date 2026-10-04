#!/usr/bin/env python3
"""Self-tests for validate.sh's interpolation-parity check.

The check sorted the EN variable set in jq (codepoint order) and the
secondary-locale set with the shell's `sort -u`, which collates by the
caller's locale. Under en_US.UTF-8, `{{fd}}` sorts before `{{fdv}}`; by
codepoint it sorts after, because `}` follows `v`. So identical sets whose
variables share a prefix compared unequal on a developer's machine while CI,
running in the C locale, stayed green (.github#99).

Each case runs the real script against a throwaway locale tree under both
locales. en_US.UTF-8 is required, not skipped: without it the test cannot
reproduce the bug it guards.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("validate.sh")
LOCALES = ("C", "en_US.UTF-8")


class InterpolationParityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # A missing locale makes `sort` fall back to C, and the UTF-8 case
        # would then pass whether or not the bug is fixed.
        available = subprocess.run(
            ["locale", "-a"], capture_output=True, text=True, check=True
        ).stdout.lower().replace("-", "")
        if "en_us.utf8" not in available.split():
            raise RuntimeError("en_US.UTF-8 is not installed; this test cannot run")

    def run_check(self, en: str, es: str, lc_all: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for loc, value in (("en", en), ("es", es)):
                ns_dir = root / "internal" / "i18n" / "locales" / loc
                ns_dir.mkdir(parents=True)
                (ns_dir / "common.json").write_text(json.dumps({"sla": value}))
            return subprocess.run(
                ["bash", str(SCRIPT), "--check", "interpolation_parity"],
                cwd=root,
                env={**os.environ, "LC_ALL": lc_all},
                capture_output=True,
                text=True,
                check=False,
            )

    def test_prefix_sharing_vars_match_in_every_locale(self) -> None:
        for lc_all in LOCALES:
            with self.subTest(lc_all=lc_all):
                result = self.run_check(
                    "FD {{fd}} ms, FDV {{fdv}} ms",
                    "FDV {{fdv}} ms, FD {{fd}} ms",
                    lc_all,
                )
                self.assertEqual(result.returncode, 0, result.stdout)

    def test_real_drift_fails_in_every_locale(self) -> None:
        for lc_all in LOCALES:
            with self.subTest(lc_all=lc_all):
                result = self.run_check("FD {{fd}} ms", "FD {{fdx}} ms", lc_all)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("interpolation vars mismatch", result.stdout)


if __name__ == "__main__":
    unittest.main()
