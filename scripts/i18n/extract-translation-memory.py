#!/usr/bin/env python3
"""Regenerate translation-memory.tsv from the canonical doc.

The doc lives in msn-docs-internal, which is private and not available to a
shared CI action, so the pairs are mirrored here as data — the same
arrangement glossary.txt has with I18N_GLOSSARY.md. The doc stays the source of
truth; this script is how the mirror is refreshed.

Usage:
  python3 scripts/i18n/extract-translation-memory.py \
      ../msn-docs-internal/05-Engineering/I18N_TRANSLATION_MEMORY.md
"""

from __future__ import annotations

import sys
from collections import OrderedDict
from pathlib import Path

HEADER = """# Canonical EN→ES pairs, one per line, tab-separated.
#
# Mirrors msn-docs-internal/05-Engineering/I18N_TRANSLATION_MEMORY.md the way
# glossary.txt mirrors I18N_GLOSSARY.md: the doc is the source of truth, this
# is the machine-readable form the tooling reads, because the docs repo is
# private and not available to a shared CI action.
#
# Regenerate with scripts/i18n/extract-translation-memory.py.
"""


def _uncode(cell: str) -> str:
    cell = cell.strip()
    if cell.startswith("`") and cell.endswith("`"):
        return cell[1:-1].strip()
    return cell


def parse(markdown: str) -> "OrderedDict[str, str]":
    """Pull EN→ES pairs out of the doc's tables.

    Both two- and three-column tables occur, and a left cell may carry more
    than one English form separated by `/` ("Retry / Try again"), which are
    distinct lookups sharing one Spanish form.
    """
    pairs: OrderedDict[str, str] = OrderedDict()
    for line in markdown.split("\n"):
        if not line.startswith("|"):
            continue
        cells = line.strip().strip("|").split("|")
        if len(cells) < 2:
            continue
        left, right = cells[0], cells[1]
        if set(left.strip()) <= set("-: ") or left.strip().upper() == "EN":
            continue
        spanish = _uncode(right)
        if not spanish:
            continue
        for part in left.split("/"):
            english = _uncode(part)
            if english and english.upper() != "EN":
                pairs.setdefault(english, spanish)
    return pairs


def main() -> int:
    if len(sys.argv) != 2:
        sys.stderr.write(f"usage: {sys.argv[0]} <I18N_TRANSLATION_MEMORY.md>\n")
        return 2
    doc = Path(sys.argv[1])
    pairs = parse(doc.read_text())
    out = Path(__file__).resolve().parent / "translation-memory.tsv"
    out.write_text(HEADER + "\n".join(f"{k}\t{v}" for k, v in pairs.items()) + "\n")
    print(f"wrote {len(pairs)} pairs to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
