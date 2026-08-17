#!/usr/bin/env python3
"""Assert a repo's CI actually enforces what the fleet requires.

Two real gaps found by hand on 2026-08-16 are exactly what this catches:

  * niac-go's `i18n` job — which validates banned vocabulary — was not in
    `ci-complete`'s `needs:`, so it ran, went red, and blocked nothing.
  * trellis had none of the four governance gates at all, because its CI was
    ported from stem's *workflows* while the checks live in `scripts/`.

Both were invisible: every check was green, and the repo looked healthy.

Checks
------
1. Required governance scripts exist.
2. Every job defined in ci.yml is either in `ci-complete`'s `needs:` or is
   listed as deliberately advisory in `.github/ci-advisory-jobs.txt` with a
   reason. A job that is neither is a gate that cannot fail the build.
3. Every branch-protection required context is a real emitted check name.
   A required context nothing emits wedges every merge.

Exit 0 clean, 1 on any finding.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

# Settings that must be identical fleet-wide. Free-tier GitHub cannot ENFORCE
# these centrally (org rulesets need Team), so this check detects drift instead.
# Every entry here exists because it was found missing in exactly one repo by
# hand — trellis had none of them on 2026-08-16.
REQUIRED_REPO_SETTINGS = {
    "secret_scanning": "enabled",
    "secret_scanning_push_protection": "enabled",
}

REQUIRED_FILES = [
    (".github/CODEOWNERS", "a CI/release change can weaken a gate without touching product code"),
]

REQUIRED_SCRIPTS = [
    ("scripts/check-banned-vocabulary.py", "banned-vocabulary is a no-exceptions rule"),
    ("scripts/check-file-size.sh", "file-size ratchet"),
]

# ci-complete is the aggregator itself; `changes` is a path-filter fan-out that
# every other job already depends on.
NOT_GATES = {"ci-complete", "changes"}


def fail(msg: str) -> None:
    print(f"::error::{msg}")


def job_names(ci: str) -> list[str]:
    """Job keys under `jobs:` only — `on:` also has two-space keys (push, etc)."""
    m = re.search(r"^jobs:\n(.*)", ci, re.S | re.M)
    if not m:
        return []
    return re.findall(r"^  ([a-z][a-z0-9-]*):\s*$", m.group(1), re.M)


def ci_complete_needs(ci: str) -> list[str] | None:
    m = re.search(r"^  ci-complete:\n(.*?)^    (?:if|steps):", ci, re.S | re.M)
    if not m:
        return None
    block = re.search(r"^    needs:\n((?:      - \S+\n)+)", m.group(1), re.M)
    if not block:
        return None
    return re.findall(r"^      - (\S+)$", block.group(1), re.M)


def advisory_jobs(root: Path) -> dict[str, str]:
    """Deliberately-advisory jobs, each with a stated reason."""
    p = root / ".github/ci-advisory-jobs.txt"
    out: dict[str, str] = {}
    if not p.exists():
        return out
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, _, reason = line.partition("|")
        out[name.strip()] = reason.strip()
    return out


def emitted_checks(repo: str) -> set[str]:
    """Check names actually reported, unioned across main and a recent PR.

    Branch protection gates pull requests, and PR-only checks (pr-body-lint,
    title-lint) never report on main — so main alone is the wrong ground truth
    and produces false "wedged" alarms.
    """
    shas = []
    try:
        shas.append(subprocess.run(
            ["gh", "api", f"repos/{repo}/commits/main", "--jq", ".sha"],
            capture_output=True, text=True, timeout=60, check=True).stdout.strip())
    except Exception:
        pass
    try:
        raw = subprocess.run(
            ["gh", "pr", "list", "-R", repo, "--state", "all", "--limit", "10",
             "--json", "headRefOid", "--jq", ".[].headRefOid"],
            capture_output=True, text=True, timeout=60, check=True).stdout
        shas.extend(x for x in raw.split() if x)
    except Exception:
        pass

    names: set[str] = set()
    for sha in shas:
        try:
            raw = subprocess.run(
                ["gh", "api", f"repos/{repo}/commits/{sha}/check-runs",
                 "--jq", "[.check_runs[].name]", "--paginate"],
                capture_output=True, text=True, timeout=120, check=True).stdout
            for line in raw.strip().splitlines():
                names.update(json.loads(line))
        except Exception:
            continue
    return names


def required_contexts(repo: str) -> list[str]:
    try:
        raw = subprocess.run(
            ["gh", "api", f"repos/{repo}/branches/main/protection", "--jq",
             ".required_status_checks.contexts"],
            capture_output=True, text=True, timeout=60, check=True,
        ).stdout.strip()
        return json.loads(raw) if raw else []
    except Exception:
        return []


class LinterFloorUnavailable(Exception):
    """The floor could not be consulted, so it was not verified.

    Distinct from "the floor is met", for the same reason repo_settings keeps
    None and {} apart: as a blocking gate, a missing or unparseable
    golangci-lint would otherwise report a clean pass while checking nothing.
    A gate that silently stops gating is the failure this script exists to catch.
    """


def linter_floor(root: Path, policy_dir: Path) -> list[str]:
    """Enabled linters missing against this repo's declared tier.

    Trellis ran 5 linters with no gosec — no Go security linting at all on a
    customer-facing product — and nothing caught it. A repo may ADD linters;
    dropping below its tier is a finding.

    Raises LinterFloorUnavailable if golangci-lint cannot be consulted.
    """
    tier_file = root / ".github/golangci-tier.txt"
    tier = tier_file.read_text().strip() if tier_file.exists() else "full"
    want = policy_dir / f"golangci-linters-{tier}.txt"
    if not want.exists():
        return []
    try:
        out = subprocess.run(["golangci-lint", "linters"], cwd=root,
                             capture_output=True, text=True, timeout=180).stdout
    except Exception as exc:
        raise LinterFloorUnavailable(f"could not run golangci-lint: {exc}") from exc
    enabled, seen = set(), False
    for line in out.splitlines():
        if line.startswith("Enabled by your configuration"): seen = True; continue
        if line.startswith("Disabled by"): break
        if seen:
            m = re.match(r"^([a-z0-9]+)", line)
            if m: enabled.add(m.group(1))
    if not enabled:
        raise LinterFloorUnavailable(
            "golangci-lint reported no enabled linters — its output format may "
            "have changed"
        )
    required = {l.strip() for l in want.read_text().split() if l.strip()}
    return sorted(required - enabled)


def repo_settings(repo: str) -> dict | None:
    """Security settings, or None if the lookup itself failed.

    None and {} must stay distinct. Swallowing a failed API call into an empty
    dict reports "secret_scanning=unset" — a policy violation — when the truth
    is that the check never ran. This bit for real: invoking the script with a
    path instead of a repo slug produced `gh api repos/.`, a 404, and two
    fabricated findings against a repo whose settings were correct. Once this
    is a blocking gate, a token blip would red-line the whole fleet the same way.
    """
    try:
        raw = subprocess.run(
            ["gh", "api", f"repos/{repo}", "--jq", ".security_and_analysis"],
            capture_output=True, text=True, timeout=60, check=True).stdout.strip()
        return json.loads(raw) if raw else {}
    except Exception:
        return None


def unpinned_tools(root: Path) -> list[str]:
    """`go install <mod>@latest` in CI or Makefiles.

    An unpinned gate can change behaviour with no code change — either a
    spurious break or a silent loss of coverage. trellis shipped govulncheck
    (a hard gate) on @latest until 2026-08-16.
    """
    hits = []
    globs = [".github/workflows/*.yml", "Makefile", "mk/*.mk"]
    for pat in globs:
        for f in root.glob(pat):
            for i, line in enumerate(f.read_text(errors="ignore").splitlines(), 1):
                # Comments are prose, not gates. A comment explaining why a
                # `go install ...@latest` was replaced used to trip this check,
                # so documenting the fix re-created the finding it described.
                if line.lstrip().startswith("#"):
                    continue
                if re.search(r"go install\s+\S+@latest", line):
                    hits.append(f"{f.relative_to(root)}:{i}")
    return hits


def main() -> int:
    root = Path.cwd()
    repo = sys.argv[1] if len(sys.argv) > 1 else ""
    findings = 0

    for rel, why in REQUIRED_FILES:
        if not (root / rel).exists():
            fail(f"missing {rel} ({why})")
            findings += 1

    policy = Path(__file__).resolve().parent.parent / "policy"
    if policy.exists():
        try:
            for missing in linter_floor(root, policy):
                fail(f"linter '{missing}' is in this repo's declared tier but not enabled")
                findings += 1
        except LinterFloorUnavailable as exc:
            fail(f"linter floor not verified: {exc}")
            findings += 1

    for site in unpinned_tools(root):
        fail(f"{site}: `go install ...@latest` — pin it; an unpinned gate can "
             f"change behaviour with no code change")
        findings += 1

    if repo:
        sa = repo_settings(repo)
        if sa is None:
            fail(f"could not read security settings for '{repo}' — is it an "
                 f"owner/name slug? This script takes a slug, not a path.")
            findings += 1
        else:
            for key, want in REQUIRED_REPO_SETTINGS.items():
                got = (sa.get(key) or {}).get("status")
                if got != want:
                    fail(f"repo setting {key}={got or 'unset'}, fleet requires {want}")
                    findings += 1

    for rel, why in REQUIRED_SCRIPTS:
        if not (root / rel).exists():
            fail(f"missing required governance script {rel} ({why})")
            findings += 1

    ci_path = root / ".github/workflows/ci.yml"
    if not ci_path.exists():
        fail("no .github/workflows/ci.yml")
        return 1
    ci = ci_path.read_text()

    needs = ci_complete_needs(ci)
    if needs is None:
        # A repo may gate on individual checks instead of an aggregator. That is
        # a valid design — but then branch protection must list them, so verify
        # that instead of demanding an aggregator that was never intended.
        contexts = required_contexts(repo) if repo else []
        if not contexts:
            fail(
                "no ci-complete aggregator AND no branch-protection required "
                "contexts — nothing gates a merge"
            )
            return 1
        print(
            f"  no ci-complete aggregator; gating on {len(contexts)} explicit "
            "required contexts instead"
        )
        needs = []
        for ctx in contexts:
            needs.append(ctx.split(" / ")[0].strip())
        # Match protection's display names back to job keys.
        names = dict(re.findall(r"^  ([a-z][a-z0-9-]*):\n(?:    .*\n)*?    name: (.+)$", ci, re.M))
        resolved = {k for k, v in names.items() if v.strip().strip("'\"") in contexts}
        needs.extend(resolved)

    advisory = advisory_jobs(root)
    for job in job_names(ci):
        if job in NOT_GATES or job in needs:
            continue
        if job in advisory:
            print(f"  advisory (documented): {job} — {advisory[job]}")
            continue
        fail(
            f"job '{job}' is not in ci-complete's needs and is not listed in "
            f".github/ci-advisory-jobs.txt — it runs but cannot block a merge"
        )
        findings += 1

    if repo:
        # Protection lists DISPLAY names, so compare against each job's `name:`
        # (falling back to the key), plus names from every other workflow file.
        # Ground truth: what main's latest commit actually reported. Parsing
        # workflow files misses GitHub-generated checks (the CodeQL aggregate)
        # and reusable-workflow names, producing false wedge warnings.
        emitted = emitted_checks(repo)
        for ctx in required_contexts(repo):
            caller = ctx.split(" / ")[0].strip()
            if caller in emitted:
                continue
            if not emitted:
                print(f"  note: could not read emitted checks; skipped verifying '{ctx}'")
                continue
            # Sampling is best-effort: a context may simply not have run in the
            # sampled commits. Only fail when nothing in any workflow could emit
            # it either — otherwise report it for a human to confirm.
            in_files = any(
                ctx.split(" / ")[0].strip() in wf.read_text()
                for wf in (root / ".github/workflows").glob("*.yml")
            )
            if in_files:
                print(
                    f"  note: required context '{ctx}' not seen in the sampled runs, "
                    "but a workflow references it — confirm it still reports."
                )
                continue
            fail(
                f"required context '{ctx}' was not reported by any sampled run and "
                "no workflow references it — every merge would be wedged"
            )
            findings += 1

    if findings:
        print(f"\nci-conformance: {findings} finding(s)")
        return 1
    print("ci-conformance: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
