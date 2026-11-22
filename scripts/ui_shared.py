#!/usr/bin/env python3
"""Copy, hash and verify the canonical shared UI files.

`ui/theme/msn-shared.css` and `ui/components/*` in this repo are the one source
of the four product UIs' shared colours and page components. Each UI repo keeps
byte-identical copies, and the fleet gate compares them by sha256: the
mechanism `ui/theme/README.md` describes, extended from one file to the set.

    where it is canonical                where a product keeps its copy
    ui/theme/msn-shared.css          ->  ui/src/theme/msn-shared.css
    ui/components/<name>.ts[x]       ->  ui/src/shared/<name>.ts[x]
                                         (tests included: a product's
                                         coverage ratchet counts them)

`ui/MANIFEST.sha256` lists the sha256 of every file by its product path, in
`sha256sum` format. It is committed so a change to a shared file shows up in
review as a hash change, and CI in this repo fails when it is stale.

    ui_shared.py manifest [--check]      rewrite (or verify) the manifest
    ui_shared.py copy PRODUCT_ROOT       copy canonical files into a product,
                                         and delete files in its shared dir
                                         that are no longer canonical
    ui_shared.py verify PRODUCT_ROOT     fail if a product's copies differ

`ui/src/shared/` is owned wholesale by this mechanism: anything in it that is
not in the manifest is drift. A product that has no `ui/src/shared/` has not
adopted the components yet and is not in scope for `check-ci-conformance.py`,
so landing a new component here never turns a product red before it has copied
the set.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

MANIFEST = Path("ui/MANIFEST.sha256")
THEME_SOURCE = Path("ui/theme/msn-shared.css")
THEME_DEST = Path("src/theme/msn-shared.css")
COMPONENTS_SOURCE = Path("ui/components")
SHARED_DEST = Path("src/shared")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_files(repo_root: Path) -> dict[str, Path]:
    """Product path (relative to the product's ui/) -> canonical file."""
    files = {THEME_DEST.as_posix(): repo_root / THEME_SOURCE}
    for source in sorted((repo_root / COMPONENTS_SOURCE).iterdir()):
        if source.suffix in {".ts", ".tsx"}:
            files[(SHARED_DEST / source.name).as_posix()] = source
    return files


def render_manifest(repo_root: Path) -> str:
    return "".join(
        f"{digest(source)}  {dest}\n" for dest, source in sorted(canonical_files(repo_root).items())
    )


def read_manifest(repo_root: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in (repo_root / MANIFEST).read_text().splitlines():
        want, _, dest = line.partition("  ")
        entries[dest] = want
    return entries


def check_manifest(repo_root: Path) -> list[str]:
    path = repo_root / MANIFEST
    if not path.exists() or path.read_text() != render_manifest(repo_root):
        return [
            f"{MANIFEST} is stale: a shared file changed without the manifest. "
            f"Run `python3 scripts/ui_shared.py manifest` and commit the result."
        ]
    return []


def adopted(product_root: Path) -> bool:
    return (product_root / "ui" / SHARED_DEST).is_dir()


def verify(repo_root: Path, product_root: Path, prefix: str = "") -> list[str]:
    """Findings for a product's copies; empty when every one matches.

    `prefix` limits the check to manifest paths that start with it, so the
    conformance gate can leave the theme to its own older rule.
    """
    ui = product_root / "ui"
    findings: list[str] = []
    manifest = {dest: want for dest, want in read_manifest(repo_root).items() if dest.startswith(prefix)}
    for dest, want in sorted(manifest.items()):
        copy = ui / dest
        if not copy.is_file():
            findings.append(f"ui/{dest} is missing: copy it from the canonical set")
        elif digest(copy) != want:
            findings.append(
                f"ui/{dest} has drifted from the canonical copy "
                f"(found sha256 {digest(copy)[:12]}, expected {want[:12]}); "
                f"change it in MustardSeedNetworks/.github and re-copy, a product-local edit cannot pass"
            )
    shared = ui / SHARED_DEST
    if shared.is_dir() and SHARED_DEST.as_posix().startswith(prefix.rstrip("/")):
        for extra in sorted(shared.rglob("*")):
            rel = extra.relative_to(ui).as_posix()
            if extra.is_file() and rel not in manifest:
                findings.append(f"ui/{rel} is not in the canonical set: delete it, or add the component upstream")
    return findings


def copy(repo_root: Path, product_root: Path) -> None:
    ui = product_root / "ui"
    files = canonical_files(repo_root)
    for dest, source in files.items():
        target = ui / dest
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    shared = ui / SHARED_DEST
    for stale in sorted(shared.rglob("*")) if shared.is_dir() else []:
        if stale.is_file() and stale.relative_to(ui).as_posix() not in files:
            stale.unlink()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    manifest_cmd = sub.add_parser("manifest")
    manifest_cmd.add_argument("--check", action="store_true")
    for name in ("copy", "verify"):
        sub.add_parser(name).add_argument("product_root", type=Path)
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parent.parent
    if args.command == "manifest":
        if args.check:
            findings = check_manifest(repo_root)
        else:
            (repo_root / MANIFEST).write_text(render_manifest(repo_root))
            findings = []
    elif args.command == "copy":
        copy(repo_root, args.product_root)
        findings = verify(repo_root, args.product_root)
    else:
        findings = verify(repo_root, args.product_root) if (args.product_root / "ui").is_dir() else [
            f"{args.product_root} has no ui/ directory"
        ]
    for finding in findings:
        print(f"::error::{finding}" if args.command != "copy" else finding, file=sys.stderr)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
