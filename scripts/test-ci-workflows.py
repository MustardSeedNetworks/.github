#!/usr/bin/env python3
"""The reusable product-CI workflows are the contract product repos pin.

These checks are what a review of the YAML would otherwise have to re-do by
hand: the aggregator does not use always(), a cancelled result still fails the
gate when the job does run, every action is pinned, and the input names the
headers advertise are the ones the files declare.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"

NEW = {
    "ci-changes.yml": {
        "filters",
    },
    "ci-backend.yml": {
        "enabled",
        "go-version-file",
        "node-version-file",
        "npm-version",
        "install-libpcap",
        "setup-node",
        "ui-artifact",
        "ui-artifact-path",
        "ui-dir",
        "ui-install",
        "golangci-lint-version",
        "golangci-lint-args",
        "lint-windows",
        "skip-native-on-pull-request",
        "cgo-enabled-windows",
        "fetch-depth",
        "native-fetch-depth",
        "timeout-minutes",
        "pre-command",
        "build-command",
        "vet-command",
        "windows-vet-command",
        "extra-command",
        "test-command",
        "coverage-command",
        "tidy-command",
        "darwin-build-command",
        "darwin-vet-command",
        "darwin-test-command",
        "windows-build-command",
        "windows-vet-only-command",
        "windows-test-command",
    },
    "ci-race.yml": {
        "enabled",
        "go-version-file",
        "install-libpcap",
        "ui-artifact",
        "ui-artifact-path",
        "pre-command",
        "test-command",
        "skip-network-tests",
        "timeout-minutes",
    },
    "ci-frontend.yml": {
        "enabled",
        "ui-dir",
        "node-version-file",
        "npm-version",
        "install-command",
        "check-lockfile",
        "typecheck-command",
        "lint-command",
        "test-command",
        "extra-command",
        "timeout-minutes",
    },
    "ci-storybook.yml": {
        "enabled",
        "ui-dir",
        "node-version-file",
        "npm-version",
        "install-command",
        "install-deps-command",
        "install-browser-command",
        "test-command",
        "contract-command",
        "timeout-minutes",
    },
    "ci-e2e.yml": {
        "enabled",
        "skip-drafts",
        "backend-result",
        "frontend-result",
        "playwright-image",
        "playwright-container-options",
        "browsers",
        "shards",
        "shard-count",
        "ui-dir",
        "node-version-file",
        "npm-version",
        "ui-artifact",
        "ui-artifact-path",
        "fetch-depth",
        "build-daemon",
        "go-version-file",
        "daemon-runner",
        "static-libpcap",
        "static-libpcap-command",
        "require-static-libpcap",
        "daemon-build-command",
        "daemon-binary",
        "daemon-artifact",
        "prepare-command",
        "test-command",
        "run-smoke",
        "smoke-command",
        "report-path",
        "flake-report",
        "flake-budget",
        "server-log",
        "timeout-minutes",
    },
    "ci-complete.yml": {"results"},
}

SHA = re.compile(r"^[0-9a-f]{40}$")
USES = re.compile(r"^\s*(?:-\s*)?uses:\s*(?P<ref>\S+)")
INPUT_KEY = re.compile(r"^      ([a-z][a-z0-9-]*):\s*$")


def workflow_inputs(text: str) -> set[str]:
    """Keys directly under workflow_call.inputs. Descriptions are nested deeper."""
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line == "    inputs:":
            start = i + 1
            break
    if start is None:
        return set()
    keys = set()
    for line in lines[start:]:
        if line.startswith("    ") and not line.startswith("      "):
            break
        m = INPUT_KEY.match(line)
        if m:
            keys.add(m.group(1))
    return keys


def complete_script() -> str:
    text = (WORKFLOWS / "ci-complete.yml").read_text()
    match = re.search(r"python3 - <<'PY'\n(.*)\n {10}PY\n", text, re.S)
    if not match:
        raise AssertionError("ci-complete.yml has no inline checker")
    return textwrap.dedent(match.group(1))


def run_complete(results: object) -> tuple[int, str]:
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "check.py"
        script.write_text(complete_script())
        proc = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            env={**os.environ, "RESULTS": json.dumps(results)},
            check=False,
        )
    return proc.returncode, proc.stdout + proc.stderr


class ReusableWorkflows(unittest.TestCase):
    def test_each_workflow_is_workflow_call_with_the_declared_inputs(self) -> None:
        for name, want in NEW.items():
            text = (WORKFLOWS / name).read_text()
            self.assertIn("workflow_call:", text, name)
            self.assertIn("\npermissions: {}\n", text, name)
            self.assertEqual(workflow_inputs(text), want, name)

    def test_actions_are_sha_pinned_in_this_repo(self) -> None:
        """A relative uses: ./ in a called workflow resolves in the caller.

        stem#1792 had to copy apt-install and flake-budget for that reason.
        The shared workflows pin the copies that live here.
        """
        shared = re.compile(
            r"^MustardSeedNetworks/\.github/\.github/actions/(?P<action>[a-z0-9-]+)@(?P<sha>[0-9a-f]{40})$"
        )
        needs_apt = {"ci-backend.yml", "ci-race.yml", "ci-storybook.yml", "ci-e2e.yml"}
        for name in NEW:
            actions = set()
            for lineno, line in enumerate((WORKFLOWS / name).read_text().splitlines(), 1):
                if line.lstrip().startswith("#"):
                    continue
                match = USES.match(line)
                if not match:
                    continue
                ref = match.group("ref")
                self.assertFalse(
                    ref.startswith("./"),
                    f"{name}:{lineno}: {ref} resolves in the caller",
                )
                _, _, version = ref.partition("@")
                self.assertTrue(
                    SHA.match(version),
                    f"{name}:{lineno}: {ref} is not a 40-hex pin",
                )
                shared_match = shared.match(ref)
                if shared_match:
                    actions.add(shared_match.group("action"))
            if name in needs_apt:
                self.assertIn("apt-install", actions, name)
            if name == "ci-e2e.yml":
                self.assertIn("flake-budget", actions, name)

    def test_no_job_or_step_uses_always(self) -> None:
        """always() is how a cancelled run posted a red CI Complete."""
        for name in NEW:
            for lineno, line in enumerate((WORKFLOWS / name).read_text().splitlines(), 1):
                code = line.split("#", 1)[0]
                self.assertNotIn(
                    "always()",
                    code,
                    f"{name}:{lineno} uses always()",
                )

    def test_aggregator_condition_is_not_cancelled(self) -> None:
        text = (WORKFLOWS / "ci-complete.yml").read_text()
        self.assertIn("if: ${{ !cancelled() }}", text)
        # The caller example in the header carries the same condition, so a
        # repo that copies it does not skip the aggregator on a failed need.
        self.assertGreaterEqual(text.count("if: ${{ !cancelled() }}"), 2)

    def test_e2e_shards_chromium_and_webkit(self) -> None:
        text = (WORKFLOWS / "ci-e2e.yml").read_text()
        self.assertIn('["chromium", "webkit"]', text)
        self.assertIn("matrix.browser", text)
        self.assertIn("matrix.shard", text)

    def test_backend_covers_darwin_and_windows(self) -> None:
        text = (WORKFLOWS / "ci-backend.yml").read_text()
        self.assertIn("runs-on: macos-latest", text)
        self.assertIn("runs-on: windows-latest", text)
        self.assertIn("GOOS: windows", text)

    def test_changes_reads_the_pinned_script(self) -> None:
        text = (WORKFLOWS / "ci-changes.yml").read_text()
        self.assertIn("job_workflow_sha", text)
        self.assertIn(".ci-changes/scripts/ci-changes.py", text)
        self.assertIn("id-token: write", text)

    def test_aggregator_passes_success_and_skipped_only(self) -> None:
        code, out = run_complete({
            "backend": {"result": "success"},
            "e2e": {"result": "skipped"},
        })
        self.assertEqual(code, 0, out)

    def test_aggregator_fails_on_failure(self) -> None:
        code, out = run_complete({"backend": {"result": "failure"}})
        self.assertNotEqual(code, 0, out)
        self.assertIn("failed or were cancelled", out)

    def test_aggregator_fails_on_a_cancelled_result(self) -> None:
        """If the job runs and a need was cancelled, that is still a red gate."""
        code, out = run_complete({"backend": {"result": "cancelled"}})
        self.assertNotEqual(code, 0, out)
        self.assertIn("cancelled", out)

    def test_aggregator_rejects_an_empty_payload(self) -> None:
        code, out = run_complete({})
        self.assertNotEqual(code, 0, out)

    def test_every_sarif_upload_skips_merge_group_without_swallowing_errors(self) -> None:
        """The queue branch is deleted before upload-sarif runs.

        A missing ref fails the step, which fails CI Complete and drops the
        PR. The scan and the finding gate still run. continue-on-error would
        also hide a broken upload on pull_request, so the step is skipped
        instead, and only on a merge-queue event or ref.
        """
        roots = [WORKFLOWS, ROOT / ".github" / "actions"]
        found: list[str] = []
        for root in roots:
            for path in sorted(root.rglob("*.yml")):
                lines = path.read_text().splitlines()
                for index, line in enumerate(lines):
                    code = line.split("#", 1)[0]
                    if "github/codeql-action/upload-sarif@" not in code:
                        continue
                    rel = path.relative_to(ROOT).as_posix()
                    found.append(f"{rel}:{index + 1}")
                    # Comments may name the defect; only the step's code counts.
                    window = "\n".join(
                        line.split("#", 1)[0]
                        for line in lines[max(0, index - 20): index + 1]
                    )
                    self.assertIn(
                        "github.event_name != 'merge_group'",
                        window,
                        f"{rel}:{index + 1} still uploads on merge_group",
                    )
                    self.assertIn(
                        "refs/heads/gh-readonly-queue/",
                        window,
                        f"{rel}:{index + 1} still uploads a deleted queue ref",
                    )
                    self.assertIn("success()", window, f"{rel}:{index + 1}")
                    self.assertNotIn(
                        "continue-on-error",
                        window,
                        f"{rel}:{index + 1} swallows upload failures",
                    )
        self.assertEqual(found, [".github/workflows/semgrep.yml:73"])

    def test_semgrep_scan_and_finding_gate_still_run_on_merge_group(self) -> None:
        text = (WORKFLOWS / "semgrep.yml").read_text()
        scan, upload_and_gate = text.split("- name: Run Semgrep (all severities, SARIF)", 1)
        upload, gate = upload_and_gate.split("- name: Fail on ERROR-severity findings", 1)
        del scan
        self.assertNotIn("merge_group", upload.split("run:", 1)[0].split("- name: Upload", 1)[0])
        gate_header = gate.split("run:", 1)[0]
        self.assertNotIn("if:", gate_header)
        self.assertNotIn("merge_group", gate_header)
        self.assertIn('if level == "error"', gate)
        self.assertIn("exit 1", gate)


if __name__ == "__main__":
    unittest.main(verbosity=2)
