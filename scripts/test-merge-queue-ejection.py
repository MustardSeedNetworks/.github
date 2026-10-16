#!/usr/bin/env python3
"""Fixture runs of the shared merge-queue ejection stop (support plan G-17).

trellis#731 re-entered the merge queue 294 times because nothing counted its
failed-checks ejections. Each case runs the workflow step's real script against
a stand-in `gh` that serves a fixture timeline and records every call, so the
stop must fire on the second failure, stay quiet on the first and on every
removal that is not a check failure, and restart its count only after its own
comment.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "merge-queue-ejection.yml"
STEP = "      - name: Stop a PR that keeps failing in the merge queue\n"
MARKER = "<!-- merge-queue-ejection -->"


def step_script() -> str:
    """The step's `run: |` block, exactly as the runner receives it."""
    lines = WORKFLOW.read_text().splitlines(keepends=True)
    start = lines.index(STEP)
    run = next(i for i in range(start, len(lines)) if lines[i].strip() == "run: |")
    body = []
    for line in lines[run + 1:]:
        if line.strip() and not line.startswith(" " * 10):
            break
        body.append(line)
    return textwrap.dedent("".join(body))


SCRIPT = step_script()

# Serves the two reads the step makes and logs everything else it runs.
FAKE_GH = """\
#!/usr/bin/env python3
import json, os, sys
fixtures = os.environ["FAKE_GH_DIR"]
args = sys.argv[1:]
query = next((a[len("query="):] for a in args if a.startswith("query=")), "")
if args[:2] == ["api", "graphql"] and "--paginate" in args:
    for node in json.load(open(os.path.join(fixtures, "timeline.json"))):
        print(json.dumps(node))
elif args[:2] == ["api", "graphql"] and "isInMergeQueue" in query:
    print(open(os.path.join(fixtures, "pr.json")).read())
else:
    with open(os.path.join(fixtures, "calls.jsonl"), "a") as fh:
        fh.write(json.dumps(args) + "\\n")
"""


def removed(minute: int, reason: str) -> dict:
    return {"__typename": "RemovedFromMergeQueueEvent",
            "createdAt": f"2026-10-07T14:{minute:02d}:00Z", "reason": reason}


def comment(minute: int, login: str, body: str = MARKER) -> dict:
    return {"__typename": "IssueComment", "createdAt": f"2026-10-07T14:{minute:02d}:00Z",
            "body": body, "author": {"login": login}}


def pr(author: str = "renovate", queued: bool = False, armed: bool = True) -> dict:
    return {"id": "PR_kwDO731", "isInMergeQueue": queued,
            "autoMergeRequest": {"enabledAt": "2026-10-06T10:58:55Z"} if armed else None,
            "author": {"login": author}}


class MergeQueueEjection(unittest.TestCase):
    def run_step(self, timeline: list[dict], state: dict) -> tuple[int, str, list[list[str]]]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bin").mkdir()
            gh = root / "bin" / "gh"
            gh.write_text(FAKE_GH)
            gh.chmod(0o755)
            (root / "timeline.json").write_text(json.dumps(timeline))
            (root / "pr.json").write_text(json.dumps(state))
            work = root / "work"
            work.mkdir()
            env = dict(os.environ, PATH=f"{root / 'bin'}:{os.environ['PATH']}",
                       FAKE_GH_DIR=str(root), REPO="MustardSeedNetworks/trellis", PR="731",
                       GH_TOKEN="unused")
            # GitHub's `bash -e {0}` shell, which the step runs under.
            proc = subprocess.run(["bash", "-e", "-c", SCRIPT], cwd=work, env=env,
                                  capture_output=True, text=True)
            log = root / "calls.jsonl"
            calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
            return proc.returncode, proc.stdout + proc.stderr, calls

    @staticmethod
    def mutations(calls: list[list[str]]) -> list[str]:
        return [a.split("{")[1].split("(")[0].strip()
                for call in calls for a in call if a.startswith("query=mutation")]

    @staticmethod
    def comments(calls: list[list[str]]) -> list[str]:
        return [call[call.index("--body") + 1] for call in calls if call[:2] == ["pr", "comment"]]

    def test_first_failure_is_retried(self) -> None:
        code, out, calls = self.run_step([removed(1, "failed_checks")], pr())
        self.assertEqual(code, 0, out)
        self.assertIn("1 failed-checks ejection(s)", out)
        self.assertEqual(calls, [])

    def test_second_failure_stops_a_renovate_pr(self) -> None:
        code, out, calls = self.run_step([removed(1, "failed_checks"), removed(9, "failed_checks")], pr())
        self.assertEqual(code, 0, out)
        self.assertEqual(self.mutations(calls), ["disablePullRequestAutoMerge"])
        self.assertIn(["pr", "edit", "731", "--repo", "MustardSeedNetworks/trellis",
                       "--add-label", "stop-updating"], calls)
        self.assertTrue(any(c[:3] == ["label", "create", "stop-updating"] for c in calls), calls)
        [body] = self.comments(calls)
        self.assertTrue(body.startswith(MARKER), body)
        self.assertIn("remove `stop-updating`", body)

    def test_a_pr_already_back_in_the_queue_is_dequeued(self) -> None:
        code, out, calls = self.run_step([removed(1, "failed_checks"), removed(9, "failed_checks")],
                                         pr(queued=True, armed=False))
        self.assertEqual(code, 0, out)
        self.assertEqual(self.mutations(calls), ["dequeuePullRequest"])

    def test_a_human_pr_is_disarmed_without_the_renovate_label(self) -> None:
        code, out, calls = self.run_step([removed(1, "failed_checks"), removed(9, "failed_checks")],
                                         pr(author="krisarmstrong"))
        self.assertEqual(code, 0, out)
        self.assertEqual(self.mutations(calls), ["disablePullRequestAutoMerge"])
        self.assertFalse(any("stop-updating" in c for call in calls for c in call[:-1]), calls)
        [body] = self.comments(calls)
        self.assertNotIn("stop-updating", body)
        self.assertIn("gh pr merge --auto", body)

    def test_only_check_failures_count(self) -> None:
        timeline = [removed(1, "merge_conflict"), removed(2, "checks_timed_out"),
                    removed(3, "failed_checks")]
        code, out, calls = self.run_step(timeline, pr())
        self.assertEqual(code, 0, out)
        self.assertEqual(calls, [])

    def test_the_count_restarts_after_its_own_stop(self) -> None:
        timeline = [removed(1, "failed_checks"), removed(2, "failed_checks"),
                    comment(3, "github-actions"), removed(4, "failed_checks")]
        code, out, calls = self.run_step(timeline, pr())
        self.assertEqual(code, 0, out)
        self.assertEqual(calls, [])

    def test_a_marker_from_anyone_else_does_not_restart_it(self) -> None:
        timeline = [removed(1, "failed_checks"), comment(2, "krisarmstrong"),
                    removed(4, "failed_checks")]
        code, out, calls = self.run_step(timeline, pr())
        self.assertEqual(code, 0, out)
        self.assertEqual(self.mutations(calls), ["disablePullRequestAutoMerge"])

    def test_the_timeline_is_read_in_time_order(self) -> None:
        timeline = [removed(4, "failed_checks"), comment(3, "github-actions"),
                    removed(1, "failed_checks"), removed(2, "failed_checks")]
        code, out, calls = self.run_step(timeline, pr())
        self.assertEqual(code, 0, out)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
