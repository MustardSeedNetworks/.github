#!/usr/bin/env python3
"""Structural checks for the fleet Renovate preset.

The soak gate resolves presets and asserts the npm age. These assert the
scheduling and grouping knobs that gate does not look at, so a revert of
`rebaseWhen` or the off-hours window fails here instead of on the next
weekday morning.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

OFF_HOURS = ["* 0-7 * * 1-5", "* 18-23 * * 1-5", "* * * * 0,6"]


class RenovatePolicy(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads((ROOT / "default.json").read_text())
        cls.preset = json.loads((ROOT / "presets" / "post-upgrade-generate.json").read_text())

    def test_rebase_only_when_conflicted(self) -> None:
        self.assertEqual(self.config["rebaseWhen"], "conflicted")

    def test_normal_updates_and_lockfile_maintenance_are_off_hours(self) -> None:
        self.assertEqual(self.config["timezone"], "America/New_York")
        self.assertEqual(self.config["schedule"], OFF_HOURS)
        self.assertEqual(self.config["lockFileMaintenance"]["schedule"], OFF_HOURS)
        self.assertNotIn("at any time", self.config["schedule"])
        self.assertNotIn("at any time", self.config["lockFileMaintenance"]["schedule"])

    def test_vulnerability_updates_are_not_on_the_off_hours_schedule(self) -> None:
        self.assertEqual(self.config["vulnerabilityAlerts"]["schedule"], ["at any time"])

    def test_shared_workflow_pins_are_one_group(self) -> None:
        rules = [
            rule for rule in self.config["packageRules"]
            if rule.get("groupSlug") == "shared-workflows"
        ]
        self.assertEqual(len(rules), 1, rules)
        rule = rules[0]
        self.assertEqual(rule["groupName"], "shared workflows")
        self.assertEqual(rule["matchManagers"], ["github-actions"])
        self.assertIn("MustardSeedNetworks/.github/**", rule["matchPackageNames"])
        # Later than the general "github actions" group, so this name wins.
        names = [r.get("groupName") for r in self.config["packageRules"]]
        self.assertLess(names.index("github actions"), names.index("shared workflows"))

    def test_generate_preset_runs_make_on_buf_and_connect(self) -> None:
        rule = self.preset["packageRules"][0]
        tasks = rule["postUpgradeTasks"]
        self.assertEqual(tasks["commands"], ["make generate generate-ts"])
        self.assertEqual(tasks["executionMode"], "branch")
        names = set(rule["matchPackageNames"])
        self.assertIn("github.com/bufbuild/buf/**", names)
        self.assertIn("connectrpc.com/connect/**", names)
        self.assertIn("@connectrpc/**", names)
        self.assertIn("@bufbuild/**", names)
        # allowedPostUpgradeCommands is admin-only. Putting it here is ignored
        # and reads as though the app will run the command.
        self.assertNotIn("allowedPostUpgradeCommands", self.preset)
        self.assertNotIn("allowedPostUpgradeCommands", self.config)


if __name__ == "__main__":
    unittest.main(verbosity=2)
