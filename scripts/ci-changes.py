#!/usr/bin/env python3
"""Classify changed paths against a paths-filter map.

The product repos each copy a `changes` job. ci-changes.yml runs this script
from the commit the caller pinned, so the classification and the workflow move
together.

Filter text is the subset of dorny/paths-filter YAML the fleet writes:

    backend:
      - '**/*.go'
      - 'go.mod'
      # comments and blank lines are ignored

`**` crosses directories, `*` does not, a leading `!` excludes. A filter is
true when any changed path matches one of its positive globs and none of its
exclusions. On `merge_group` every declared filter is true: the queue has no
PR base to diff, and it exists to test the merged result.

Reads FILTERS and EVENT_NAME from the environment (never from argv — a filter
blob is data). Changed paths come from stdin, one per line. Prints a JSON
object of filter name to "true"/"false". When GITHUB_OUTPUT is set, also
writes `filters` and the fleet's known output names.
"""

from __future__ import annotations

import json
import os
import re
import sys

# Declared as workflow outputs so callers can write
# `needs.changes.outputs.backend` the way their ci.yml already does. Any other
# key is only in the JSON output.
KNOWN_OUTPUTS = (
    "backend",
    "frontend",
    "docs",
    "ci_infra",
    "darwin_bridge",
    "c",
    "schema",
    "https",
    "hooks",
    "docker",
)

_KEY = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):\s*$")
_ITEM = re.compile(r"^\s+-\s+(.+?)\s*$")


def parse_filters(text: str) -> dict[str, list[str]]:
    """The filter YAML the fleet writes. Anything else is a hard error."""
    filters: dict[str, list[str]] = {}
    current: str | None = None
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.split(" #", 1)[0].rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key = _KEY.match(line)
        if key and not line.startswith((" ", "\t")):
            current = key.group(1)
            filters[current] = []
            continue
        item = _ITEM.match(line)
        if item and current is not None:
            value = item.group(1).strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                value = value[1:-1]
            if not value:
                raise SystemExit(f"filters:{lineno}: empty pattern")
            filters[current].append(value)
            continue
        raise SystemExit(f"filters:{lineno}: unsupported line: {raw!r}")
    if not filters:
        raise SystemExit("filters: no filters declared")
    empty = [name for name, patterns in filters.items() if not patterns]
    if empty:
        raise SystemExit(f"filters: {', '.join(empty)} has no patterns")
    return filters


def _glob_to_re(pattern: str) -> re.Pattern[str]:
    """Convert one filter glob to a full-path regular expression.

    `**/` matches zero or more directories, including none, so `**/*.go`
    matches a `.go` file at the repository root. `*` and `?` stay inside one
    path segment.
    """
    out = ["^"]
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    out.append("$")
    return re.compile("".join(out))


def _matches(path: str, pattern: str) -> bool:
    negated = pattern.startswith("!")
    body = pattern[1:] if negated else pattern
    return _glob_to_re(body).search(path) is not None


def file_matches(path: str, patterns: list[str]) -> bool:
    positive = [p for p in patterns if not p.startswith("!")]
    negative = [p for p in patterns if p.startswith("!")]
    if not any(_matches(path, p) for p in positive):
        return False
    if any(_matches(path, p) for p in negative):
        return False
    return True


def classify(filters: dict[str, list[str]], files: list[str], event: str) -> dict[str, str]:
    if event == "merge_group":
        return {name: "true" for name in filters}
    return {
        name: "true" if any(file_matches(path, patterns) for path in files) else "false"
        for name, patterns in filters.items()
    }


def write_github_output(result: dict[str, str]) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as fh:
        blob = json.dumps(result, sort_keys=True)
        fh.write(f"filters<<EOF\n{blob}\nEOF\n")
        for name in KNOWN_OUTPUTS:
            fh.write(f"{name}={result.get(name, '')}\n")


def main() -> int:
    filters = parse_filters(os.environ.get("FILTERS", ""))
    event = os.environ.get("EVENT_NAME", "")
    files = [line.strip() for line in sys.stdin.read().splitlines() if line.strip()]
    result = classify(filters, files, event)
    write_github_output(result)
    json.dump(result, sys.stdout, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
