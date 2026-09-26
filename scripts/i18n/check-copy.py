#!/usr/bin/env python3
"""Ratchet hardcoded English copy down, in the shapes check-source.py cannot see.

check-source.py blocks on hardcoded bare JSX text — everything between a
closing `>` and the next `<`. It has one shape-shaped blind spot, found in seed
(seed#2491, seed#2495): copy that never appears as a text node. All three of
these passed it while rendering English to a Spanish operator:

    <IconButton aria-label="Refresh" />              a prop value
    <ListDetail empty="No alerts match this filter" />
    {loading ? 'Loading…' : rows.length}             a string in an expression

So this gate scans the same tree for the two shapes the text-node scan cannot
reach:

  copy-prop   a value of a prop that carries copy (aria-label, placeholder,
              label, empty, title, …). Single words count: `aria-label="Close"`
              is read out by a screen reader either way.
  literal     a prose string literal (two or more words, capitalised) anywhere
              in a .tsx that is not the argument of a t() call. This is the
              shape a `Record<Status, string>` of labels and a thrown
              `new Error('Failed to load users')` both take.

Unlike check-source.py it is a RATCHET, because no repo was at zero when it was
promoted from seed: each repo lists its existing sites in its own baseline
(COPY_BASELINE, default scripts/i18n/copy-baseline.txt) with a reason, and the
list may only shrink — a new site fails, and an entry that no longer matches
must be removed so the file cannot drift into fiction.

Entries are keyed by file and text, NOT by line number. seed's line-anchored
UI-fetch baseline had to be re-pointed after every split above a baselined
site; copy does not move when the lines around it do.
"""

from __future__ import annotations

import importlib.util
import os
import re
import sys
from pathlib import Path

# The comment blanking and the skip rules are check-source.py's, so the two
# scans agree on what counts as shipped source.
_spec = importlib.util.spec_from_file_location(
    "check_source", Path(__file__).with_name("check-source.py")
)
assert _spec is not None and _spec.loader is not None
check_source = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_source)

# Props whose value is read by a person or a screen reader. A value here is copy
# however short it is.
COPY_PROPS = (
    "alt", "aria-label", "ariaLabel", "aria-description", "body", "caption",
    "cancelLabel", "confirmLabel", "description", "empty", "emptyMessage",
    "error", "eyebrow", "headline", "heading", "helpText", "hint", "label",
    "leftLabel", "legend", "message", "placeholder", "rightLabel", "subtitle",
    "submitLabel", "summary", "text", "title", "tooltip",
)

PROP = re.compile(
    r"\b(" + "|".join(re.escape(p) for p in COPY_PROPS) + r")=(\"|')([^\"'{}<>\n]{2,120})\2"
)
# A capitalised multi-word string: "Failed to load users". The space is
# required and the delimiters are excluded from the separator class on purpose:
# without them "Content-Type" and the tail of `'Connecting...' : 'Connect'` both
# read as prose, and a gate that cries wolf gets a blanket baseline entry.
LITERAL = re.compile(r"(\"|')([A-Z][a-z]+(?:[ ,.!?:;’/-]+[^\"'\n]{1,80})+?)\1")

# A developer-facing log line, not shipped copy.
LOG_CALL = re.compile(r"\b(?:logger|console)\.\w+\(")

# An example value, not copy: an IP, a port, a host, a URL, a lowercase sample.
EXAMPLE = re.compile(r"^(?:[^A-Z]|.*://|[\w.-]+\.[a-z]{2,}$)")
# `t('key')`, `t("key", …)` — the literal that follows is a key, not copy.
T_CALL = re.compile(r"\bt\(\s*$")


def sites(src: Path, root: Path):
    """Yield (key, relative path, kind, text) for each hardcoded-copy site.

    A site repeated in one file yields once per occurrence; main() keys on it.
    """
    for path in sorted(src.rglob("*.tsx")):
        s = str(path)
        if any(part in s for part in check_source.SKIP_PARTS) or s.endswith(
            check_source.SKIP_SUFFIX
        ):
            continue
        text = check_source.blank_comments(path.read_text(encoding="utf-8"))
        rel = path.relative_to(root).as_posix()
        for match in PROP.finditer(text):
            prop, value = match.group(1), match.group(3).strip()
            if not value or EXAMPLE.match(value):
                continue
            yield f"{rel} copy-prop {prop}={value}", rel, "copy-prop", f"{prop}={value!r}"
        for match in LITERAL.finditer(text):
            value = " ".join(match.group(2).split())
            if " " not in value:
                continue
            # A log line is read by whoever runs the daemon, not by the
            # operator using the UI, and it stays English on purpose.
            line_start = text.rfind("\n", 0, match.start()) + 1
            if LOG_CALL.search(text[line_start : match.start()]):
                continue
            # The first argument of t() is a key, and a key looks nothing like
            # this, but `t('Some key', …)` would still be a false positive.
            if T_CALL.search(text[max(0, match.start() - 40) : match.start()]):
                continue
            yield f"{rel} literal {value}", rel, "literal", repr(value)


def load_baseline(path: Path) -> set[str]:
    """Entries are `<file> <kind> <text>`; `#` lines and `  #` tails are reasons."""
    return {
        entry
        for raw in path.read_text(encoding="utf-8").splitlines()
        if (entry := raw.split("  #", 1)[0].strip()) and not entry.startswith("#")
    }


def main() -> int:
    root = Path(os.environ.get("I18N_REPO_ROOT", ".")).resolve()
    src = root / os.environ.get("UI_SRC_DIR", "ui/src")
    baseline_rel = os.environ.get("COPY_BASELINE", "scripts/i18n/copy-baseline.txt")
    baseline_path = root / baseline_rel
    if not baseline_path.is_file():
        print(f"::error::copy baseline {baseline_rel} not found")
        return 1

    found = {key: (rel, kind, shown) for key, rel, kind, shown in sites(src, root)}
    baseline = load_baseline(baseline_path)

    new = sorted(set(found) - baseline)
    gone = sorted(baseline - set(found))

    if new:
        print("::error::hardcoded English copy the JSX-text gate cannot see "
              "— move it into a locale file and read it with t():")
        for key in new:
            rel, kind, shown = found[key]
            print(f"  {kind:9} {rel}: {shown}")
            print(f"::error file={rel}::hardcoded English copy ({kind}): {shown}")
    if gone:
        print(f"::error::baseline entries that no longer match — remove them from {baseline_rel}:")
        for key in gone:
            print(f"  {key}")

    props = sum(1 for _, kind, _ in found.values() if kind == "copy-prop")
    print(
        f"i18n copy gate: {len(found)} hardcoded sites "
        f"({props} copy-prop, {len(found) - props} literal), {len(baseline)} baselined."
    )
    return 1 if new or gone else 0


if __name__ == "__main__":
    sys.exit(main())
