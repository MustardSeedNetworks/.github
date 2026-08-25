#!/usr/bin/env python3
"""Draft the Spanish for keys that have an English value and no Spanish one.

Key parity across en/es is already a blocking check, so a gap never reaches
main — it is caught while the author is still writing the change, and the cost
lands on them as "now hand-write Spanish for this". That is the friction this
removes: the translation memory, the glossary and the ES style guide were a doc
someone had to remember to follow, and this makes them the default.

**It never edits an existing Spanish value.** Filling gaps is a mechanical
operation with a right answer; revising reviewed copy is not, and the two do
not belong in the same tool.

What it can and cannot do, stated plainly:

- An English value that matches the translation memory is translated from it.
- A value made entirely of glossary terms (`RSSI`, `PCAP`, `Mbps`) is copied
  verbatim, which is what the glossary requires.
- Anything else is **reported, not invented**. A novel sentence needs a
  translator; a tool that guessed would produce Spanish nobody checked, which
  is worse than an obvious gap.

Usage:
  python3 scripts/i18n/es-fill.py                # report what is missing
  python3 scripts/i18n/es-fill.py --write        # fill what it can
  python3 scripts/i18n/es-fill.py --check        # exit 1 if fillable gaps exist
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import OrderedDict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("I18N_REPO_ROOT", ".")).resolve()
LOCALES = ROOT / os.environ.get("LOCALES_DIR", "internal/i18n/locales")
GLOSSARY = ROOT / os.environ.get("GLOSSARY_FILE", "scripts/i18n/glossary.txt")
MEMORY = HERE / "translation-memory.tsv"

INTERPOLATION = re.compile(r"\{\{[^}]+\}\}")


def _load_lines(path: Path) -> list[str]:
    if not path.is_file():
        return []
    out = []
    for raw in path.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            out.append(line)
    return out


def load_memory() -> dict[str, str]:
    pairs: dict[str, str] = {}
    for line in _load_lines(MEMORY):
        if "\t" not in line:
            continue
        english, spanish = line.split("\t", 1)
        pairs[english.strip()] = spanish.strip()
    return pairs


def flatten(node: object, prefix: str = "") -> "OrderedDict[str, str]":
    flat: OrderedDict[str, str] = OrderedDict()
    if isinstance(node, dict):
        for key, value in node.items():
            path = f"{prefix}.{key}" if prefix else key
            flat.update(flatten(value, path))
    elif isinstance(node, str):
        flat[prefix] = node
    return flat


def set_path(tree: dict, dotted: str, value: str) -> None:
    parts = dotted.split(".")
    node = tree
    for part in parts[:-1]:
        node = node.setdefault(part, OrderedDict())
    node[parts[-1]] = value


def sort_tree(node):
    if isinstance(node, dict):
        return OrderedDict((k, sort_tree(node[k])) for k in sorted(node))
    return node


def translate(english: str, memory: dict[str, str], glossary: list[str]) -> str | None:
    """Return the Spanish for one English value, or None if it needs a human.

    Interpolation placeholders are preserved exactly; a memory hit whose
    placeholders do not match the source is rejected rather than shipped, since
    a dropped `{{count}}` renders as literal text.
    """
    hit = memory.get(english) or memory.get(english.rstrip(".…:"))
    if hit is not None:
        if set(INTERPOLATION.findall(english)) == set(INTERPOLATION.findall(hit)):
            return hit
        return None

    # A value that is only glossary terms, punctuation and placeholders is the
    # same string in every locale — translating it is what the glossary forbids.
    residue = english
    for term in sorted(glossary, key=len, reverse=True):
        residue = residue.replace(term, " ")
    residue = INTERPOLATION.sub(" ", residue)
    if residue.strip(" ·-–—/,.:()[]%") == "":
        return english
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="fill what can be filled")
    parser.add_argument("--check", action="store_true", help="exit 1 if fillable gaps exist")
    args = parser.parse_args()

    memory = load_memory()
    glossary = _load_lines(GLOSSARY)
    en_dir, es_dir = LOCALES / "en", LOCALES / "es"
    if not en_dir.is_dir():
        sys.stderr.write(f"✘ {en_dir} does not exist (run from the repo root)\n")
        return 2

    filled: list[tuple[str, str, str]] = []
    needs_human: list[tuple[str, str, str]] = []

    for path in sorted(en_dir.glob("*.json")):
        namespace = path.name
        english = flatten(json.loads(path.read_text()))
        es_path = es_dir / namespace
        spanish_tree = (
            json.loads(es_path.read_text(), object_pairs_hook=OrderedDict)
            if es_path.is_file()
            else OrderedDict()
        )
        spanish = flatten(spanish_tree)

        changed = False
        for key, value in english.items():
            if key in spanish:
                continue  # never touch what is already there
            drafted = translate(value, memory, glossary)
            if drafted is None:
                needs_human.append((namespace, key, value))
                continue
            filled.append((namespace, key, drafted))
            if args.write:
                set_path(spanish_tree, key, drafted)
                changed = True

        if changed:
            es_path.write_text(
                json.dumps(sort_tree(spanish_tree), indent=2, ensure_ascii=False) + "\n"
            )

    if filled:
        verb = "Filled" if args.write else "Can fill"
        print(f"{verb} {len(filled)} key(s) from the translation memory and glossary:")
        for namespace, key, value in filled[:30]:
            print(f"  {namespace}: {key} → {value!r}")
        if len(filled) > 30:
            print(f"  … and {len(filled) - 30} more")

    if needs_human:
        print(f"\n{len(needs_human)} key(s) need a translator — no memory or glossary match:")
        for namespace, key, value in needs_human[:30]:
            print(f"  {namespace}: {key} = {value!r}")
        if len(needs_human) > 30:
            print(f"  … and {len(needs_human) - 30} more")

    if not filled and not needs_human:
        print("✓ es has no gaps against en")

    if args.check and filled:
        print("\n::error::run `es-fill.py --write` — these gaps are mechanically fillable")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
