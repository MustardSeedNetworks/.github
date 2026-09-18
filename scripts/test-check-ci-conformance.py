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
    def run_checker(self, ci: str, status_definitions: str = "",
                    theme: str | None = None,
                    locales_alias: str | None = None,
                    locales_dir: str = "internal/i18n/locales") -> tuple[int, str]:
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
            if status_definitions:
                (root / "ui/src").mkdir(parents=True)
                (root / "ui/src/state.ts").write_text(status_definitions)
            if theme is not None:
                (root / "ui/src/theme").mkdir(parents=True, exist_ok=True)
                (root / "ui/src/theme/msn-shared.css").write_text(theme)
            if locales_alias is not None:
                (root / "ui").mkdir(parents=True, exist_ok=True)
                (root / "ui/vite.config.ts").write_text(
                    "export default {\n"
                    "  resolve: { alias: [\n"
                    f"    {{ find: '@locales', replacement: '{locales_alias}' }},\n"
                    "  ] },\n"
                    "};\n")
                (root / locales_dir / "en").mkdir(parents=True, exist_ok=True)
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

    def test_rollup_accepts_only_the_two_approved_vocabularies(self) -> None:
        for members in (
            "'ok' | 'warn' | 'crit' | 'unknown'",
            "'ok' | 'warn' | 'crit' | 'unknown' | 'idle'",
        ):
            with self.subTest(members=members):
                _, out = self.run_checker(
                    GOOD_CI,
                    f"export type RollupState = {members};\n"
                    "export type RecordState = RollupState;\n",
                )
                self.assertNotIn("fleet vocabulary", out)

    def test_rollup_rejects_missing_or_unapproved_states(self) -> None:
        for members in (
            "'ok' | 'warn' | 'crit' | 'idle'",
            "'ok' | 'warn' | 'crit' | 'unknown' | 'idle' | 'busy'",
            "'ok' | 'warn' | 'crit' | 'unknown' | 'loading'",
            "'ok' | 'warn' | 'crit' | 'unknown' | 'info'",
            "'ok' | 'warn' | 'crit' | 'unknown' | 'idle' | 'idle'",
            "string",
        ):
            with self.subTest(members=members):
                code, out = self.run_checker(
                    GOOD_CI, f"export type RollupState = {members};\n"
                )
                self.assertNotEqual(code, 0)
                self.assertIn("`RollupState` has drifted", out)

    def test_card_status_keeps_its_existing_vocabulary(self) -> None:
        definition = (
            "export type Status = 'success' | 'warning' | 'error' | 'unknown' | 'loading'"
        )
        _, out = self.run_checker(GOOD_CI, definition + ";\n")
        self.assertNotIn("fleet vocabulary", out)
        code, out = self.run_checker(GOOD_CI, definition + " | 'idle';\n")
        self.assertNotEqual(code, 0)
        self.assertIn("`Status` has drifted", out)

    def test_record_state_remains_an_alias(self) -> None:
        code, out = self.run_checker(
            GOOD_CI, "export type RecordState = RollupState | 'idle';\n"
        )
        self.assertNotEqual(code, 0)
        self.assertIn("`RecordState` has drifted", out)


    # ---- shared theme (.github#69) -------------------------------------
    #
    # The fleet shipped three different msn-shared.css files with every repo
    # green, so these assert on the REAL canonical file rather than a fixture
    # of one: a canonical edit that is not re-copied must fail here too.

    CANONICAL = CHECKER.parent.parent / "ui/theme/msn-shared.css"

    def test_identical_theme_copy_passes(self) -> None:
        _, out = self.run_checker(GOOD_CI, theme=self.CANONICAL.read_text())
        self.assertNotIn("has drifted from the canonical theme", out)

    def test_drifted_theme_copy_is_rejected(self) -> None:
        drifted = self.CANONICAL.read_text().replace(
            "--color-status-success: #2a7146;", "--color-status-success: #2f7d4f;")
        self.assertNotEqual(drifted, self.CANONICAL.read_text(),
                            "fixture did not mutate the canonical file")
        code, out = self.run_checker(GOOD_CI, theme=drifted)
        self.assertNotEqual(code, 0, out)
        self.assertIn("has drifted from the canonical theme", out)

    def test_comment_only_theme_drift_is_rejected(self) -> None:
        """Comments carry the measurements; they drift too."""
        drifted = self.CANONICAL.read_text() + "\n/* product-local note */\n"
        code, out = self.run_checker(GOOD_CI, theme=drifted)
        self.assertNotEqual(code, 0, out)
        self.assertIn("has drifted from the canonical theme", out)

    def test_missing_theme_in_a_ui_repo_is_rejected(self) -> None:
        code, out = self.run_checker(GOOD_CI, status_definitions="// ui repo\n")
        self.assertNotEqual(code, 0, out)
        self.assertIn("ui/src/theme/msn-shared.css is missing", out)

    def test_backend_only_repo_is_out_of_scope(self) -> None:
        _, out = self.run_checker(GOOD_CI)
        self.assertNotIn("msn-shared.css", out)



    def run_checker_with_vite(self, vite: str) -> tuple[int, str]:
        """Run the checker over a minimal repo whose vite config is `vite`."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".github/workflows").mkdir(parents=True)
            (root / ".github/workflows/ci.yml").write_text(GOOD_CI)
            (root / ".github/CODEOWNERS").write_text("* @owner\n")
            (root / ".github/ci-advisory-jobs.txt").write_text("# none\n")
            (root / "scripts").mkdir()
            (root / "scripts/check-banned-vocabulary.py").write_text("")
            (root / "scripts/check-file-size.sh").write_text("")
            (root / "ui").mkdir(parents=True)
            (root / "internal/i18n/locales/en").mkdir(parents=True)
            (root / "ui/vite.config.ts").write_text(vite)
            p = subprocess.run([sys.executable, str(CHECKER)], cwd=root,
                               capture_output=True, text=True)
            return p.returncode, p.stdout + p.stderr

    def test_canonical_locales_alias_is_accepted(self) -> None:
        _, out = self.run_checker(
            GOOD_CI, locales_alias="../internal/i18n/locales")
        self.assertNotIn("@locales alias", out)

    def test_frontend_locales_alias_is_rejected(self) -> None:
        code, out = self.run_checker(GOOD_CI, locales_alias="./locales")
        self.assertNotEqual(code, 0, out)
        self.assertIn("@locales alias does not resolve to "
                      "internal/i18n/locales/", out)

    def test_repo_without_a_locales_alias_is_not_forced_to_have_one(self) -> None:
        """A repo with no i18n must not be failed into adopting it.

        The rule pins where translations live, not whether a product has any.
        """
        _, out = self.run_checker(GOOD_CI)
        self.assertNotIn("@locales alias", out)

    def test_a_commented_out_alias_is_not_a_violation(self) -> None:
        """A doc comment showing the old path must not fail the repo.

        The relocation leaves comments behind that quote `'@locales': './locales'`
        as the thing that changed; reading those as live config would fail a
        repo for describing its own history correctly.
        """
        _, out = self.run_checker_with_vite(
            "export default {\n"
            "  resolve: { alias: [\n"
            "    // was: { find: '@locales', replacement: './locales' }\n"
            "    { find: '@locales', "
            "replacement: '../internal/i18n/locales' },\n"
            "  ] },\n"
            "};\n")
        self.assertNotIn("@locales alias", out)

    def test_a_regex_find_with_the_target_on_the_next_line_is_read(self) -> None:
        """seed writes the alias as a regex `find:` over two lines.

        Matching only a quoted `'@locales'` key skipped that file outright, so
        seed passed for appearing to have no alias at all -- the rule was
        vacuous in one of the four repos it gates.
        """
        _, out = self.run_checker_with_vite(
            "export default {\n"
            "  resolve: { alias: [\n"
            "    {\n"
            "      find: /^@locales\\//,\n"
            "      replacement: fileURLToPath("
            "new URL('../internal/i18n/locales/', import.meta.url)),\n"
            "    },\n"
            "  ] },\n"
            "};\n")
        self.assertNotIn("@locales alias", out)

    def test_a_regex_find_pointing_at_the_frontend_is_rejected(self) -> None:
        code, out = self.run_checker_with_vite(
            "export default {\n"
            "  resolve: { alias: [\n"
            "    {\n"
            "      find: /^@locales\\//,\n"
            "      replacement: fileURLToPath("
            "new URL('./locales/', import.meta.url)),\n"
            "    },\n"
            "  ] },\n"
            "};\n")
        self.assertNotEqual(code, 0, out)
        self.assertIn("@locales alias does not resolve to "
                      "internal/i18n/locales/", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
