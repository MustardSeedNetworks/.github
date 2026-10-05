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
from datetime import UTC, datetime
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


def parse_plan(path: Path) -> list[Row]:
    rows: list[Row] = []
    section = ""
    in_index = False
    for line in path.read_text().splitlines():
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
            rows.append(Row(path.name, section, parts[0], parts[1]))
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
            branch = git(path, "branch", "--show-current") or "(detached)"
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
