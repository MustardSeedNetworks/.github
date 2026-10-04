#!/usr/bin/env python3
"""Self-test for check-copy.py: builds a throwaway repo tree and proves the gate
goes red for each failure class, green when the tree matches its baseline, and
quiet on the shapes that are not copy."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

spec = importlib.util.spec_from_file_location("gate", Path(__file__).with_name("check-copy.py"))
assert spec is not None and spec.loader is not None
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class Tree:
    def __init__(self, source: str) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.src = self.root / "ui" / "src"
        self.src.mkdir(parents=True)
        (self.src / "Thing.tsx").write_text(source, encoding="utf-8")

    def keys(self) -> list[str]:
        return sorted({key for key, _, _, _ in gate.sites(self.src, self.root)})

    def baseline(self, text: str, rel: str = "scripts/i18n/copy-baseline.txt") -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def run_gate(self, **env: str) -> tuple[int, str]:
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"I18N_REPO_ROOT": str(self.root), **env}):
            with contextlib.redirect_stdout(out):
                code = gate.main()
        return code, out.getvalue()

    def cleanup(self) -> None:
        self.tmp.cleanup()


def keys_for(source: str) -> list[str]:
    tree = Tree(source)
    try:
        return tree.keys()
    finally:
        tree.cleanup()


class FindsCopy(unittest.TestCase):
    def test_copy_prop_value(self) -> None:
        self.assertEqual(
            keys_for('<button aria-label="Refresh" />'),
            ["ui/src/Thing.tsx copy-prop aria-label=Refresh"],
        )

    def test_prop_value_of_any_length(self) -> None:
        # A single word is still read out by a screen reader.
        self.assertEqual(len(keys_for('<Input placeholder="Password" />')), 1)

    def test_string_in_a_jsx_expression(self) -> None:
        self.assertEqual(
            keys_for("<p>{loading ? 'Loading the rows' : rows.length}</p>"),
            ["ui/src/Thing.tsx literal Loading the rows"],
        )

    def test_string_in_a_label_map(self) -> None:
        self.assertEqual(
            keys_for("const L = { failed: 'Failed to load users' };"),
            ["ui/src/Thing.tsx literal Failed to load users"],
        )

    def test_prop_value_with_an_apostrophe(self) -> None:
        # .github#100: the value class stopped at either quote.
        self.assertIn(
            "ui/src/Thing.tsx copy-prop title=Reads the walk. Doesn't modify the file.",
            keys_for('<b title="Reads the walk. Doesn\'t modify the file." />'),
        )

    def test_literal_with_an_apostrophe(self) -> None:
        self.assertEqual(
            keys_for('const L = { role: "Choose this stem\'s role" };'),
            ["ui/src/Thing.tsx literal Choose this stem's role"],
        )

    def test_single_word_in_a_child_ternary(self) -> None:
        # .github#100: LITERAL needs two words, so both branches passed.
        self.assertEqual(
            keys_for("<Button>{saving ? 'Saving…' : 'Save'}</Button>"),
            ["ui/src/Thing.tsx child Save", "ui/src/Thing.tsx child Saving…"],
        )

    def test_child_after_text_and_logical_branches(self) -> None:
        self.assertEqual(
            keys_for("<td>State: {ok && 'VALID'}{name ?? 'Unknown'}</td>"),
            ["ui/src/Thing.tsx child Unknown", "ui/src/Thing.tsx child VALID"],
        )

    def test_child_prose_is_reported_once(self) -> None:
        self.assertEqual(
            keys_for("<p>{busy ? 'Saving the rows' : 'Save'}</p>"),
            ["ui/src/Thing.tsx child Save", "ui/src/Thing.tsx literal Saving the rows"],
        )


class IgnoresWhatIsNotCopy(unittest.TestCase):
    def assert_clean(self, source: str) -> None:
        self.assertEqual(keys_for(source), [])

    def test_locale_key_argument(self) -> None:
        self.assert_clean("const x = t('Refresh the rows');")

    def test_prose_inside_a_comment(self) -> None:
        self.assert_clean("/* Renders the device list for this profile. */")

    def test_log_line(self) -> None:
        self.assert_clean("logger.warn('discovery', 'Failed to fetch service status');")

    def test_example_values(self) -> None:
        self.assert_clean(
            '<Input placeholder="192.168.1.1" />'
            '<Input placeholder="google.com" />'
            '<Input placeholder="rtsp://host:554/stream" />'
            '<Input placeholder="alice" />'
        )

    def test_code_token_that_reads_like_prose(self) -> None:
        # "Content-Type" and the tail of a ternary both look like two words to a
        # separator class that owns the hyphen or the quote.
        self.assert_clean("h['Content-Type'] = 'application/json';\nconst m = 'Hide';")

    def test_class_names_and_ids(self) -> None:
        self.assert_clean('<div className="flex items-center" data-testid="thing-row" />')

    def test_child_expression_that_does_not_show_its_strings(self) -> None:
        self.assert_clean(
            "<p>{status === 'ok' ? n : m}</p>"
            "<p>{' '}</p>"
            "<p>{PRESETS[preset ?? 'common'].label}</p>"
            "<p>{rows.map((r) => r.name ?? 'Unknown')}</p>"
            "<i className={`${base} ${on ? 'text-brand' : 'text-muted'}`} />"
        )

    def test_typescript_after_a_generic(self) -> None:
        # Both open a '{' straight after a '>' and hold `key: 'value'`.
        self.assert_clean(
            "const SIZE: Record<Size, string> = { sm: 'Small', md: 'Medium' };\n"
            "function f(): Promise<void> { const m = ok ? 'Yes' : 'No'; }\n"
            "const g = (x: number) => { return x ? 'Yes' : 'No' }\n"
        )

    def test_test_and_story_files_are_out_of_scope(self) -> None:
        tree = Tree("")
        try:
            (tree.src / "Thing.stories.tsx").write_text('<b aria-label="Refresh" />')
            (tree.src / "Thing.test.tsx").write_text('<b aria-label="Refresh" />')
            self.assertEqual(tree.keys(), [])
        finally:
            tree.cleanup()


class Ratchet(unittest.TestCase):
    def setUp(self) -> None:
        self.tree = Tree('<button aria-label="Refresh" />')

    def tearDown(self) -> None:
        self.tree.cleanup()

    def test_baselined_site_passes(self) -> None:
        self.tree.baseline(
            "# the reason\nui/src/Thing.tsx copy-prop aria-label=Refresh  # tail reason\n"
        )
        code, out = self.tree.run_gate()
        self.assertEqual(code, 0, out)

    def test_new_site_fails(self) -> None:
        self.tree.baseline("")
        code, out = self.tree.run_gate()
        self.assertEqual(code, 1)
        self.assertIn("::error file=ui/src/Thing.tsx::", out)

    def test_stale_entry_fails(self) -> None:
        self.tree.baseline(
            "ui/src/Thing.tsx copy-prop aria-label=Refresh\nui/src/Gone.tsx literal Was here once\n"
        )
        code, out = self.tree.run_gate()
        self.assertEqual(code, 1)
        self.assertIn("ui/src/Gone.tsx literal Was here once", out)

    def test_missing_baseline_fails(self) -> None:
        # The gate cannot tell "nothing baselined" from "wrong path"; validate.sh
        # decides whether a repo without the file runs it at all.
        code, out = self.tree.run_gate()
        self.assertEqual(code, 1)
        self.assertIn("not found", out)

    def test_baseline_and_source_paths_come_from_env(self) -> None:
        (self.tree.root / "web").mkdir()
        (self.tree.src / "Thing.tsx").rename(self.tree.root / "web" / "Thing.tsx")
        self.tree.baseline("web/Thing.tsx copy-prop aria-label=Refresh\n", rel="copy.txt")
        code, out = self.tree.run_gate(UI_SRC_DIR="web", COPY_BASELINE="copy.txt")
        self.assertEqual(code, 0, out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
