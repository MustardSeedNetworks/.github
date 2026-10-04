#!/usr/bin/env python3
"""Self-tests for the release-conformance check (.github#103).

Each rule is asserted to FIRE on a release missing what it guards, and the
check stays quiet on a release that publishes exactly what it declares. The
asset names mirror a real goreleaser release (seed v0.222.0).
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "check_release_artifacts", Path(__file__).with_name("check-release-artifacts.py")
)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)

DECLARATION = """\
# seed's primary artifacts
seed-{version}-linux-amd64.tar.gz
seed-{version}-windows-amd64.zip
seed_{version}_amd64.deb
seed-{version}-1.x86_64.rpm
"""

ARTIFACTS = [
    "seed-0.222.0-linux-amd64.tar.gz",
    "seed-0.222.0-windows-amd64.zip",
    "seed_0.222.0_amd64.deb",
    "seed-0.222.0-1.x86_64.rpm",
]


def release_assets() -> list[str]:
    assets = ["checksums.txt", "checksums.txt.cosign.bundle", "seed-slsa-provenance.intoto.jsonl"]
    for artifact in ARTIFACTS:
        assets += [
            artifact,
            artifact + ".cosign.bundle",
            artifact + ".sbom.json",
            artifact + ".sbom.json.cosign.bundle",
        ]
    return assets


def without(name: str) -> list[str]:
    assets = release_assets()
    assets.remove(name)
    return assets


class ReleaseConformance(unittest.TestCase):
    def test_a_release_that_publishes_its_declaration_passes(self) -> None:
        self.assertEqual(checker.check(DECLARATION, "v0.222.0", release_assets()), [])

    def test_a_missing_artifact_fails(self) -> None:
        findings = checker.check(DECLARATION, "v0.222.0", without("seed_0.222.0_amd64.deb"))
        self.assertEqual(findings, ["v0.222.0: missing seed_0.222.0_amd64.deb"])

    def test_each_missing_companion_fails(self) -> None:
        for suffix in (".sbom.json", ".cosign.bundle", ".sbom.json.cosign.bundle"):
            with self.subTest(suffix=suffix):
                name = "seed-0.222.0-1.x86_64.rpm" + suffix
                self.assertEqual(
                    checker.check(DECLARATION, "v0.222.0", without(name)), [f"v0.222.0: missing {name}"]
                )

    def test_missing_checksums_or_their_signature_fails(self) -> None:
        for name in ("checksums.txt", "checksums.txt.cosign.bundle"):
            with self.subTest(name=name):
                self.assertEqual(
                    checker.check(DECLARATION, "v0.222.0", without(name)), [f"v0.222.0: missing {name}"]
                )

    def test_missing_provenance_fails(self) -> None:
        findings = checker.check(DECLARATION, "v0.222.0", without("seed-slsa-provenance.intoto.jsonl"))
        self.assertEqual(findings, ["v0.222.0: missing a .intoto.jsonl provenance"])

    def test_an_undeclared_artifact_fails_with_its_companions(self) -> None:
        """Removing one line from the declaration is the acceptance's RED case."""
        declaration = DECLARATION.replace("seed_{version}_amd64.deb\n", "")
        findings = checker.check(declaration, "v0.222.0", release_assets())
        self.assertEqual(len(findings), 4)
        self.assertTrue(all("seed_0.222.0_amd64.deb" in f and "not declared" in f for f in findings))

    def test_an_unknown_extra_asset_fails(self) -> None:
        findings = checker.check(DECLARATION, "v0.222.0", [*release_assets(), "install.sh"])
        self.assertEqual(findings, ["v0.222.0: install.sh is published but not declared in .github/release-artifacts.txt"])

    def test_a_declared_artifact_from_another_version_does_not_match(self) -> None:
        findings = checker.check(DECLARATION, "v0.223.0", release_assets())
        self.assertIn("v0.223.0: missing seed_0.223.0_amd64.deb", findings)

    def test_a_line_without_a_version_placeholder_is_rejected(self) -> None:
        declaration = DECLARATION + "seed-0.222.0-linux-arm64.tar.gz\n"
        findings = checker.check(declaration, "v0.222.0", release_assets())
        self.assertEqual(len(findings), 1)
        self.assertIn("has no {version}", findings[0])

    def test_a_companion_cannot_be_declared_as_an_artifact(self) -> None:
        declaration = DECLARATION + "seed-{version}-linux-amd64.tar.gz.sbom.json\n"
        findings = checker.check(declaration, "v0.222.0", release_assets())
        self.assertEqual(len(findings), 1)
        self.assertIn("is not a primary artifact", findings[0])

    def test_an_empty_declaration_is_rejected(self) -> None:
        findings = checker.check("# nothing yet\n", "v0.222.0", release_assets())
        self.assertIn(".github/release-artifacts.txt declares no artifacts", findings)


if __name__ == "__main__":
    unittest.main(verbosity=2)
