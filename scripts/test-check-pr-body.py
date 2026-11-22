#!/usr/bin/env python3
"""Self-tests for check-pr-body.py.

The checker reads its rules from pr-hygiene.yml, so these cases run it against
a pinned copy of that workflow (fixtures/pr-hygiene.yml). They assert each rule
fires on a violating PR and that a workflow with a rule removed is rejected,
instead of passing on rules the script made up.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).parent
CHECKER = HERE / "check-pr-body.py"
WORKFLOW = HERE / "fixtures" / "pr-hygiene.yml"

GOOD_BODY = """\
## Summary

Does a thing.

## Linked Issue

Fixes #12

## Testing Evidence

```text
$ make test
ok
```

## Security and Release Checklist

- [x] done
"""


def run(
    title: str, body: str, workflow: Path = WORKFLOW
) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "body.md"
        f.write_text(body, encoding="utf-8")
        return subprocess.run(
            [
                sys.executable,
                str(CHECKER),
                "--title",
                title,
                "--body-file",
                str(f),
                "--workflow",
                str(workflow),
            ],
            capture_output=True,
            text=True,
            check=False,
        )


class CheckPRBody(unittest.TestCase):
    def test_good_passes(self) -> None:
        r = run("fix(api): handle empty body", GOOD_BODY)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_missing_heading(self) -> None:
        r = run("fix: ok title", GOOD_BODY.replace("## Linked Issue", "## Linked"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("Missing ## Linked Issue", r.stderr)

    def test_heading_inside_fence_does_not_count(self) -> None:
        body = GOOD_BODY.replace("## Summary\n", "```\n## Summary\n```\n", 1)
        r = run("fix: ok title", body)
        self.assertEqual(
            r.returncode,
            0,
            "line-anchored match accepts a fenced heading too; parity with the lint",
        )

    def test_issue_link_needs_number_sign(self) -> None:
        r = run("fix: ok title", GOOD_BODY.replace("Fixes #12", "Fixes 12"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("Link the tracked issue", r.stderr)

    def test_related_to_accepted(self) -> None:
        self.assertEqual(
            run(
                "fix: ok title", GOOD_BODY.replace("Fixes #12", "related to #3")
            ).returncode,
            0,
        )

    def test_unclosed_evidence_fence_fails(self) -> None:
        body = GOOD_BODY.replace("ok\n```\n", "ok\n")
        r = run("fix: ok title", body)
        self.assertEqual(r.returncode, 1)
        self.assertIn("Testing Evidence", r.stderr)

    def test_not_run_reason_accepted(self) -> None:
        body = GOOD_BODY.replace("```text\n$ make test\nok\n```", "Not run: docs only")
        self.assertEqual(run("docs: ok title", body).returncode, 0)

    def test_empty_fence_passes_the_lint_but_warns(self) -> None:
        # The lint's regex counts the `text` info string as content, so the
        # unfilled template passes CI. Parity means passing here too.
        body = GOOD_BODY.replace("$ make test\nok\n", "")
        r = run("fix: ok title", body)
        self.assertEqual(r.returncode, 0)
        self.assertIn("WARN", r.stderr)

    def test_nested_heading_in_evidence_does_not_cut_section(self) -> None:
        body = GOOD_BODY.replace("ok\n```", "### RED\nfail\n### GREEN\nok\n```")
        self.assertEqual(run("fix: ok title", body).returncode, 0)

    def test_title_uppercase_subject(self) -> None:
        r = run("fix: Handle it", GOOD_BODY)
        self.assertEqual(r.returncode, 1)
        self.assertIn("lowercase", r.stderr)

    def test_title_unknown_type(self) -> None:
        r = run("wip: handle it", GOOD_BODY)
        self.assertEqual(r.returncode, 1)
        self.assertIn("Unknown type", r.stderr)

    def test_title_not_conventional(self) -> None:
        self.assertEqual(run("handle it", GOOD_BODY).returncode, 1)

    def test_title_scope_and_breaking_marker(self) -> None:
        self.assertEqual(run("feat(api)!: drop the thing", GOOD_BODY).returncode, 0)

    def test_workflow_without_rule_is_rejected_not_ignored(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8").replace(
            "const requiredHeadings", "const renamedHeadings"
        )
        with tempfile.TemporaryDirectory() as tmp:
            wf = Path(tmp) / "pr-hygiene.yml"
            wf.write_text(text, encoding="utf-8")
            r = run("fix: ok title", GOOD_BODY, wf)
        self.assertEqual(r.returncode, 2)
        self.assertIn("requiredHeadings", r.stderr)


if __name__ == "__main__":
    unittest.main()
