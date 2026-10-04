#!/usr/bin/env python3
"""Assert that a product release published the artifacts it declares.

CI conformance checks how a release is wired, never what it produced, so a
release that silently drops a package, an SBOM or a signature passes every
gate (.github#103, gap 3 of the release-artifact parity review). This reads a
release's asset list and checks it against the product's own declaration,
`.github/release-artifacts.txt`:

    # one primary artifact per line; {version} is the tag without its "v"
    seed-{version}-linux-amd64.tar.gz
    seed_{version}_amd64.deb

A primary artifact is a `.tar.gz`, `.zip`, `.deb` or `.rpm`. For the release
to conform:

1. every declared artifact is published, with its `.sbom.json`, its
   `.cosign.bundle` and the SBOM's own `.cosign.bundle`
2. `checksums.txt`, its `.cosign.bundle` and a `.intoto.jsonl` provenance
   are published
3. nothing else is: an asset that is neither declared nor one of those
   companions fails, so a difference between products (niac's `niac-content`
   packages) is declared rather than silently divergent

Usage:
    check-release-artifacts.py OWNER/REPO [--expect FILE] [--tag TAG]

Without --expect the declaration is read from the repository's default branch;
without --tag the latest release is checked. Both reads go through `gh api`.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

EXPECT_PATH = ".github/release-artifacts.txt"
PRIMARY_SUFFIXES = (".tar.gz", ".zip", ".deb", ".rpm")
COMPANIONS = (".sbom.json", ".cosign.bundle", ".sbom.json.cosign.bundle")
CHECKSUMS = ("checksums.txt", "checksums.txt.cosign.bundle")
PROVENANCE_SUFFIX = ".intoto.jsonl"


def parse_expectation(text: str, version: str) -> tuple[set[str], list[str]]:
    """Return the declared artifacts for `version` and any malformed lines."""
    declared: set[str] = set()
    problems: list[str] = []
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "{version}" not in line:
            problems.append(f"{EXPECT_PATH}:{n}: `{line}` has no {{version}}, so it can only match one release")
        elif not line.endswith(PRIMARY_SUFFIXES):
            problems.append(
                f"{EXPECT_PATH}:{n}: `{line}` is not a primary artifact "
                f"({', '.join(PRIMARY_SUFFIXES)}); its companions are checked without being declared"
            )
        else:
            declared.add(line.replace("{version}", version))
    if not declared and not problems:
        problems.append(f"{EXPECT_PATH} declares no artifacts")
    return declared, problems


def check(expectation: str, tag: str, assets: list[str]) -> list[str]:
    declared, findings = parse_expectation(expectation, tag.removeprefix("v"))
    published = set(assets)

    required = set(CHECKSUMS)
    for artifact in declared:
        required.add(artifact)
        required.update(artifact + suffix for suffix in COMPANIONS)
    findings += [f"{tag}: missing {name}" for name in sorted(required - published)]

    provenance = {name for name in published if name.endswith(PROVENANCE_SUFFIX)}
    if not provenance:
        findings.append(f"{tag}: missing a {PROVENANCE_SUFFIX} provenance")

    undeclared = published - required - provenance
    findings += [f"{tag}: {name} is published but not declared in {EXPECT_PATH}" for name in sorted(undeclared)]
    return findings


def gh_api(path: str, *flags: str) -> str:
    result = subprocess.run(["gh", "api", *flags, path], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        sys.exit(f"gh api {path}: {result.stderr.strip()}")
    return result.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("repo", help="OWNER/REPO")
    parser.add_argument("--expect", type=Path, help=f"declaration to use instead of the repo's {EXPECT_PATH}")
    parser.add_argument("--tag", help="release tag to check instead of the latest release")
    args = parser.parse_args()

    if args.expect:
        expectation = args.expect.read_text()
    else:
        expectation = gh_api(f"repos/{args.repo}/contents/{EXPECT_PATH}", "-H", "Accept: application/vnd.github.raw")

    release_path = f"repos/{args.repo}/releases/" + (f"tags/{args.tag}" if args.tag else "latest")
    release = json.loads(gh_api(release_path))
    tag = release["tag_name"]
    assets = [asset["name"] for asset in release["assets"]]

    findings = check(expectation, tag, assets)
    for finding in findings:
        print(f"{args.repo} {finding}")
    if findings:
        return 1
    print(f"{args.repo} {tag}: {len(assets)} assets match {EXPECT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
