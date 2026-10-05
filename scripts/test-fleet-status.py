#!/usr/bin/env python3
"""Self-tests for fleet-status.py.

The page is only worth reading if a red main, an unreadable repo or a stalled
row shows up on it, so each case feeds that state in and asserts it comes out.
GitHub is replaced by a dict of canned responses; working trees are real
throwaway git repositories.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("fleet_status", Path(__file__).with_name("fleet-status.py"))
fs = importlib.util.module_from_spec(SPEC)
# dataclasses resolves annotations through sys.modules.
sys.modules[SPEC.name] = fs
SPEC.loader.exec_module(fs)

NOW = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)

PLAN = """\
# Widget v1 plan

## Owner decisions

| ID / entry | State | Details |
| --- | --- | --- |
| Entry 1 | Details | [Full](#plan-detail-1) |

## Phase 1: truth

| ID / entry | State | Details |
| --- | --- | --- |
| W-1 | DONE abc1234 | [Full](#plan-detail-2) |
| W-2 | IN-PROGRESS (macOS leg) | [Full](#plan-detail-3) |
| W-3 | TODO | [Full](#plan-detail-4) |
| W-4 | WITHDRAWN | [Full](#plan-detail-5) |

Unrelated table, not an index:

| Tool | Version |
| --- | --- |
| Go | 1.27.1 |

## Phase 2: release

| ID / entry | State | Details |
| --- | --- | --- |
| W-5 | BLOCKED | [Full](#plan-detail-6) |
"""


def fake_api(responses: dict[str, object]):
    def api(path: str) -> object:
        value = responses.get(path)
        if value is None:
            raise fs.ApiError("HTTP 404: Not Found")
        if isinstance(value, fs.ApiError):
            raise value
        return value

    return api


def repo_responses(repo: str, runs: list[dict], pulls: list[dict] | None = None) -> dict[str, object]:
    return {
        f"repos/{repo}/commits/main": {"sha": "f" * 40},
        f"repos/{repo}/actions/runs?head_sha={'f' * 40}&per_page=100": {"workflow_runs": runs},
        f"repos/{repo}/pulls?state=open&per_page=100": pulls or [],
        f"repos/{repo}/releases/latest": {"tag_name": "v1.2.3"},
        f"repos/{repo}/compare/v1.2.3...main": {"ahead_by": 4},
    }


def run(name: str, conclusion: str | None, status: str = "completed") -> dict:
    return {"name": name, "status": status, "conclusion": conclusion}


def pr(number: int, *, armed: bool = False, draft: bool = False, created: str = "2026-09-23T12:00:00+00:00") -> dict:
    return {
        "number": number,
        "title": "fix: a | pipe",
        "user": {"login": "renovate[bot]"},
        "created_at": created,
        "auto_merge": {"merge_method": "squash"} if armed else None,
        "draft": draft,
    }


class PlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp())
        (self.dir / "widget-v1-plan.md").write_text(PLAN)
        (self.dir / "notes.md").write_text(PLAN)  # not a plan of record: ignored

    def test_reads_only_index_tables_with_their_section(self) -> None:
        rows = fs.parse_plan(self.dir / "widget-v1-plan.md")
        self.assertEqual([r.row_id for r in rows], ["Entry 1", "W-1", "W-2", "W-3", "W-4", "W-5"])
        self.assertEqual(rows[2].section, "Phase 1: truth")
        self.assertEqual(rows[5].section, "Phase 2: release")

    def test_lists_moving_rows_and_counts_the_rest(self) -> None:
        page = "\n".join(fs.plans_section(self.dir))
        self.assertIn("| widget-v1-plan.md | 6 | BLOCKED 1, DETAILS 1, DONE 1, IN-PROGRESS 1, TODO 1, WITHDRAWN 1 |", page)
        self.assertIn("| widget-v1-plan.md | Phase 1: truth | W-2 | IN-PROGRESS (macOS leg) |", page)
        self.assertIn("| widget-v1-plan.md | Phase 2: release | W-5 | BLOCKED |", page)
        for settled in ("W-1", "W-3", "W-4", "Entry 1"):
            self.assertNotIn(f"| {settled} |", page)
        self.assertNotIn("notes.md", page)


class GitHubTests(unittest.TestCase):
    def test_red_main_names_the_failing_workflows(self) -> None:
        api = fake_api(repo_responses("o/a", [run("CI", "failure"), run("CodeQL", "success"), run("Lint", "cancelled")]))
        self.assertEqual(fs.main_ci(api, "o/a"), "RED: CI, Lint")

    def test_skipped_runs_are_green_and_unfinished_ones_running(self) -> None:
        green = fake_api(repo_responses("o/a", [run("CI", "success"), run("Retry", "skipped")]))
        self.assertEqual(fs.main_ci(green, "o/a"), "green")
        busy = fake_api(repo_responses("o/a", [run("CI", "success"), run("Release", None, "in_progress")]))
        self.assertEqual(fs.main_ci(busy, "o/a"), "running (1)")

    def test_one_unreadable_repo_does_not_hide_the_others(self) -> None:
        responses = repo_responses("o/good", [run("CI", "success")], [pr(7, armed=True), pr(8), pr(9, draft=True)])
        responses["repos/o/bad/commits/main"] = fs.ApiError("HTTP 403: Resource not accessible by integration")
        responses["repos/o/bad/pulls?state=open&per_page=100"] = fs.ApiError("HTTP 403: Resource not accessible")
        page = "\n".join(fs.github_sections(fake_api(responses), ["o/bad", "o/good"], NOW))
        self.assertIn("| bad | unreadable: HTTP 403: Resource not accessible by integration | none |", page)
        self.assertIn("| good | green | v1.2.3 | 4 | 3 |", page)
        self.assertIn("| good | #7 | fix: a \\| pipe | renovate[bot] | 3 d | armed |", page)
        self.assertIn("| good | #8 |", page)
        self.assertTrue(any(line.startswith("| good | #8 ") and line.endswith("| no |") for line in page.splitlines()))
        self.assertTrue(any(line.startswith("| good | #9 ") and line.endswith("| draft |") for line in page.splitlines()))

    def test_stuck_lists_old_armed_and_long_unarmed_prs_only(self) -> None:
        pulls = [
            pr(1, armed=True),  # 3 d armed: stuck
            pr(2, armed=True, created="2026-09-25T12:00:00+00:00"),  # 24 h armed: fine
            pr(3),  # 3 d unarmed: still waiting on a human, not stuck yet
            pr(4, created="2026-09-18T12:00:00+00:00"),  # 8 d unarmed: stuck
            pr(5, draft=True, created="2026-09-01T12:00:00+00:00"),  # draft: never stuck
        ]
        page = fs.github_sections(fake_api(repo_responses("o/a", [run("CI", "success")], pulls)), ["o/a"], NOW)
        stuck = page[: page.index("## Repositories")]
        numbers = [line.split("|")[2].strip() for line in stuck if line.startswith("| a |")]
        self.assertEqual(numbers, ["#1", "#4"])

    def test_nothing_stuck_says_none(self) -> None:
        page = fs.github_sections(fake_api(repo_responses("o/a", [run("CI", "success")], [pr(2, armed=True, created="2026-09-26T10:00:00+00:00")])), ["o/a"], NOW)
        self.assertEqual(page[: page.index("## Repositories")][-2], "None.")


class DriverTests(unittest.TestCase):
    def test_absent_state_says_not_collected(self) -> None:
        self.assertIn("Not collected", "\n".join(fs.driver_section(None, NOW)))

    def test_renders_the_watchdogs_verdict(self) -> None:
        state = {
            "seed": {
                "alerts": {"overdue": {"since_us": 1}},
                "last_finished": {"at_us": 1790409600000000, "status": "failed", "reason": "spend limit"},
                "last_success": {"at_us": 1790323200000000},
            },
            "ui": {"alerts": {}, "last_finished": {}, "last_success": {}},
        }
        path = Path(tempfile.mkdtemp()) / "state.json"
        path.write_text(json.dumps(state))
        page = "\n".join(fs.driver_section(path, NOW))
        self.assertIn("| seed | 2026-09-26 08:00Z (4 h ago) | failed: spend limit | 2026-09-25 08:00Z (28 h ago) | overdue |", page)
        self.assertIn("| ui | never | ? | never | none |", page)


class WorktreeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        for name, branch in (("widget", "main"), ("widget-fix", "fix/thing"), ("widget-new", "feat/new")):
            path = self.root / name
            subprocess.run(["git", "init", "-q", "-b", branch, str(path)], check=True)
            subprocess.run(
                ["git", "-C", str(path), "remote", "add", "origin", "https://github.com/o/widget.git"], check=True
            )
        (self.root / "widget-fix" / "a.txt").write_text("x")
        (self.root / "widget-fix" / "b.txt").write_text("y")
        (self.root / "not-a-repo").mkdir()

    def test_branch_dirty_count_and_pr_state(self) -> None:
        api = fake_api({"repos/o/widget/pulls?state=all&head=o:fix/thing&per_page=5": [{"number": 5, "merged_at": "x", "state": "closed"}]})
        page = "\n".join(fs.worktrees_section(api, [self.root]))
        self.assertIn(f"| {self.root / 'widget'} | main | 0 | — |", page)
        self.assertIn(f"| {self.root / 'widget-fix'} | fix/thing | 2 | merged (#5) |", page)
        self.assertIn(f"| {self.root / 'widget-new'} | feat/new | 0 | unreadable: HTTP 404: Not Found |", page)
        self.assertNotIn("not-a-repo", page)

    def test_no_roots_says_not_collected(self) -> None:
        self.assertIn("Not collected", "\n".join(fs.worktrees_section(fake_api({}), [])))


class RenderTests(unittest.TestCase):
    def test_runner_page_has_every_section(self) -> None:
        plans = Path(tempfile.mkdtemp())
        (plans / "widget-v1-plan.md").write_text(PLAN)
        args = argparse.Namespace(plans=plans, repo=["o/a"], watchdog_state=None, worktrees=[])
        page = fs.render(args, fake_api(repo_responses("o/a", [run("CI", "success")])), NOW)
        headings = [line for line in page.splitlines() if line.startswith("## ")]
        self.assertEqual(
            headings, ["## Driver health", "## Stuck pull requests", "## Repositories", "## Open pull requests", "## Plans", "## Working trees"]
        )


if __name__ == "__main__":
    unittest.main()
