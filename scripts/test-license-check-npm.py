#!/usr/bin/env python3
"""Fixture runs of the npm half of the shared license gate.

The step classified a public caller's own package as an external BUSL-1.1
dependency and failed foundation#91 (.github#98). The fix excludes the caller
by its exact name@version, so each case runs the step's real script, with the
real checker, against a hand-built ui/ tree: the self-exclusion must hold, and
it must not widen into a licence exception.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "license-check.yml"
STEP = "      - name: Check npm dependencies for license compliance\n"


def step_script() -> str:
    """The step's `run: |` block, exactly as the runner receives it."""
    lines = WORKFLOW.read_text().splitlines(keepends=True)
    start = lines.index(STEP)
    run = next(i for i in range(start, len(lines)) if lines[i].strip() == "run: |")
    body = []
    for line in lines[run + 1:]:
        if line.strip() and not line.startswith(" " * 10):
            break
        body.append(line)
    return textwrap.dedent("".join(body))


SCRIPT = step_script()

AUTH_UI = {"name": "@mustardseednetworks/auth-ui", "version": "0.0.0", "license": "BUSL-1.1"}


class NpmLicenseGate(unittest.TestCase):
    def run_gate(self, root: dict, deps: list[dict]) -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as tmp:
            ui = Path(tmp)
            manifest = dict(root, dependencies={d["name"]: d["version"] for d in deps})
            (ui / "package.json").write_text(json.dumps(manifest))
            for dep in deps:
                pkg = ui / "node_modules" / dep["name"]
                pkg.mkdir(parents=True)
                (pkg / "package.json").write_text(json.dumps(dep))
            # GitHub's `bash -e {0}` shell, which the step runs under.
            proc = subprocess.run(["bash", "-e", "-c", SCRIPT], cwd=ui,
                                  capture_output=True, text=True)
            return proc.returncode, proc.stdout + proc.stderr

    def test_public_busl_self_with_an_mit_dependency_passes(self) -> None:
        code, out = self.run_gate(AUTH_UI, [{"name": "react", "version": "19.2.8", "license": "MIT"}])
        self.assertEqual(code, 0, out)
        self.assertIn("Excluding the project itself: @mustardseednetworks/auth-ui@0.0.0", out)

    def test_third_party_gpl_dependency_fails(self) -> None:
        code, out = self.run_gate(AUTH_UI, [{"name": "gpl-dep", "version": "1.0.0", "license": "GPL-3.0"}])
        self.assertNotEqual(code, 0, out)
        self.assertIn('"gpl-dep@1.0.0" is licensed under "GPL-3.0"', out)

    def test_third_party_busl_dependency_fails(self) -> None:
        """Excluding self must not turn into allowing BUSL-1.1."""
        code, out = self.run_gate(AUTH_UI, [{"name": "busl-dep", "version": "1.0.0", "license": "BUSL-1.1"}])
        self.assertNotEqual(code, 0, out)
        self.assertIn('"busl-dep@1.0.0" is licensed under "BUSL-1.1"', out)

    def test_public_root_without_a_version_fails(self) -> None:
        root = {k: v for k, v in AUTH_UI.items() if k != "version"}
        code, out = self.run_gate(root, [{"name": "react", "version": "19.2.8", "license": "MIT"}])
        self.assertNotEqual(code, 0, out)
        self.assertIn("has no name and version", out)

    def test_public_root_without_a_name_fails(self) -> None:
        root = {k: v for k, v in AUTH_UI.items() if k != "name"}
        code, out = self.run_gate(root, [{"name": "react", "version": "19.2.8", "license": "MIT"}])
        self.assertNotEqual(code, 0, out)
        self.assertIn("has no name and version", out)

    def test_same_name_at_another_version_is_still_classified(self) -> None:
        """Only the exact root identity is excluded, not every version of its name."""
        nested = dict(AUTH_UI, version="0.0.1")
        code, out = self.run_gate(dict(AUTH_UI, name="consumer", license="MIT"), [nested])
        self.assertEqual(self._excluded(out), "consumer@0.0.0")
        self.assertNotEqual(code, 0, out)
        self.assertIn('"@mustardseednetworks/auth-ui@0.0.1" is licensed under "BUSL-1.1"', out)

    def test_private_caller_is_unchanged(self) -> None:
        """seed, stem, niac and trellis: no identity needed, nothing excluded by name."""
        root = {"name": "seed-ui", "private": True}
        code, out = self.run_gate(root, [{"name": "react", "version": "19.2.8", "license": "MIT"}])
        self.assertEqual(code, 0, out)
        self.assertIsNone(self._excluded(out))

    def test_private_caller_with_a_gpl_dependency_still_fails(self) -> None:
        root = {"name": "seed-ui", "version": "0.221.4", "private": True}
        code, out = self.run_gate(root, [{"name": "gpl-dep", "version": "1.0.0", "license": "GPL-3.0"}])
        self.assertNotEqual(code, 0, out)

    @staticmethod
    def _excluded(out: str) -> str | None:
        marker = "Excluding the project itself: "
        for line in out.splitlines():
            if line.startswith(marker):
                return line[len(marker):]
        return None


if __name__ == "__main__":
    unittest.main(verbosity=2)
