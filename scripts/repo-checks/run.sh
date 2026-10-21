#!/usr/bin/env bash
# Run the named shared repo checks against the current directory.
#
# One entry point for both callers: the repo-checks composite action in CI, and
# each product's scripts/shared-check.sh shim locally, so a check name means the
# same script in both places. Every named check runs even after one fails, so a
# single CI run reports all of them.

set -euo pipefail

if [ "$#" -eq 0 ]; then
	echo "usage: run.sh <check>..." >&2
	exit 2
fi

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
failed=()

for check in "$@"; do
	case "$check" in
		banned-vocabulary | component-variants | tsconfig-flags)
			command=(python3 "$HERE/check-$check.py") ;;
		package-reachability | stale-tests)
			command=(bash "$HERE/check-$check.sh") ;;
		*)
			echo "::error::unknown repo check: $check" >&2
			exit 2 ;;
	esac
	echo "── $check"
	"${command[@]}" || failed+=("$check")
done

if [ "${#failed[@]}" -gt 0 ]; then
	echo "::error::repo checks failed: ${failed[*]}"
	exit 1
fi
