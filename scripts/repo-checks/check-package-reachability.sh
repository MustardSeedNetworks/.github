#!/bin/bash
# scripts/repo-checks/check-package-reachability.sh (MustardSeedNetworks/.github)
# Fails when a package in this module is reachable from no binary.
#
# staticcheck's unused checks (U1000 and friends) cannot answer this. They find
# unused identifiers *within* a package that is being compiled; a package
# nobody imports still looks fully used from inside its own tests. That gap is
# not theoretical — stem carried 2,800 lines across two packages that no binary
# reached, past a weekly dead-code job that reported success every time.
#
# `go list -deps` over every main package answers it directly, in a second.
#
# Every non-main package counts, not just the ones under internal/. trellis
# keeps most of its library code in core/ and foundation in pkg/, and stem's
# 2,800 unreachable lines were library code too, so an internal/-only gate
# would have missed exactly the case it exists for.
#
# Run from the root of the module being checked. Packages already unreachable
# when this gate was adopted are recorded in the calling repo's
# scripts/package-reachability-baseline.txt with a note. They are debt, not
# permission: the list may shrink and must not grow.

set -euo pipefail

BASELINE_FILE=${BASELINE_FILE:-scripts/package-reachability-baseline.txt}
MODULE=$(go list -m)

GOOSES="linux darwin windows"

# Packages reached from any binary's import graph, on every platform the
# products ship to. A single-platform check would report a package wired only under
# //go:build linux as dead when run on a developer's Mac, which is the fastest
# way to make a gate untrustworthy.
reachable=$(
    for goos in $GOOSES; do
        # Every main package, not just ./cmd/... — niac reaches one of its
        # packages only from ./tools/, and hardcoding ./cmd would report that
        # as dead.
        mains=$(GOOS=$goos go list -f '{{if eq .Name "main"}}{{.ImportPath}}{{end}}' ./... 2>/dev/null)
        [ -z "$mains" ] && continue
        # shellcheck disable=SC2086 # deliberate word splitting of the package list
        GOOS=$goos go list -deps $mains 2>/dev/null
    done | sort -u
)

# Every non-main package in the module, unioned over the same platforms. The
# enumeration has to be as platform-blind as the reachability side above: a
# package whose files are all behind //go:build linux does not load on darwin,
# and listing it on only one GOOS would make the gate's answer depend on the
# machine it ran on.
all_packages=$(
    for goos in $GOOSES; do
        GOOS=$goos go list -f '{{if ne .Name "main"}}{{.ImportPath}}{{end}}' ./... 2>/dev/null
    done | sort -u
)

baselined() {
    local pkg=$1
    # Comment and blank lines are ignored; the package path is the first field.
    awk -v target="$pkg" '
        /^[[:space:]]*(#|$)/ { next }
        $1 == target { found = 1; exit }
        END { exit !found }
    ' "$BASELINE_FILE"
}

new_unreachable=()
still_unreachable=0

while read -r pkg; do
    [ -z "$pkg" ] && continue
    if grep -qxF "$pkg" <<<"$reachable"; then
        continue
    fi
    short=${pkg#"$MODULE/"}
    if baselined "$short"; then
        still_unreachable=$((still_unreachable + 1))
        continue
    fi
    new_unreachable+=("$short")
done <<<"$all_packages"

if [ ${#new_unreachable[@]} -eq 0 ]; then
    echo "✓ no new unreachable packages ($still_unreachable baselined)"
    exit 0
fi

echo "::error::${#new_unreachable[@]} package(s) are reachable from no binary"
echo
for pkg in "${new_unreachable[@]}"; do
    echo "  $pkg"
done
echo
echo "No main package can reach these, so they are not in any shipped"
echo "binary. Either wire them up, delete them, or — if a package is"
echo "deliberately test-only or platform-gated — add it to $BASELINE_FILE"
echo "with a line saying which."
echo
echo "Before deleting: check for consumers Go tooling cannot see. A frontend"
echo "importing a directory inside a Go package is invisible to go build, and"
echo "stem's locales sat inside a dead package for exactly that reason."
exit 1
