#!/usr/bin/env python3
"""Write the fleet's STATUS.md: plans, open PRs, CI on main, releases.

"How will I know where it stands" had no answer that did not mean asking a
session: the plans say what each row claims, GitHub says what actually merged,
and nothing put the two side by side. This reads both and writes one page.

GitHub sections (every run):

    repositories    CI on main's head commit, latest release, commits since it
    stuck PRs       open PRs that should have merged by now (see STUCK_*)
    pull requests   every open PR with its age and whether auto-merge is armed
    plans           row counts per plan of record, and every row still moving
    CI load         failed Actions runs per day per repo, and how much of the
                    last week's completed plan rows were CI/process work

Host sections (only when their inputs are given, i.e. on the driver host):

    driver health   the claude-driver watchdog's state.json, read as-is: the
                    watchdog decides what a successful run is, this only shows it
    working trees   every checkout and worktree under the given roots with its
                    branch, dirty-file count and whether its PR merged

A GitHub runner has neither, so the reusable workflow leaves them out and says
so in the page rather than printing an empty section that reads as healthy.
Every API call that fails is reported in the cell it would have filled; one
unreadable repo never hides the others.

Usage:
    fleet-status.py --plans DIR [--repo OWNER/NAME ...] [--watchdog-state FILE]
                    [--worktrees DIR ...] [--output FILE]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

DEFAULT_REPOS = (
    "MustardSeedNetworks/seed",
    "MustardSeedNetworks/stem",
    "MustardSeedNetworks/niac-go",
    "MustardSeedNetworks/trellis",
    "MustardSeedNetworks/foundation",
    "MustardSeedNetworks/.github",
    "MustardSeedNetworks/msn-docs-internal",
    "MustardSeedNetworks/msn-internal-tools",
    "MustardSeedNetworks/niac-demo-catalog",
    "MustardSeedNetworks/mustardseednetworks-com",
    "MustardSeedNetworks/niac-java",
)

# The plans of record are the files that carry the compact row index.
PLAN_GLOB = "*plan.md"
INDEX_HEADER = "| ID / entry | State | Details |"
# States that need nobody: listed as counts only.
SETTLED = {"DONE", "SUPERSEDED", "WITHDRAWN", "TODO", "DETAILS"}
# An armed PR lands within hours once CI is green, so one still open after two
# days is red or wedged. Renovate PRs sat like that for two days in October
# 2026 with nothing reporting them (.github#107). An unarmed PR is waiting on a
# human, and a week is long enough to say so.
STUCK_ARMED_HOURS = 48
STUCK_UNARMED_HOURS = 7 * 24
RED = {"failure", "cancelled", "timed_out", "action_required", "startup_failure"}

# CI load. The owner's question (2026-10-15) was how much of the fleet's effort
# goes into CI and process rather than the product; this keeps the answer on
# the page so it can be watched instead of re-measured. Run counts come one
# UTC day at a time because the runs API caps total_count at 2,500, which the
# busiest repos pass inside a week.
CI_LOAD_DAYS = 7
PLAN_REPOS = {
    "seed-v1-plan.md": "seed",
    "stem-v1-plan.md": "stem",
    "niac-v1-plan.md": "niac-go",
    "trellis-v1-plan.md": "trellis",
}
SUPPORT = "support repos"
QUEUE_GLOB = "msn-master-queue-*.md"
# Owner decision §24 (foundation first): its rows cite the decision in their Task.
FOUNDATION_FIRST = re.compile(r"§24\b|foundation-first")
QUEUE_HEADER = "| ID | Driver | Sev | Issue | State |"
# A keyword estimate, not a judgement: on 2026-10-15 it agreed with a hand
# classification of all 698 DONE rows on CI-or-not for 83 % of them. Rows
# without a match are product work (features and product defects).
CI_PROCESS = re.compile(
    r"\bCI\b|\bci\.yml|\bworkflows?\b|GitHub Actions|\bflak|merge[ -]queue|\brenovate|release-please|goreleaser"
    r"|golangci|govulncheck|codeql|zizmor|actionlint|pre-commit|branch protection|\brulesets?\b|\bE2E\b"
    r"|playwright|\bharness\b|\brunners?\b|required checks?|toolchain|\bno-op tests?"
    r"|\btests? (?:fail|flake|hang|time out|timeout|race)|\bstranded\b|\bworktrees?\b|\brunbook\b"
    r"|immutable releases|release pipeline|\bSHA[- ]pin|(?-i:\bTest[A-Z]\w+)|\.test\.tsx?\b|\bvitest\b|\bnightly\b"
    r"|\bmake (?:build|test|lint|validate)|dependabot|\bbump|bookkeeping|check-[\w-]+\.sh|\btriage\b",
    re.IGNORECASE,
)

Api = Callable[[str], object]


class ApiError(Exception):
    pass


def gh_api(path: str) -> object:
    proc = subprocess.run(["gh", "api", path], capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        detail = (proc.stderr.strip().splitlines() or ["no output"])[-1]
        raise ApiError(detail)
    return json.loads(proc.stdout)


def cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def hours_since(stamp: str, now: datetime) -> float:
    return (now - datetime.fromisoformat(stamp)).total_seconds() / 3600


def age(stamp: str, now: datetime) -> str:
    hours = hours_since(stamp, now)
    return f"{hours:.0f} h" if hours < 48 else f"{hours / 24:.0f} d"


@dataclass
class Row:
    plan: str
    section: str
    row_id: str
    state: str
    task: str = ""


def parse_plan(path: Path) -> list[Row]:
    return parse_index(path.name, path.read_text())


def parse_index(name: str, text: str) -> list[Row]:
    """Index rows, each with the Task of the "Plan detail" its Details cell links."""
    rows: list[Row] = []
    section = ""
    in_index = False
    links: list[str | None] = []
    for line in text.splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
        if line.strip() == INDEX_HEADER:
            in_index = True
            continue
        if in_index:
            if not line.startswith("|"):
                in_index = False
                continue
            parts = [p.strip() for p in line.strip().strip("|").split("|")]
            if len(parts) < 2 or set(parts[0]) <= {"-", " "}:
                continue
            rows.append(Row(name, section, parts[0], parts[1]))
            link = re.search(r"plan-detail-(\d+)", line)
            links.append(link.group(1) if link else None)
    tasks = dict(re.findall(r"^### Plan detail (\d+)\n(?:(?!^### ).)*?^Task:\n\n(.*?)\n\n", text, re.MULTILINE | re.DOTALL))
    for row, link in zip(rows, links, strict=True):
        row.task = tasks.get(link, "").replace("\n", " ")
    return rows


def parse_queue(name: str, text: str) -> list[Row]:
    """The master queue's own rows: one table, each row's problem in a bold-ID paragraph."""
    rows: list[Row] = []
    in_table = False
    for line in text.splitlines():
        if line.strip() == QUEUE_HEADER:
            in_table = True
            continue
        if in_table:
            if not line.startswith("|"):
                break
            parts = [p.strip() for p in line.strip().strip("|").split("|")]
            if len(parts) < 5 or set(parts[0]) <= {"-", " "}:
                continue
            # The problem statement only: every Acceptance names the gates it must pass.
            body = re.search(
                rf"^\*\*{re.escape(parts[0])}\.\*\*(.*?)(?:\*Acceptance|\n\n|\Z)", text, re.MULTILINE | re.DOTALL
            )
            task = body.group(1).replace("\n", " ").strip() if body else ""
            rows.append(Row(name, parts[3], parts[0], parts[4], task))
    return rows


def state_key(state: str) -> str:
    return state.split()[0].upper() if state else "?"


def plans_section(plans_dir: Path) -> list[str]:
    out = ["## Plans", ""]
    files = sorted(p for p in plans_dir.glob(PLAN_GLOB) if INDEX_HEADER in p.read_text())
    if not files:
        return [*out, f"No plan in `{plans_dir}` carries a row index.", ""]
    moving: list[Row] = []
    out += ["| Plan | Rows | By state |", "| --- | --- | --- |"]
    for path in files:
        rows = parse_plan(path)
        counts = Counter(state_key(r.state) for r in rows)
        summary = ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))
        out.append(f"| {path.name} | {len(rows)} | {summary} |")
        moving += [r for r in rows if state_key(r.state) not in SETTLED]
    out += ["", "### Rows in flight", ""]
    if not moving:
        return [*out, "None.", ""]
    out += ["| Plan | Section | Row | State |", "| --- | --- | --- | --- |"]
    out += [f"| {r.plan} | {cell(r.section)} | {cell(r.row_id)} | {cell(r.state)} |" for r in moving]
    return [*out, ""]


def foundation_section(plans_dir: Path) -> list[str]:
    out = ["## Foundation adoption", ""]
    rows = [r for path in sorted(plans_dir.glob(PLAN_GLOB)) for r in parse_plan(path) if FOUNDATION_FIRST.search(r.task)]
    if not rows:
        return [*out, "No plan row cites msn-owner-decisions §24.", ""]
    done = sum(bool(re.match(r"\W*DONE\b", r.state)) for r in rows)
    out += [f"{done} of {len(rows)} rows done.", "", "| Plan | Row | State |", "| --- | --- | --- |"]
    out += [f"| {r.plan} | {cell(r.row_id)} | {cell(r.state)} |" for r in rows]
    return [*out, ""]


def is_ci_process(row: Row) -> bool:
    return bool(CI_PROCESS.search(row.task))


def row_repo(row: Row) -> str:
    if row.plan in PLAN_REPOS:
        return PLAN_REPOS[row.plan]
    # A queue row names its repo in the Issue cell, kept in `section`.
    issue = re.match(r"([\w.-]+)#\d+", row.section)
    return issue.group(1) if issue and issue.group(1) in PLAN_REPOS.values() else SUPPORT


def plan_rows(plans_dir: Path, rev: str | None) -> list[Row]:
    """Every indexed and queue row, at `rev` of the plans checkout or on disk."""

    def read(path: Path) -> str:
        if rev is None:
            return path.read_text()
        proc = subprocess.run(
            ["git", "-C", str(plans_dir), "show", f"{rev}:{path.name}"], capture_output=True, text=True, check=False
        )
        return proc.stdout if proc.returncode == 0 else ""

    rows: list[Row] = []
    for path in sorted(plans_dir.glob(PLAN_GLOB)):
        rows += parse_index(path.name, read(path))
    for path in sorted(plans_dir.glob(QUEUE_GLOB)):
        rows += parse_queue(path.name, read(path))
    return rows


def completed_rows(plans_dir: Path, now: datetime) -> tuple[list[Row], str]:
    """Rows DONE now that were not DONE CI_LOAD_DAYS ago, and what "ago" was."""
    since = now - timedelta(days=CI_LOAD_DAYS)
    proc = subprocess.run(
        ["git", "-C", str(plans_dir), "log", "-1", f"--before={since.isoformat()}", "--format=%h %cs"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        raise LookupError(f"the plans checkout has no commit before {since:%Y-%m-%d} (shallow clone?)")
    rev, day = proc.stdout.split()
    before = {(r.plan, r.row_id) for r in plan_rows(plans_dir, rev) if state_key(r.state) == "DONE"}
    done = [r for r in plan_rows(plans_dir, None) if state_key(r.state) == "DONE" and (r.plan, r.row_id) not in before]
    return done, f"`{rev}` ({day})"


def runs_per_day(api: Api, repo: str, days: list[str]) -> tuple[float, float]:
    total = failed = 0
    for day in days:
        total += api(f"repos/{repo}/actions/runs?created={day}&per_page=1")["total_count"]
        failed += api(f"repos/{repo}/actions/runs?created={day}&status=failure&per_page=1")["total_count"]
    return total / len(days), failed / len(days)


def ci_load_section(api: Api, repos: list[str], plans_dir: Path, now: datetime) -> list[str]:
    out = ["## CI load", ""]
    days = [f"{now - timedelta(days=n):%Y-%m-%d}" for n in range(CI_LOAD_DAYS, 0, -1)]
    collected = True
    try:
        done, since = completed_rows(plans_dir, now)
        by_repo = Counter(row_repo(r) for r in done)
        ci_by_repo = Counter(row_repo(r) for r in done if is_ci_process(r))
        rows_note = (
            f"Rows done are plan and master-queue rows whose State became DONE since {since}. The CI/process "
            "share is a keyword estimate (`CI_PROCESS` in the script), not a judgement of each row."
        )
    except LookupError as err:
        collected, by_repo, ci_by_repo = False, Counter(), Counter()
        rows_note = f"Rows done: not collected, {err}."
    out += [
        (
            f"Actions runs created {days[0]} to {days[-1]} (UTC), averaged per day; failed counts conclusion "
            f"`failure` only. {rows_note}"
        ),
        "",
        "| Repo | Runs/day | Failed/day | Failed % | Rows done | CI/process rows |",
        "| --- | --- | --- | --- | --- | --- |",
    ]

    def share(name: str) -> tuple[str, str]:
        if not collected:
            return "—", "—"
        total, ci = by_repo[name], ci_by_repo[name]
        return str(total), f"{ci} ({ci / total:.0%})" if total else "0"

    for repo in repos:
        name = repo.split("/", 1)[1]
        try:
            runs, failed = runs_per_day(api, repo, days)
            load = f"{runs:.0f} | {failed:.1f} | {failed / runs:.1%}" if runs else "0 | 0 | —"
        except ApiError as err:
            load = f"unreadable: {cell(str(err))} | — | —"
        rows_done, ci = share(name)
        out.append(f"| {name} | {load} | {rows_done} | {ci} |")
    if by_repo[SUPPORT]:
        rows_done, ci = share(SUPPORT)
        out.append(f"| {SUPPORT} (plans) | — | — | — | {rows_done} | {ci} |")
    return [*out, ""]


def main_ci(api: Api, repo: str) -> str:
    try:
        sha = api(f"repos/{repo}/commits/main")["sha"]
        runs = api(f"repos/{repo}/actions/runs?head_sha={sha}&per_page=100")["workflow_runs"]
    except ApiError as err:
        return f"unreadable: {err}"
    if not runs:
        return f"no runs on `{sha[:7]}`"
    red = sorted({r["name"] for r in runs if r["conclusion"] in RED})
    running = sum(1 for r in runs if r["status"] != "completed")
    if red:
        return "RED: " + ", ".join(red)
    return f"running ({running})" if running else "green"


def release(api: Api, repo: str) -> tuple[str, str]:
    try:
        tag = api(f"repos/{repo}/releases/latest")["tag_name"]
    except ApiError as err:
        return "none" if "Not Found" in str(err) else f"unreadable: {err}", ""
    try:
        ahead = api(f"repos/{repo}/compare/{tag}...main")["ahead_by"]
    except ApiError as err:
        return tag, f"unreadable: {err}"
    return tag, str(ahead)


def github_sections(api: Api, repos: list[str], now: datetime) -> list[str]:
    summary = [
        "## Repositories",
        "",
        "| Repo | CI on main | Latest release | Commits since | Open PRs |",
        "| --- | --- | --- | --- | --- |",
    ]
    prs = [
        "## Open pull requests",
        "",
        "Merge-queue membership is not in the REST API; a queued PR reads as unarmed here.",
        "",
        "| Repo | PR | Title | Author | Age | Auto-merge |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    stuck: list[str] = []
    for repo in repos:
        name = repo.split("/", 1)[1]
        try:
            pulls = api(f"repos/{repo}/pulls?state=open&per_page=100")
            count = str(len(pulls))
        except ApiError as err:
            pulls, count = [], f"unreadable: {err}"
        tag, ahead = release(api, repo)
        summary.append(f"| {name} | {cell(main_ci(api, repo))} | {cell(tag)} | {cell(ahead)} | {cell(count)} |")
        for pr in pulls:
            armed = "armed" if pr["auto_merge"] else ("draft" if pr["draft"] else "no")
            line = (
                f"| {name} | #{pr['number']} | {cell(pr['title'])} | {pr['user']['login']} "
                f"| {age(pr['created_at'], now)} | {armed} |"
            )
            prs.append(line)
            limit = STUCK_ARMED_HOURS if pr["auto_merge"] else STUCK_UNARMED_HOURS
            if not pr["draft"] and hours_since(pr["created_at"], now) > limit:
                stuck.append(line)
    stuck_section = [
        "## Stuck pull requests",
        "",
        f"Armed and open over {STUCK_ARMED_HOURS} h, or unarmed and open over {STUCK_UNARMED_HOURS // 24} d.",
        "",
    ]
    if stuck:
        stuck_section += [prs[4], prs[5], *stuck]
    else:
        stuck_section.append("None.")
    return [*stuck_section, "", *summary, "", *prs, ""]


def driver_section(state_file: Path | None, now: datetime) -> list[str]:
    out = ["## Driver health", ""]
    if state_file is None:
        return [*out, "Not collected: this run had no watchdog state (host-only).", ""]
    try:
        state = json.loads(state_file.read_text())
    except (OSError, json.JSONDecodeError) as err:
        return [*out, f"Watchdog state unreadable: {err}", ""]
    out += ["| Driver | Last finished | Outcome | Last success | Open alerts |", "| --- | --- | --- | --- | --- |"]
    for name in sorted(state):
        entry = state[name]
        done = entry.get("last_finished") or {}
        ok = entry.get("last_success") or {}

        def when(rec: dict) -> str:
            if "at_us" not in rec:
                return "never"
            at = datetime.fromtimestamp(rec["at_us"] / 1e6, UTC)
            return f"{at:%Y-%m-%d %H:%MZ} ({age(at.isoformat(), now)} ago)"

        outcome = done.get("status", "?")
        if done.get("reason"):
            outcome += f": {done['reason']}"
        alerts = ", ".join(sorted(entry.get("alerts") or {})) or "none"
        out.append(f"| {name} | {when(done)} | {cell(outcome)} | {when(ok)} | {cell(alerts)} |")
    return [*out, ""]


def git(path: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(path), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def repo_slug(url: str) -> str | None:
    m = re.search(r"github\.com[:/](?P<slug>[^/]+/[^/]+?)(?:\.git)?$", url)
    return m.group("slug") if m else None


def merged(api: Api, path: Path, branch: str) -> str:
    if branch in {"main", "(detached)"}:
        return "—"
    try:
        slug = repo_slug(git(path, "remote", "get-url", "origin"))
    except subprocess.CalledProcessError:
        return "no origin"
    if slug is None:
        return "not GitHub"
    owner = slug.split("/")[0]
    try:
        pulls = api(f"repos/{slug}/pulls?state=all&head={owner}:{branch}&per_page=5")
    except ApiError as err:
        return f"unreadable: {err}"
    if not pulls:
        return "no PR"
    pr = pulls[0]
    if pr["merged_at"]:
        return f"merged (#{pr['number']})"
    return f"{pr['state']} (#{pr['number']})"


def worktrees_section(api: Api, roots: list[Path]) -> list[str]:
    out = ["## Working trees", ""]
    if not roots:
        return [*out, "Not collected: this run had no worktree roots (host-only).", ""]
    out += ["| Path | Branch | Dirty files | PR |", "| --- | --- | --- | --- |"]
    for root in roots:
        for path in sorted(p for p in root.iterdir() if (p / ".git").exists()):
            # A worktree whose main repository pruned or lost it still has its
            # .git file; name it so the owner can clean it up, and keep going.
            try:
                branch = git(path, "branch", "--show-current") or "(detached)"
            except subprocess.CalledProcessError:
                out.append(f"| {path} | ? | ? | broken: not a git repository |")
                continue
            dirty = len(git(path, "status", "--porcelain").splitlines())
            out.append(f"| {path} | {cell(branch)} | {dirty} | {cell(merged(api, path, branch))} |")
    return [*out, ""]


def render(args: argparse.Namespace, api: Api, now: datetime) -> str:
    lines = [
        "# Fleet status",
        "",
        f"Generated {now:%Y-%m-%d %H:%M} UTC by `.github/scripts/fleet-status.py`.",
        "",
        *driver_section(args.watchdog_state, now),
        *github_sections(api, args.repo or list(DEFAULT_REPOS), now),
        *plans_section(args.plans),
        *foundation_section(args.plans),
        *ci_load_section(api, args.repo or list(DEFAULT_REPOS), args.plans, now),
        *worktrees_section(api, args.worktrees),
    ]
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--plans", type=Path, required=True, help="msn-plans checkout")
    ap.add_argument("--repo", action="append", help="OWNER/NAME; repeatable (default: the fleet)")
    ap.add_argument("--watchdog-state", type=Path, help="claude-driver watchdog state.json")
    ap.add_argument("--worktrees", type=Path, action="append", default=[], help="dir of checkouts; repeatable")
    ap.add_argument("--output", type=Path, help="write here instead of stdout")
    args = ap.parse_args(argv)
    page = render(args, gh_api, datetime.now(UTC))
    if args.output:
        args.output.write_text(page)
    else:
        sys.stdout.write(page)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
