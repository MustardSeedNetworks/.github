#!/usr/bin/env python3
"""Self-tests for the CI conformance gate's build-contract checks.

Every rule here exists because the fleet found the gap by hand first, and
each is the kind that looks green: a workflow that pins Node twice, a
govulncheck that reports instead of blocking, a binary whose /__version says
"unknown", a concurrency group that silently drops main runs.

A gate that cannot fail is the defect these rules are about, so each case
asserts the check FIRES on a violating fixture and stays quiet on the
compliant one -- not merely that the script runs.

The checker derives paths from the working directory, so each case builds a
throwaway repo tree and runs there.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CHECKER = Path(__file__).with_name("check-ci-conformance.py")

# A ci.yml that satisfies every rule below. Cases mutate one thing at a time,
# so a failure names exactly which rule moved.
GOOD_CI = """\
name: CI

on:
  push:
    branches: [main]
  pull_request:
  merge_group:

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}${{ github.ref == 'refs/heads/main' && format('-{0}', github.sha) || '' }}
  cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: ./.github/actions/setup-go
      - uses: ./.github/actions/setup-node
      - name: Compile check
        run: go build ./...
      - name: Cross-compile check
        run: go build -trimpath -o /dev/null ./cmd/x/
      - name: Build
        run: |
          go build -trimpath \\
            -ldflags="-X example.com/x/internal/version.Version=${VERSION}" \\
            -o x ./cmd/x
      - name: Run govulncheck
        run: govulncheck ./...

  ci-complete:
    needs:
      - backend
    if: always()
    steps:
      - run: echo done
"""


class ConformanceChecks(unittest.TestCase):
    def run_checker(self, ci: str) -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".github/workflows").mkdir(parents=True)
            (root / ".github/workflows/ci.yml").write_text(ci)
            # The unrelated checks (CODEOWNERS, governance scripts, advisory
            # list) are not under test here; give them what they need so the
            # only findings are the ones each case is about.
            (root / ".github/CODEOWNERS").write_text("* @owner\n")
            (root / ".github/ci-advisory-jobs.txt").write_text("# none\n")
            (root / "scripts").mkdir()
            (root / "scripts/check-banned-vocabulary.py").write_text("")
            (root / "scripts/check-file-size.sh").write_text("")
            p = subprocess.run([sys.executable, str(CHECKER)], cwd=root,
                               capture_output=True, text=True)
            return p.returncode, p.stdout + p.stderr

    def assertFires(self, ci: str, needle: str) -> None:
        code, out = self.run_checker(ci)
        self.assertNotEqual(code, 0, f"expected a finding for {needle!r}:\n{out}")
        self.assertIn(needle, out)

    def assertQuiet(self, ci: str, needle: str) -> None:
        _, out = self.run_checker(ci)
        self.assertNotIn(needle, out)

    def test_good_fixture_is_clean_on_these_rules(self) -> None:
        """The compliant fixture must trip none of the four rules.

        Without this, every case below could pass because the checker reports
        everything always.
        """
        _, out = self.run_checker(GOOD_CI)
        for needle in ("stock actions/setup-", "hardcodes node-version",
                       "continue-on-error", "without -ldflags",
                       "not keyed by github.sha"):
            self.assertNotIn(needle, out, f"good fixture tripped {needle!r}:\n{out}")

    def test_stock_setup_action_is_rejected(self) -> None:
        ci = GOOD_CI.replace("- uses: ./.github/actions/setup-go",
                             "- uses: actions/setup-go@v7.0.0")
        self.assertFires(ci, "stock actions/setup-go")

    def test_hardcoded_node_version_is_rejected(self) -> None:
        ci = GOOD_CI.replace("      - uses: ./.github/actions/setup-node",
                             "      - uses: ./.github/actions/setup-node\n"
                             "        with:\n          node-version: 26.8.1")
        self.assertFires(ci, "hardcodes node-version")

    def test_advisory_govulncheck_is_rejected(self) -> None:
        ci = GOOD_CI.replace("      - name: Run govulncheck\n",
                             "      - name: Run govulncheck\n        continue-on-error: true\n")
        self.assertFires(ci, "govulncheck runs continue-on-error")

    def test_build_without_ldflags_is_rejected(self) -> None:
        ci = GOOD_CI.replace(
            '          go build -trimpath \\\n'
            '            -ldflags="-X example.com/x/internal/version.Version=${VERSION}" \\\n'
            '            -o x ./cmd/x\n',
            "          go build -trimpath -o x ./cmd/x\n")
        self.assertFires(ci, "without -ldflags")

    def test_compile_checks_are_not_builds(self) -> None:
        """`go build ./...` and `-o /dev/null` produce nothing to ship.

        The first version of this rule flagged both, plus every real build --
        because it read one line at a time and every build in the fleet puts
        -ldflags on the line after `go build -trimpath \\`. It reported four
        violations per repo, all false.
        """
        self.assertQuiet(GOOD_CI, "without -ldflags")

    def test_main_concurrency_must_key_on_sha(self) -> None:
        ci = GOOD_CI.replace(
            "  group: ${{ github.workflow }}-${{ github.ref }}${{ github.ref == 'refs/heads/main' && format('-{0}', github.sha) || '' }}",
            "  group: ${{ github.workflow }}-${{ github.ref }}")
        self.assertFires(ci, "not keyed by github.sha")


if __name__ == "__main__":
    unittest.main(verbosity=2)
