#!/usr/bin/env python3
"""Self-tests for the Spanish gap filler.

The property that matters is the one a reviewer cannot check by eye: that it
never rewrites an existing Spanish value. Everything else it does is visible in
the diff; that guarantee is what makes the diff safe to skim.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

FILLER = Path(__file__).with_name("es-fill.py")


class EsFillTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "scripts" / "i18n").mkdir(parents=True)
        shutil.copy(FILLER, self.root / "scripts" / "i18n" / "es-fill.py")
        shutil.copy(
            Path(__file__).with_name("translation-memory.tsv"),
            self.root / "scripts" / "i18n" / "translation-memory.tsv",
        )
        (self.root / "scripts" / "i18n" / "glossary.txt").write_text("RSSI\nMbps\nPCAP\n")
        for lang in ("en", "es"):
            (self.root / "internal" / "i18n" / "locales" / lang).mkdir(parents=True)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write(self, lang: str, namespace: str, payload: dict) -> None:
        path = self.root / "internal" / "i18n" / "locales" / lang / f"{namespace}.json"
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))

    def read(self, lang: str, namespace: str) -> dict:
        path = self.root / "internal" / "i18n" / "locales" / lang / f"{namespace}.json"
        return json.loads(path.read_text())

    def run_filler(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "scripts/i18n/es-fill.py", *args],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "I18N_REPO_ROOT": str(self.root)},
        )

    def test_fills_a_memory_hit(self) -> None:
        self.write("en", "common", {"buttons": {"save": "Save"}})
        self.write("es", "common", {})
        self.run_filler("--write")
        self.assertEqual(self.read("es", "common")["buttons"]["save"], "Guardar")

    def test_never_rewrites_an_existing_value(self) -> None:
        """The guarantee the tool exists to keep."""
        self.write("en", "common", {"buttons": {"save": "Save", "cancel": "Cancel"}})
        self.write("es", "common", {"buttons": {"save": "Conservar"}})
        self.run_filler("--write")
        spanish = self.read("es", "common")["buttons"]
        self.assertEqual(spanish["save"], "Conservar", "reviewed copy was overwritten")
        self.assertEqual(spanish["cancel"], "Cancelar")

    def test_copies_glossary_only_values_verbatim(self) -> None:
        self.write("en", "units", {"rate": "Mbps", "signal": "RSSI"})
        self.write("es", "units", {})
        self.run_filler("--write")
        spanish = self.read("es", "units")
        self.assertEqual(spanish["rate"], "Mbps")
        self.assertEqual(spanish["signal"], "RSSI")

    def test_refuses_to_invent_a_novel_string(self) -> None:
        self.write("en", "common", {"prose": {"line": "Coverage is measured per survey."}})
        self.write("es", "common", {})
        result = self.run_filler("--write")
        self.assertNotIn("line", self.read("es", "common").get("prose", {}))
        self.assertIn("need a translator", result.stdout)

    def test_rejects_a_memory_hit_that_drops_a_placeholder(self) -> None:
        """A dropped {{count}} renders as literal text, so this is not a fill."""
        self.write("en", "common", {"n": {"items": "Save {{count}}"}})
        self.write("es", "common", {})
        self.run_filler("--write")
        self.assertNotIn("items", self.read("es", "common").get("n", {}))

    def test_check_mode_fails_only_on_fillable_gaps(self) -> None:
        self.write("en", "common", {"buttons": {"save": "Save"}})
        self.write("es", "common", {})
        self.assertEqual(self.run_filler("--check").returncode, 1)

        self.run_filler("--write")
        self.assertEqual(self.run_filler("--check").returncode, 0)

    def test_check_mode_passes_when_only_human_work_remains(self) -> None:
        self.write("en", "common", {"prose": {"line": "Coverage is measured per survey."}})
        self.write("es", "common", {})
        self.assertEqual(self.run_filler("--check").returncode, 0)


if __name__ == "__main__":
    unittest.main()
