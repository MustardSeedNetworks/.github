#!/usr/bin/env python3
"""Self-test for check-source.py: builds a throwaway repo tree and proves the
JSX-text gate goes red for each shape of hardcoded English, and stays quiet on
TypeScript that only looks like a text run."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

spec = importlib.util.spec_from_file_location("gate", Path(__file__).with_name("check-source.py"))
assert spec is not None and spec.loader is not None
gate = importlib.util.module_from_spec(spec)


def run_gate(source: str) -> tuple[int, str]:
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "ui" / "src"
        src.mkdir(parents=True)
        (src / "Thing.tsx").write_text(source, encoding="utf-8")
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"I18N_REPO_ROOT": tmp}):
            # ROOT and UI_SRC are read at import, so load inside the patch.
            assert spec.loader is not None
            spec.loader.exec_module(gate)
            with contextlib.redirect_stdout(out):
                code = gate.main()
        return code, out.getvalue()


class FindsEnglish(unittest.TestCase):
    def assert_found(self, source: str, snippet: str) -> None:
        code, out = run_gate(source)
        self.assertEqual(code, 1, out)
        self.assertIn(f"ui/src/Thing.tsx:1: {snippet}\n", out)

    def test_prose(self) -> None:
        self.assert_found("<p>Sign in to continue</p>", "Sign in to continue")

    def test_single_word(self) -> None:
        # .github#100: PROSE needed two words, so a heading passed.
        self.assert_found("<h2>Statistics</h2>", "Statistics")

    def test_text_that_ends_at_an_expression(self) -> None:
        # .github#100: the text run stopped at '{' and never matched.
        self.assert_found(
            "<p>Logs go to the daemon's{' '}<code>{path}</code></p>", "Logs go to the daemon's"
        )


class IgnoresWhatIsNotEnglish(unittest.TestCase):
    def assert_clean(self, source: str) -> None:
        code, out = run_gate(source)
        self.assertEqual(code, 0, out)

    def test_interpolation_and_lowercase(self) -> None:
        self.assert_clean("<p>{t('k')}</p><td>{n} ms</td><code>eth0</code>")

    def test_acronym(self) -> None:
        self.assert_clean("<h2>RFC 2544</h2><span>LLDP</span>")

    def test_typescript_generics_and_arrows(self) -> None:
        self.assert_clean(
            "const f = async (): Promise<void> => { await go(); };\n"
            "const m = new Map<string, Device>();\n"
            "items.filter((d) => Boolean(d)).map((d) => <Row key={d.id} />);\n"
        )

    def test_comment(self) -> None:
        self.assert_clean("<p>{/* Renders the list */}</p>")

    def test_marker(self) -> None:
        self.assert_clean("// allow-hardcoded: product name\n<option>PostgreSQL</option>")


if __name__ == "__main__":
    unittest.main(verbosity=2)
