#!/usr/bin/env python3
"""Self-tests for the policy repository's own pin gate.

The gate exists because `license-check.yml` ran `go install
github.com/google/go-licenses@latest` in four repos' CI for months and nothing
here could see it (.github#67). A gate that stops firing recreates exactly
that, so each case asserts the rule FIRES on a violating fixture and stays
quiet on the compliant one.

Every case builds a throwaway repo tree, because the checker walks
`.github/workflows/` and `tools/**/Dockerfile` under a root it is given.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CHECKER = Path(__file__).with_name("check-self-pins.py")

GOOD_WORKFLOW = """\
name: Gate
on: [pull_request]
jobs:
  gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - uses: ./.github/actions/apt-install
      - run: go install github.com/rhysd/actionlint/cmd/actionlint@v1.7.12
      - run: pipx install zizmor==1.29.0
      - run: npx --yes --package renovate@42.5.2 -- renovate-config-validator default.json
"""

GOOD_DOCKERFILE = """\
FROM golang:1.27.0-bookworm
ARG GOLANGCI_VERSION=v2.13.2
RUN go install github.com/golangci/golangci-lint/v2/cmd/golangci-lint@${GOLANGCI_VERSION}
"""


class SelfPinGate(unittest.TestCase):
    def run_checker(self, workflow: str = GOOD_WORKFLOW,
                    dockerfile: str = GOOD_DOCKERFILE) -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".github" / "workflows").mkdir(parents=True)
            (root / ".github" / "workflows" / "ci.yml").write_text(workflow)
            (root / "tools" / "lint-linux").mkdir(parents=True)
            (root / "tools" / "lint-linux" / "Dockerfile").write_text(dockerfile)
            proc = subprocess.run([sys.executable, str(CHECKER), str(root)],
                                  capture_output=True, text=True)
            return proc.returncode, proc.stdout + proc.stderr

    def test_a_fully_pinned_repo_passes(self) -> None:
        code, out = self.run_checker()
        self.assertEqual(code, 0, out)

    def test_go_install_latest_is_rejected(self) -> None:
        """The real .github#67 defect, in the workflow four repos call."""
        bad = GOOD_WORKFLOW.replace("actionlint@v1.7.12", "actionlint@latest")
        code, out = self.run_checker(workflow=bad)
        self.assertNotEqual(code, 0, out)
        self.assertIn("pin a version", out)

    def test_unpinned_pipx_install_is_rejected(self) -> None:
        bad = GOOD_WORKFLOW.replace("zizmor==1.29.0", "zizmor")
        code, out = self.run_checker(workflow=bad)
        self.assertNotEqual(code, 0, out)
        self.assertIn("==<version>", out)

    def test_unpinned_npx_package_is_rejected(self) -> None:
        bad = GOOD_WORKFLOW.replace("renovate@42.5.2", "renovate")
        code, out = self.run_checker(workflow=bad)
        self.assertNotEqual(code, 0, out)
        self.assertIn("@<version>", out)

    def test_action_pinned_to_a_tag_is_rejected(self) -> None:
        bad = GOOD_WORKFLOW.replace(
            "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1", "actions/checkout@v7")
        code, out = self.run_checker(workflow=bad)
        self.assertNotEqual(code, 0, out)
        self.assertIn("40-hex commit SHA", out)

    def test_local_action_reference_is_not_a_finding(self) -> None:
        """`uses: ./...` rides this commit; there is nothing to pin."""
        _, out = self.run_checker()
        self.assertNotIn("./.github/actions/apt-install", out)

    def test_floating_base_image_is_rejected(self) -> None:
        bad = GOOD_DOCKERFILE.replace("golang:1.27.0-bookworm", "golang:latest")
        code, out = self.run_checker(dockerfile=bad)
        self.assertNotEqual(code, 0, out)
        self.assertIn("pin a concrete tag", out)

    def test_untagged_base_image_is_rejected(self) -> None:
        bad = GOOD_DOCKERFILE.replace("golang:1.27.0-bookworm", "golang")
        code, out = self.run_checker(dockerfile=bad)
        self.assertNotEqual(code, 0, out)
        self.assertIn("pin a concrete tag", out)

    def test_floating_version_arg_is_rejected(self) -> None:
        bad = GOOD_DOCKERFILE.replace("GOLANGCI_VERSION=v2.13.2", "GOLANGCI_VERSION=latest")
        code, out = self.run_checker(dockerfile=bad)
        self.assertNotEqual(code, 0, out)
        self.assertIn("pin a concrete version", out)

    def test_a_commented_out_violation_is_not_a_finding(self) -> None:
        bad = GOOD_WORKFLOW + "      # - run: go install example.com/tool@latest\n"
        code, out = self.run_checker(workflow=bad)
        self.assertEqual(code, 0, out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
