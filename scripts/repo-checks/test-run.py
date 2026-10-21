#!/usr/bin/env python3
"""Self-tests for the repo-checks entry point the action and the shims share."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

RUN = Path(__file__).with_name("run.sh")


class RunTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.write("scripts/banned-vocabulary-exclusions.txt", "# none\n")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write(self, path: str, content: str) -> None:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def run_checks(self, *checks: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(RUN), *checks],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_clean_repo_passes_with_canonical_terms(self) -> None:
        self.write("README.md", "A source-available network tool.\n")
        result = self.run_checks("banned-vocabulary", "tsconfig-flags")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_every_check_runs_after_a_failure(self) -> None:
        self.write("README.md", "An AI-powered network tool.\n")
        self.write("ui/tsconfig.app.json", '{ "compilerOptions": { "strict": false } }\n')
        result = self.run_checks("banned-vocabulary", "tsconfig-flags")
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertIn("README.md:1: banned term 'AI-powered'", result.stdout)
        self.assertIn("strict is false", result.stdout)
        self.assertIn("repo checks failed: banned-vocabulary tsconfig-flags", result.stdout)

    def test_unknown_check_is_a_usage_error(self) -> None:
        result = self.run_checks("bogus")
        self.assertEqual(2, result.returncode)
        self.assertIn("unknown repo check: bogus", result.stderr)

    def test_no_check_is_a_usage_error(self) -> None:
        self.assertEqual(2, self.run_checks().returncode)


if __name__ == "__main__":
    unittest.main()
