#!/usr/bin/env python3
"""Self-tests for the shared-UI copy, manifest and verify mechanism.

The mechanism exists so a fleet-wide divergence cannot hide (.github#69), so
each case asserts it FIRES on drift, a missing file and a stray file, and stays
quiet on a clean copy and on a product that has not adopted the set yet.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
import ui_shared  # noqa: E402

spec = importlib.util.spec_from_file_location("conformance", SCRIPTS / "check-ci-conformance.py")
assert spec and spec.loader
conformance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(conformance)


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


class Fixture(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.canon = base / "canon"
        self.product = base / "product"
        write(self.canon / "ui/theme/msn-shared.css", ":root{}\n")
        write(self.canon / "ui/components/Button.tsx", "export const a = 1;\n")
        write(self.canon / "ui/components/Button.test.tsx", "export const t = 1;\n")
        write(self.canon / "ui/components/test/Fixtures.tsx", "export const f = 1;\n")
        write(self.canon / "ui/components/notes.md", "not shipped\n")
        (self.canon / ui_shared.MANIFEST).write_text(ui_shared.render_manifest(self.canon))
        (self.product / "ui/src").mkdir(parents=True)

    def adopt(self) -> None:
        ui_shared.copy(self.canon, self.product)


class ManifestTests(Fixture):
    def test_lists_theme_and_components_but_not_other_files(self) -> None:
        self.assertEqual(
            sorted(ui_shared.read_manifest(self.canon)),
            [
                "src/shared/Button.test.tsx",
                "src/shared/Button.tsx",
                "src/shared/test/Fixtures.tsx",
                "src/theme/msn-shared.css",
            ],
        )

    def test_current_manifest_passes(self) -> None:
        self.assertEqual(ui_shared.check_manifest(self.canon), [])

    def test_stale_manifest_fails_after_a_component_changes(self) -> None:
        write(self.canon / "ui/components/Button.tsx", "export const a = 2;\n")
        self.assertEqual(len(ui_shared.check_manifest(self.canon)), 1)

    def test_stale_manifest_fails_after_a_component_is_added(self) -> None:
        write(self.canon / "ui/components/Card.tsx", "export const c = 1;\n")
        self.assertEqual(len(ui_shared.check_manifest(self.canon)), 1)

    def test_missing_manifest_fails(self) -> None:
        (self.canon / ui_shared.MANIFEST).unlink()
        self.assertEqual(len(ui_shared.check_manifest(self.canon)), 1)

    def test_the_committed_manifest_is_current(self) -> None:
        self.assertEqual(ui_shared.check_manifest(SCRIPTS.parent), [])


class VerifyTests(Fixture):
    def test_a_fresh_copy_verifies(self) -> None:
        self.adopt()
        self.assertEqual(ui_shared.verify(self.canon, self.product), [])

    def test_a_helper_under_test_is_copied_and_verified_in_place(self) -> None:
        self.adopt()
        self.assertTrue((self.product / "ui/src/shared/test/Fixtures.tsx").is_file())
        self.assertEqual(ui_shared.verify(self.canon, self.product), [])

    def test_a_local_edit_is_drift(self) -> None:
        self.adopt()
        write(self.product / "ui/src/shared/Button.tsx", "export const a = 99;\n")
        findings = ui_shared.verify(self.canon, self.product)
        self.assertEqual(len(findings), 1)
        self.assertIn("Button.tsx has drifted", findings[0])

    def test_a_deleted_copy_is_reported(self) -> None:
        self.adopt()
        (self.product / "ui/src/shared/Button.test.tsx").unlink()
        findings = ui_shared.verify(self.canon, self.product)
        self.assertEqual(len(findings), 1)
        self.assertIn("is missing", findings[0])

    def test_a_stray_file_in_the_shared_dir_is_reported(self) -> None:
        self.adopt()
        write(self.product / "ui/src/shared/Local.tsx", "export const l = 1;\n")
        findings = ui_shared.verify(self.canon, self.product)
        self.assertEqual(len(findings), 1)
        self.assertIn("not in the canonical set", findings[0])

    def test_theme_drift_is_reported_by_a_full_verify(self) -> None:
        self.adopt()
        write(self.product / "ui/src/theme/msn-shared.css", ":root{--x:1}\n")
        self.assertEqual(len(ui_shared.verify(self.canon, self.product)), 1)

    def test_copy_removes_a_component_deleted_upstream(self) -> None:
        self.adopt()
        (self.canon / "ui/components/Button.test.tsx").unlink()
        (self.canon / ui_shared.MANIFEST).write_text(ui_shared.render_manifest(self.canon))
        ui_shared.copy(self.canon, self.product)
        self.assertFalse((self.product / "ui/src/shared/Button.test.tsx").exists())
        self.assertEqual(ui_shared.verify(self.canon, self.product), [])

    def test_the_real_canonical_set_copies_and_verifies(self) -> None:
        real = SCRIPTS.parent
        ui_shared.copy(real, self.product)
        self.assertEqual(ui_shared.verify(real, self.product), [])
        self.assertTrue((self.product / "ui/src/shared/PageHeader.tsx").is_file())


class ConformanceRuleTests(Fixture):
    def test_a_product_that_has_not_adopted_the_set_is_not_checked(self) -> None:
        self.assertEqual(conformance.shared_components(self.product, self.canon), [])

    def test_an_empty_ui_src_is_not_adoption(self) -> None:
        self.assertFalse(ui_shared.adopted(self.product))

    def test_an_adopted_product_that_matches_passes(self) -> None:
        self.adopt()
        self.assertEqual(conformance.shared_components(self.product, self.canon), [])

    def test_an_adopted_product_that_drifted_fails(self) -> None:
        self.adopt()
        write(self.product / "ui/src/shared/Button.tsx", "export const a = 99;\n")
        self.assertEqual(len(conformance.shared_components(self.product, self.canon)), 1)

    def test_an_adopted_product_missing_a_file_fails(self) -> None:
        self.adopt()
        (self.product / "ui/src/shared/Button.tsx").unlink()
        self.assertEqual(len(conformance.shared_components(self.product, self.canon)), 1)

    def test_the_theme_is_left_to_its_own_rule(self) -> None:
        self.adopt()
        write(self.product / "ui/src/theme/msn-shared.css", ":root{--x:1}\n")
        self.assertEqual(conformance.shared_components(self.product, self.canon), [])


if __name__ == "__main__":
    unittest.main()
