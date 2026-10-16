#!/usr/bin/env python3
"""The path classifier is the changes job. A glob that stops matching lets a
PR skip the suite it should have run, and CI Complete accepts `skipped`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("ci-changes.py")

# The shape seed's ci.yml passes to dorny/paths-filter, comments included.
SEED_FILTERS = """\
backend:
  - '**/*.go'
  - 'go.mod'
  - 'go.sum'
  - 'Makefile'
  - 'mk/**'
  # Embedded migration baseline. A change here must run Go tests.
  - 'internal/database/migrations/**'
  - 'internal/i18n/locales/**'
frontend:
  - 'ui/**'
  - 'internal/i18n/locales/**'
darwin_bridge:
  - 'internal/**/*_darwin.h'
  - '.clang-format'
docs:
  - '**/*.md'
ci_infra:
  - '.github/workflows/**'
  - '.github/actions/**'
  - 'scripts/**'
  - '.golangci.yml'
  - 'biome.json'
"""


def classify(filters: str, files: list[str], event: str = "pull_request") -> dict[str, str]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input="\n".join(files) + ("\n" if files else ""),
        capture_output=True,
        text=True,
        env={**os.environ, "FILTERS": filters, "EVENT_NAME": event},
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(proc.stderr or proc.stdout)
    return json.loads(proc.stdout)


class Classify(unittest.TestCase):
    def test_seed_filters_split_a_mixed_diff(self) -> None:
        got = classify(SEED_FILTERS, [
            "internal/api/server.go",
            "ui/src/App.tsx",
            "README.md",
            "scripts/check-foo.sh",
            "internal/wifi/bridge_darwin.h",
            "internal/database/migrations/001_init.sql",
            "internal/i18n/locales/en.json",
            "mk/lint.mk",
            "go.mod",
        ])
        self.assertEqual(got["backend"], "true")
        self.assertEqual(got["frontend"], "true")
        self.assertEqual(got["docs"], "true")
        self.assertEqual(got["ci_infra"], "true")
        self.assertEqual(got["darwin_bridge"], "true")

    def test_a_docs_only_diff_skips_code_filters(self) -> None:
        got = classify(SEED_FILTERS, ["docs/OPERATIONS.md", "README.md"])
        self.assertEqual(got["docs"], "true")
        self.assertEqual(got["backend"], "false")
        self.assertEqual(got["frontend"], "false")
        self.assertEqual(got["ci_infra"], "false")
        self.assertEqual(got["darwin_bridge"], "false")

    def test_root_go_file_matches_double_star(self) -> None:
        got = classify(SEED_FILTERS, ["main.go"])
        self.assertEqual(got["backend"], "true")
        self.assertEqual(got["frontend"], "false")

    def test_star_does_not_cross_directories(self) -> None:
        got = classify("root:\n  - 'buf*.yaml'\n", ["buf.gen.yaml", "proto/buf.yaml"])
        self.assertEqual(got["root"], "true")
        got = classify("root:\n  - 'buf*.yaml'\n", ["proto/buf.yaml"])
        self.assertEqual(got["root"], "false")

    def test_negation_excludes_a_match(self) -> None:
        filters = "backend:\n  - '**/*.go'\n  - '!internal/vendor/**'\n"
        self.assertEqual(classify(filters, ["internal/vendor/x.go"])["backend"], "false")
        self.assertEqual(classify(filters, ["internal/api/x.go"])["backend"], "true")

    def test_merge_group_forces_every_declared_filter(self) -> None:
        got = classify(SEED_FILTERS, [], event="merge_group")
        self.assertTrue(all(value == "true" for value in got.values()))
        self.assertEqual(set(got), {"backend", "frontend", "darwin_bridge", "docs", "ci_infra"})

    def test_comments_and_blank_lines_are_not_patterns(self) -> None:
        filters = "docs:\n\n  # - '**/*.go'\n  - '**/*.md'\n"
        got = classify(filters, ["main.go"])
        self.assertEqual(got["docs"], "false")

    def test_a_malformed_filter_fails(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT)],
            input="",
            capture_output=True,
            text=True,
            env={**os.environ, "FILTERS": "not a filter", "EVENT_NAME": "push"},
            check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("unsupported line", proc.stderr)

    def test_github_output_includes_known_names_and_the_json(self) -> None:
        import tempfile
        fd, name = tempfile.mkstemp()
        os.close(fd)
        out = Path(name)
        try:
            proc = subprocess.run(
                [sys.executable, str(SCRIPT)],
                input="ui/src/App.tsx\n",
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "FILTERS": "frontend:\n  - 'ui/**'\nextra:\n  - 'proto/**'\n",
                    "EVENT_NAME": "pull_request",
                    "GITHUB_OUTPUT": str(out),
                },
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            text = out.read_text()
        finally:
            out.unlink(missing_ok=True)
        self.assertIn("frontend=true", text)
        self.assertIn("backend=\n", text)
        self.assertIn('"extra": "false"', text)
        self.assertIn('"frontend": "true"', text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
