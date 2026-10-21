#!/usr/bin/env bash
# Template for each product repo's scripts/shared-check.sh.
#
# The repo checks live once in MustardSeedNetworks/.github. This shim keeps
# `make test`, validate-touched and the pre-push hooks running them from a repo
# checkout:
#
#   ./scripts/shared-check.sh banned-vocabulary tsconfig-flags
#
# The pin is read from this repo's own ci.yml `uses:` line, so there is exactly
# one pinned SHA per repo and a local run cannot drift from what CI runs.
# Renovate bumps that line; this follows automatically. The cache layout is the
# i18n shim's, so one fetch per SHA serves both.
#
# Offline: once a SHA is cached the shim never reaches the network again.

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

SHARED_REPO="${MSN_SHARED_REPO:-https://github.com/MustardSeedNetworks/.github.git}"
WORKFLOW=".github/workflows/ci.yml"

PIN="$(grep -oE 'MustardSeedNetworks/\.github/\.github/actions/repo-checks@[0-9a-f]{40}' "$WORKFLOW" \
	| head -1 | cut -d@ -f2 || true)"
if [ -z "$PIN" ]; then
	echo "✘ no pinned repo-checks SHA found in $WORKFLOW" >&2
	echo "  CI and this script share that pin; without it they could disagree." >&2
	exit 1
fi

CACHE="${MSN_SHARED_CACHE:-$HOME/.cache/msn-shared}/$PIN"
if [ ! -d "$CACHE/scripts/repo-checks" ]; then
	echo "→ fetching shared repo checks @ ${PIN:0:12} (first run for this pin)" >&2
	rm -rf "$CACHE"
	mkdir -p "$CACHE"
	git -C "$CACHE" init -q
	git -C "$CACHE" remote add origin "$SHARED_REPO"
	git -C "$CACHE" fetch -q --depth 1 origin "$PIN"
	git -C "$CACHE" checkout -q FETCH_HEAD
fi

exec bash "$CACHE/scripts/repo-checks/run.sh" "$@"
