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
import os
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


DETAILED_PLAN = """\
# Widget v1 plan

## Rows

| ID / entry | State | Details |
| --- | --- | --- |
| W-1 | {w1} | [Full](#plan-detail-1) |
| W-2 | {w2} | [Full](#plan-detail-2) |
| W-3 | DONE | [Full](#plan-detail-3) |

## Plan row details

### Plan detail 1

ID:

W-1

Task:

Add the floor editor
to the survey page.

Status:

done

### Plan detail 2

ID:

W-2

Task:

`TestReflectorRuns` flakes under load; fix the race.

### Plan detail 3

ID:

W-3

Task:

Old work.
"""

QUEUE = """\
## 3. Rows defined here

| ID | Driver | Sev | Issue | State |
| --- | --- | --- | --- | --- |
| D-SEED-1 | seed | high | seed#10 | {d1} |
| G-1 | ui | low | .github#5 | DONE |

**D-SEED-1.** The merge queue ejects PRs when the Storybook
job hangs. *Acceptance:* it does not.

**G-1.** Old support work.

## 4. Owner actions
"""


class PlanDetailTests(unittest.TestCase):
    def test_index_rows_carry_their_linked_task(self) -> None:
        rows = fs.parse_index("widget-v1-plan.md", DETAILED_PLAN.format(w1="DONE", w2="TODO"))
        self.assertEqual(rows[0].task, "Add the floor editor to the survey page.")
        self.assertEqual(rows[1].task, "`TestReflectorRuns` flakes under load; fix the race.")

    def test_queue_rows_carry_their_paragraph_and_issue(self) -> None:
        rows = fs.parse_queue("msn-master-queue-x.md", QUEUE.format(d1="DONE"))
        self.assertEqual([(r.row_id, r.state, fs.row_repo(r)) for r in rows], [("D-SEED-1", "DONE", "seed"), ("G-1", "DONE", fs.SUPPORT)])
        self.assertEqual(rows[0].task, "The merge queue ejects PRs when the Storybook job hangs.")

    def test_ci_process_keywords(self) -> None:
        def ci(task: str) -> bool:
            return fs.is_ci_process(fs.Row("p", "s", "X-1", "DONE", task))

        self.assertTrue(ci("`TestCollectorCloseStopsTheSampler` fails on healthy code"))
        self.assertTrue(ci("The Storybook CI job hangs until its timeout"))
        self.assertTrue(ci("Bump every consumer to v0.5.5"))
        # A Go test name is case-sensitive: "testing" and "tests" are product prose.
        self.assertFalse(ci("Y.1564 testing cannot tell a host stall from path delay"))
        self.assertFalse(ci("Place, move and delete an AP through the API."))


class CILoadTests(unittest.TestCase):
    NOW = datetime(2026, 10, 15, 6, 0, tzinfo=UTC)

    def git(self, *args: str, when: str | None = None) -> None:
        env = {"GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when} if when else {}
        subprocess.run(
            ["git", "-C", str(self.dir), "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args],
            check=True,
            capture_output=True,
            env={**os.environ, **env},
        )

    def commit(self, w1: str, w2: str, d1: str, when: str) -> None:
        (self.dir / "widget-v1-plan.md").write_text(DETAILED_PLAN.format(w1=w1, w2=w2))
        (self.dir / "msn-master-queue-x.md").write_text(QUEUE.format(d1=d1))
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "plan", when=when)

    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp())
        self.git("init", "-q", "-b", "main")
        self.commit("TODO", "TODO", "TODO", "2026-10-01T12:00:00+00:00")
        self.commit("DONE", "DONE", "DONE", "2026-10-12T12:00:00+00:00")
        days = ["2026-10-08", "2026-10-09", "2026-10-10", "2026-10-11", "2026-10-12", "2026-10-13", "2026-10-14"]
        self.responses: dict[str, object] = {}
        for day in days:
            self.responses[f"repos/o/widget/actions/runs?created={day}&per_page=1"] = {"total_count": 100}
            self.responses[f"repos/o/widget/actions/runs?created={day}&status=failure&per_page=1"] = {"total_count": 5}
        self.responses["repos/o/bad/actions/runs?created=2026-10-08&per_page=1"] = fs.ApiError("HTTP 403: Forbidden")

    def test_rows_done_this_week_split_by_repo_and_kind(self) -> None:
        fs.PLAN_REPOS["widget-v1-plan.md"] = "widget"
        self.addCleanup(fs.PLAN_REPOS.pop, "widget-v1-plan.md")
        page = "\n".join(fs.ci_load_section(fake_api(self.responses), ["o/widget", "o/seed", "o/bad"], self.dir, self.NOW))
        self.assertIn("2026-10-08 to 2026-10-14", page)
        # W-1 product, W-2 a flaky test: one of two. W-3 was DONE before the window.
        self.assertIn("| widget | 100 | 5.0 | 5.0% | 2 | 1 (50%) |", page)
        self.assertIn("| seed | unreadable: HTTP 404: Not Found | — | — | 1 | 1 (100%) |", page)
        self.assertIn("| bad | unreadable: HTTP 403: Forbidden | — | — | 0 | 0 |", page)
        # G-1 was DONE in both commits, so the support line stays out.
        self.assertNotIn(fs.SUPPORT, page)

    def test_no_history_before_the_window_says_so(self) -> None:
        page = "\n".join(fs.ci_load_section(fake_api(self.responses), ["o/widget"], Path(tempfile.mkdtemp()), self.NOW))
        self.assertIn("Rows done: not collected, the plans checkout has no commit before 2026-10-08", page)
        self.assertIn("| widget | 100 | 5.0 | 5.0% | — | — |", page)


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
            headings, ["## Driver health", "## Stuck pull requests", "## Repositories", "## Open pull requests", "## Plans", "## CI load", "## Working trees"]
        )


if __name__ == "__main__":
    unittest.main()
