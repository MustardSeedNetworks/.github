import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import {
	mkdirSync,
	mkdtempSync,
	readFileSync,
	rmSync,
	writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

// Execute the reusable workflow's real gate, not a parallel implementation.
const workflow = readFileSync(
	new URL("../.github/workflows/license-check.yml", import.meta.url),
	"utf8",
);
const block = workflow.match(
	/ {6}- name: Check npm dependencies for license compliance\n[\s\S]*? {8}run: \|\n([\s\S]*?)(?=\n {6}- name:)/u,
);
assert(block?.[1], "npm license check step must exist");
const command = block[1].replace(/^ {10}/gmu, "");
const name = "@mustardseednetworks/auth-ui";

interface Fixture {
	name?: string;
	lockName?: string;
	license: string;
	private?: boolean;
	dependencyName?: string;
}

function runFixture(fixture: Fixture) {
	const directory = mkdtempSync(join(tmpdir(), "npm-license-self-"));
	const dependencyName = fixture.dependencyName ?? "external-dependency";
	const manifest = {
		name: fixture.name,
		version: "0.1.0",
		license: "BUSL-1.1",
		private: fixture.private ?? false,
		dependencies: { [dependencyName]: "1.0.0" },
	};
	try {
		writeFileSync(join(directory, "package.json"), JSON.stringify(manifest));
		writeFileSync(
			join(directory, "package-lock.json"),
			JSON.stringify({
				lockfileVersion: 3,
				packages: {
					"": { ...manifest, name: fixture.lockName ?? fixture.name },
				},
			}),
		);
		const dependency = join(directory, "node_modules", dependencyName);
		mkdirSync(dependency, { recursive: true });
		writeFileSync(
			join(dependency, "package.json"),
			JSON.stringify({
				name: dependencyName,
				version: "1.0.0",
				license: fixture.license,
			}),
		);
		return spawnSync("bash", ["-euo", "pipefail", "-c", command], {
			cwd: directory,
			encoding: "utf8",
			timeout: 120_000,
		});
	} finally {
		rmSync(directory, { recursive: true, force: true });
	}
}

test("public BUSL project with an MIT dependency passes", () => {
	const result = runFixture({ name, license: "MIT" });
	assert.equal(result.status, 0, result.stdout + result.stderr);
	assert.match(result.stdout, /MIT/u);
});

test("private project behavior stays unchanged", () => {
	const result = runFixture({ name, license: "MIT", private: true });
	assert.equal(result.status, 0, result.stdout + result.stderr);
});

for (const license of ["GPL-3.0", "BUSL-1.1"]) {
	test(`public third-party ${license} dependency fails`, () => {
		const result = runFixture({ name, license });
		assert.equal(result.status, 1, result.stdout + result.stderr);
		assert.match(result.stderr, /external-dependency@1\.0\.0/u);
	});
}

test("same package name at a different dependency version is not excluded", () => {
	const result = runFixture({
		name,
		license: "BUSL-1.1",
		dependencyName: name,
	});
	assert.equal(result.status, 1, result.stdout + result.stderr);
	assert.match(result.stderr, /auth-ui@1\.0\.0/u);
});

for (const fixture of [
	{ name, lockName: "different-project", license: "MIT" },
	{ license: "MIT" },
	{ name: `${name};external-dependency`, license: "MIT" },
]) {
	test(`invalid root identity fails closed: ${fixture.name ?? "missing"}`, () => {
		const result = runFixture(fixture);
		assert.notEqual(result.status, 0, result.stdout + result.stderr);
		assert.match(result.stderr, /Invalid npm project identity/u);
	});
}
