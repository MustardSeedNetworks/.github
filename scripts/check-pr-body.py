#!/usr/bin/env python3
"""Run a repo's PR title and PR body lint locally, before `gh pr create`.

The rules are not restated here. They are read out of the repo's own
`.github/workflows/pr-hygiene.yml`, the file CI runs, so this check and the
required `Lint PR Title` / `Lint PR Body` contexts cannot drift apart. If the
workflow changes shape so a rule can no longer be found, this exits 2 and names
the missing piece rather than passing on a stale copy.

    python3 check-pr-body.py --title 'fix(api): handle empty body' --body-file body.md
    python3 check-pr-body.py --workflow path/to/pr-hygiene.yml ...

Exit 0 clean, 1 on lint findings, 2 when the workflow cannot be parsed.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_WORKFLOW = ".github/workflows/pr-hygiene.yml"
HEADER = re.compile(r"^(\w*)(?:\((.*)\))?(!)?: (.*)$")


class WorkflowShapeError(Exception):
    """pr-hygiene.yml no longer has a construct this script reads."""


@dataclass(frozen=True)
class Rules:
    types: tuple[str, ...]
    require_scope: bool
    subject_pattern: re.Pattern[str]
    subject_error: str
    headings: tuple[str, ...]
    issue_link: re.Pattern[str]
    issue_link_error: str
    evidence_heading: re.Pattern[str]
    evidence: tuple[re.Pattern[str], ...]
    evidence_error: str


def job_block(text: str, job: str) -> str:
    """Return one top-level job's text: from `  <job>:` to the next job."""
    m = re.search(
        rf"^  {re.escape(job)}:\n(.*?)(?=^  [A-Za-z0-9_-]+:\n|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if not m:
        raise WorkflowShapeError(f"job {job!r} not found")
    return m.group(1)


def scalar(block: str, key: str) -> str:
    m = re.search(rf"^\s+{key}:\s*(.+?)\s*$", block, re.MULTILINE)
    if not m:
        raise WorkflowShapeError(f"`{key}:` not found in the title job")
    return m.group(1)


def literal_list(block: str, key: str) -> tuple[str, ...]:
    m = re.search(rf"^(\s+){key}:\s*\|\s*\n((?:\1\s+\S.*\n?)+)", block, re.MULTILINE)
    if not m:
        raise WorkflowShapeError(f"`{key}: |` list not found in the title job")
    return tuple(line.strip() for line in m.group(2).splitlines() if line.strip())


def js_regex(literal: str, flags: str) -> re.Pattern[str]:
    """Compile a JS regex literal body. The constructs the workflow uses
    (\\s \\d \\S, classes, anchors, alternation) mean the same in Python."""
    return re.compile(
        literal,
        (re.IGNORECASE if "i" in flags else 0) | (re.MULTILINE if "m" in flags else 0),
    )


def regex_literal(script: str, anchor: str) -> tuple[str, str]:
    m = re.search(anchor, script)
    if not m:
        raise WorkflowShapeError(f"no regex matching {anchor!r} in the body script")
    return m.group(1), m.group(2)


def parse_rules(workflow: str) -> Rules:
    title = job_block(workflow, "lint-pr-title")
    body = job_block(workflow, "lint-pr-body")

    heading_list = re.search(r"const requiredHeadings = \[(.*?)\];", body, re.DOTALL)
    if not heading_list:
        raise WorkflowShapeError("`const requiredHeadings = [...]` not found")
    headings = tuple(re.findall(r'"([^"]+)"', heading_list.group(1)))
    if not headings:
        raise WorkflowShapeError("requiredHeadings is empty")

    issue_re, issue_flags = regex_literal(body, r"if \(!/(.+)/(\w*)\.test\(body\)\)")
    issue_msg = re.search(r'\.test\(body\)\)\s*\{\s*errors\.push\("([^"]+)"\)', body)
    ev_heading, ev_heading_flags = regex_literal(
        body, r"body\.split\(/(.+?)/(\w*)\)\[1\]"
    )
    ev_a, ev_a_flags = regex_literal(body, r"if \(!/(.+?)/(\w*)\.test\(testing\) &&")
    ev_b, ev_b_flags = regex_literal(body, r"&& !/(.+?)/(\w*)\.test\(testing\)")
    ev_msg = re.search(r'\.test\(testing\)\) \{\s*errors\.push\("([^"]+)"\)', body)
    if not issue_msg or not ev_msg:
        raise WorkflowShapeError("an errors.push(...) message was not found")

    return Rules(
        types=literal_list(title, "types"),
        require_scope=scalar(title, "requireScope") == "true",
        subject_pattern=re.compile(scalar(title, "subjectPattern")),
        subject_error=scalar(title, "subjectPatternError"),
        headings=headings,
        issue_link=js_regex(issue_re, issue_flags),
        issue_link_error=issue_msg.group(1),
        evidence_heading=js_regex(ev_heading, ev_heading_flags),
        evidence=(js_regex(ev_a, ev_a_flags), js_regex(ev_b, ev_b_flags)),
        evidence_error=ev_msg.group(1),
    )


def lint_title(title: str, rules: Rules) -> list[str]:
    m = HEADER.match(title)
    if not m:
        return [
            f"Title must look like `type(scope): subject` with type one of: {', '.join(rules.types)}."
        ]
    kind, scope, _, subject = m.groups()
    errors: list[str] = []
    if kind not in rules.types:
        errors.append(f"Unknown type {kind!r}; use one of: {', '.join(rules.types)}.")
    if rules.require_scope and not scope:
        errors.append("The title needs a scope.")
    if not rules.subject_pattern.search(subject):
        errors.append(rules.subject_error)
    return errors


def lint_body(body: str, rules: Rules) -> list[str]:
    errors = [
        f"Missing {h}"
        for h in rules.headings
        if not re.search(rf"^{re.escape(h)}\s*$", body, re.MULTILINE)
    ]
    if not rules.issue_link.search(body):
        errors.append(rules.issue_link_error)
    parts = rules.evidence_heading.split(body)
    after = parts[1] if len(parts) > 1 else ""
    testing = re.split(r"^## ", after, flags=re.MULTILINE)[0]
    if not any(p.search(testing) for p in rules.evidence):
        errors.append(rules.evidence_error)
    return errors


def empty_evidence_fences(body: str, rules: Rules) -> bool:
    """True when the evidence section holds only empty fences. The lint accepts
    that (the info string `text` counts as content), so this is a warning."""
    parts = rules.evidence_heading.split(body)
    testing = re.split(r"^## ", parts[1] if len(parts) > 1 else "", flags=re.MULTILINE)[
        0
    ]
    fences = re.findall(r"^```[^\n]*\n(.*?)^```", testing, re.MULTILINE | re.DOTALL)
    return bool(fences) and not any(f.strip() for f in fences)


def find_workflow(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    top = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    return Path(top or ".") / DEFAULT_WORKFLOW


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--title", required=True)
    ap.add_argument("--body-file", required=True, type=Path)
    ap.add_argument(
        "--workflow",
        help=f"pr-hygiene.yml to read the rules from (default: repo's {DEFAULT_WORKFLOW})",
    )
    args = ap.parse_args()

    path = find_workflow(args.workflow)
    try:
        rules = parse_rules(path.read_text(encoding="utf-8"))
    except (OSError, WorkflowShapeError) as exc:
        print(
            f"check-pr-body: cannot read the lint rules from {path}: {exc}",
            file=sys.stderr,
        )
        return 2

    body = args.body_file.read_text(encoding="utf-8")
    errors = lint_title(args.title, rules) + lint_body(body, rules)
    if empty_evidence_fences(body, rules):
        print(
            "WARN: the Testing Evidence block is empty; the lint accepts it, a reviewer will not.",
            file=sys.stderr,
        )
    for e in errors:
        print(f"FAIL: {e}", file=sys.stderr)
    if errors:
        return 1
    print("PR title and body pass the lint.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
