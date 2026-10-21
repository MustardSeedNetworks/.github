#!/usr/bin/env python3
"""Self-tests for the fleet TypeScript strictness gate."""

from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

CHECKER = Path(__file__).with_name("check-tsconfig-flags.py")
_spec = importlib.util.spec_from_file_location("check_tsconfig_flags", CHECKER)
assert _spec is not None and _spec.loader is not None
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
REQUIRED: dict[str, bool] = _module.REQUIRED


def tsconfig(overrides: dict[str, str]) -> str:
    flags = {flag: str(want).lower() for flag, want in REQUIRED.items()}
    flags.update(overrides)
    body = ",\n".join(f'    "{flag}": {value}' for flag, value in flags.items() if value)
    # The path glob and the comments are the JSONC shapes that broke the
    # strip-then-parse reader this gate replaced.
    return (
        "{\n  // strictness contract\n  \"compilerOptions\": {\n"
        '    "paths": { "@/*": ["./src/*"] },\n'
        f"{body}\n  }}\n}}\n"
    )


class TsconfigFlagsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def run_checker(self, content: str | None) -> subprocess.CompletedProcess[str]:
        if content is not None:
            config = self.root / "ui" / "tsconfig.app.json"
            config.parent.mkdir(parents=True)
            config.write_text(content, encoding="utf-8")
        return subprocess.run(
            ["python3", str(CHECKER), "--root", str(self.root)],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_full_contract_passes(self) -> None:
        result = self.run_checker(tsconfig({}))
        self.assertEqual(0, result.returncode, result.stdout)

    def test_missing_flag_fails(self) -> None:
        result = self.run_checker(tsconfig({"noUncheckedIndexedAccess": ""}))
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertIn("noUncheckedIndexedAccess is missing", result.stdout)

    def test_wrong_value_fails(self) -> None:
        result = self.run_checker(tsconfig({"verbatimModuleSyntax": "false"}))
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertIn("verbatimModuleSyntax is false", result.stdout)

    def test_commented_out_flag_counts_as_missing(self) -> None:
        content = tsconfig({}).replace('    "strict": true', '    // "strict": true')
        result = self.run_checker(content)
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertIn("strict is missing", result.stdout)

    def test_repo_without_ui_passes(self) -> None:
        result = self.run_checker(None)
        self.assertEqual(0, result.returncode, result.stdout)


if __name__ == "__main__":
    unittest.main()
