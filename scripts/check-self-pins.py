#!/usr/bin/env python3
"""Apply the fleet's pin policy to the policy repository itself.

This repo tells four product repos to pin everything they install: the
conformance script fails a product `ci.yml` that runs `go install ...@latest`,
and the Renovate preset pins ranges, SHAs and action digests. None of that was
ever pointed back here (.github#67). The reusable `license-check.yml` installed
`go-licenses@latest` — a floating gate running in every product's CI — and
`tools/lint-linux/Dockerfile`, the fleet's only Linux lint pass for cgo files,
sat two patch releases behind the pinned golangci-lint with nothing able to
see it: Renovate had no config in this repo at all.

An unpinned install here is worse than one in a product repo, because these
workflows run in all four. So the same rules apply, checked the same way:

    go install <mod>@<ver>    concrete version, never latest/master/main
    pipx/pip install <pkg>    `==<version>`
    npx --package <pkg>       `@<version>`
    uses: <action>            40-hex commit SHA, not a tag or branch
    FROM <image>:<tag>        concrete tag, never `latest`
    ARG <NAME>_VERSION=       concrete value, never latest/master/main

A finding is a line, printed with its file and line number, so the fix is the
pin rather than an exemption. There is no exemption list: every pin this repo
carries today is one Renovate can bump.

Usage:
    check-self-pins.py [ROOT]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

WORKFLOW_GLOB = ".github/workflows/*.y*ml"
DOCKERFILES = "tools/**/Dockerfile"

FLOATING = {"latest", "master", "main", "HEAD"}

GO_INSTALL = re.compile(r"go install\s+(?P<mod>[^\s@]+)@(?P<ver>[^\s'\";\\]+)")
PIPX_INSTALL = re.compile(r"\b(?:pipx|pip3?) install\s+(?P<spec>[A-Za-z0-9._-]+(?:==\S+)?)")
NPX_PACKAGE = re.compile(r"--package[= ](?P<spec>[^\s'\"]+)")
USES = re.compile(r"^\s*(?:-\s*)?uses:\s*(?P<ref>\S+)")
FROM = re.compile(r"^\s*FROM\s+(?P<image>\S+)", re.IGNORECASE)
ARG_VERSION = re.compile(r"^\s*ARG\s+(?P<name>[A-Z0-9_]*VERSION)=(?P<ver>\S+)", re.IGNORECASE)
SHA = re.compile(r"^[0-9a-f]{40}$")


def check_workflow(path: Path, findings: list[str]) -> None:
    for n, line in enumerate(path.read_text().splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue

        m = GO_INSTALL.search(line)
        if m and m.group("ver") in FLOATING:
            findings.append(f"{path}:{n}: `go install {m.group('mod')}@{m.group('ver')}` — pin a version")

        m = PIPX_INSTALL.search(line)
        if m and "==" not in m.group("spec"):
            findings.append(f"{path}:{n}: `pip install {m.group('spec')}` — pin with `==<version>`")

        m = NPX_PACKAGE.search(line)
        if m and "@" not in m.group("spec").lstrip("@").replace("/", ""):
            findings.append(f"{path}:{n}: `npx --package {m.group('spec')}` — pin with `@<version>`")

        m = USES.match(line)
        if m:
            ref = m.group("ref")
            # A local composite action or reusable workflow rides this commit.
            if not ref.startswith("./"):
                _, _, version = ref.partition("@")
                if not SHA.match(version):
                    findings.append(f"{path}:{n}: `uses: {ref}` — pin to a 40-hex commit SHA")


def check_dockerfile(path: Path, findings: list[str]) -> None:
    for n, line in enumerate(path.read_text().splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue

        m = FROM.match(line)
        if m:
            image = m.group("image")
            _, _, tag = image.rpartition(":")
            if ":" not in image or tag in FLOATING:
                findings.append(f"{path}:{n}: `FROM {image}` — pin a concrete tag")

        m = ARG_VERSION.match(line)
        if m and m.group("ver").lstrip("v") in FLOATING:
            findings.append(f"{path}:{n}: `ARG {m.group('name')}={m.group('ver')}` — pin a concrete version")


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parent.parent
    findings: list[str] = []

    for path in sorted(root.glob(WORKFLOW_GLOB)):
        check_workflow(path, findings)
    for path in sorted(root.glob(DOCKERFILES)):
        check_dockerfile(path, findings)

    if findings:
        print("Unpinned dependencies in the policy repository:")
        for f in findings:
            print(f"  {f}")
        return 1

    print("OK — every install in this repo's workflows and images is pinned")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
