#!/usr/bin/env python3
"""Self-tests for the repository banned-vocabulary gate."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path


CHECKER = Path(__file__).with_name("check-banned-vocabulary.py")


class BannedVocabularyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.terms = self.root / "terms.txt"
        self.terms.write_text("AI\nAI-powered\nopen source\n", encoding="utf-8")
        self.exclusions = self.root / "exclusions.txt"
        # The gate's own term list and exclusion list sit inside the tree it
        # scans, and both necessarily contain banned terms. The real repository
        # excludes them for exactly this reason (see the banned-vocab.txt and
        # banned-vocabulary-exclusions.txt entries in the shipped exclusions
        # file), so the fixture mirrors that rather than being a shape the gate
        # never actually runs against.
        self.exclusions.write_text(
            "terms.txt | policy term source\n"
            "exclusions.txt | policy exclusion list\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write(self, path: str, content: str) -> None:
        self.write_untracked(path, content)
        subprocess.run(["git", "-C", str(self.root), "add", "-f", path], check=True)

    def write_untracked(self, path: str, content: str) -> None:
        """Write a file without staging it — the state a doc is in while
        someone is still writing it, and the state the gate used to miss."""
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def run_checker(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "python3",
                str(CHECKER),
                "--root",
                str(self.root),
                "--terms",
                str(self.terms),
                "--exclusions",
                str(self.exclusions),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_positive_fixture_fails_with_location(self) -> None:
        self.write("README.md", "An AI-powered network tool.\n")
        result = self.run_checker()
        self.assertEqual(1, result.returncode)
        self.assertIn("README.md:1: banned term 'AI-powered'", result.stdout)

    def test_negative_fixture_passes(self) -> None:
        self.write("README.md", "A source-available network tool.\n")
        result = self.run_checker()
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_matching_is_case_insensitive(self) -> None:
        self.write("docs/current.md", "This is OPEN SOURCE.\n")
        result = self.run_checker()
        self.assertEqual(1, result.returncode)
        self.assertIn("docs/current.md:1: banned term 'open source'", result.stdout)

    def test_only_documented_paths_are_excluded(self) -> None:
        with self.exclusions.open("a", encoding="utf-8") as exclusions:
            exclusions.write(
                "CHANGELOG.md | immutable release history\n"
                "internal/database/migrations/** | immutable migrations\n"
                "**/AGENTS.md | developer instructions\n"
            )
        self.write("CHANGELOG.md", "AI-powered\n")
        self.write("internal/database/migrations/00001.sql", "AI-powered\n")
        self.write("dev/AGENTS.md", "AI-powered\n")
        result = self.run_checker()
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_stale_exclusion_is_an_error(self) -> None:
        with self.exclusions.open("a", encoding="utf-8") as exclusions:
            exclusions.write("docs/missing.md | stale path\n")
        result = self.run_checker()
        self.assertEqual(2, result.returncode)
        self.assertIn(
            "exclusion matches no repository file: docs/missing.md", result.stderr
        )

    def test_unstaged_file_is_still_checked(self) -> None:
        """The loop that matters is write -> run the gate -> commit. Enumerating
        with plain `git ls-files` made the gate blind in exactly that order, so
        a banned term passed locally and failed in CI one push later (#951)."""
        self.write_untracked("docs/new-page.md", "An AI-powered network tool.\n")
        result = self.run_checker()
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("docs/new-page.md:1: banned term 'AI-powered'", result.stdout)

    def test_gitignored_files_stay_out(self) -> None:
        """`--others` must not become a directory walk: --exclude-standard is
        what keeps build output (an untracked ui/storybook-static/ bundle, say)
        from flooding the gate."""
        self.write(".gitignore", "build-output/\n")
        self.write_untracked("build-output/vendor.md", "An AI-powered bundle.\n")
        result = self.run_checker()
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
