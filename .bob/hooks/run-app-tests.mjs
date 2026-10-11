#!/usr/bin/env node
/**
 * OnRamp post-tool-use hook: run the app-level test suite whenever a
 * Python file under hc/ is written or patched.
 *
 * Input (stdin): PostToolUse JSON payload from Bob.
 * Output: stdout text is added to Bob's context as a tool annotation.
 * Exit 0 always — this hook reports but never blocks.
 */

import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { resolve, join } from "node:path";

let raw = "";
for await (const chunk of process.stdin) raw += chunk;

const input = JSON.parse(raw);
const cwd = input.cwd ?? process.cwd();

// Only react to file-write tools
const WRITE_TOOLS = new Set([
  "write_file",
  "apply_diff",
  "search_and_replace",
  "insert_content",
]);
if (!WRITE_TOOLS.has(input.tool_name)) process.exit(0);

// Resolve the edited file path (tool_input.path is repo-relative)
const editedPath = String(input.tool_input?.path ?? "");
if (!editedPath.endsWith(".py")) process.exit(0);

// Only fire for files under hc/
const normalized = editedPath.replace(/\\/g, "/");
if (!normalized.startsWith("hc/")) process.exit(0);

// Read profile for the test runner command
let profile;
try {
  const profilePath = join(cwd, "docs", "onramp", "profile.json");
  profile = JSON.parse(readFileSync(profilePath, "utf8"));
} catch {
  process.stdout.write(
    "[OnRamp hook] Could not read docs/onramp/profile.json — skipping test run.\n"
  );
  process.exit(0);
}

// Derive app label: hc/<app>/... -> hc.<app>
// Special case: hc/test.py (base class) -> run full suite
const parts = normalized.split("/"); // ["hc", "<app>", ...]
let testTarget;
if (parts.length >= 2 && parts[1] && parts[1] !== "test.py") {
  // e.g. hc/api/views.py -> hc.api
  testTarget = `${parts[0]}.${parts[1]}`;
} else {
  // hc/test.py or unexpected layout -> full suite
  testTarget = null;
}

const runner = profile.test_runner ?? "python manage.py test";
const cmd = testTarget ? `${runner} ${testTarget} --verbosity=2` : `${runner} --verbosity=2`;

const label = testTarget ?? "(full suite)";
process.stdout.write(
  `[OnRamp hook] ${editedPath} edited — running ${label} tests...\n`
);

const result = spawnSync(cmd, {
  shell: true,
  cwd,
  encoding: "utf8",
  timeout: 120_000,
});

const output = (result.stdout ?? "") + (result.stderr ?? "");

// Extract the Django summary line: "OK" or "FAILED (failures=N)"
// Django prints this before the database teardown message.
const summaryMatch = output.match(/^(OK|FAILED[^\n]*)/m);
const summary = summaryMatch ? summaryMatch[1] : (output.split("\n").filter((l) => l.trim()).pop() ?? "");

// Determine pass/fail
const passed = /^OK/.test(summary);
const statusIcon = passed ? "PASS" : "FAIL";

process.stdout.write(
  `[OnRamp hook] ${label}: ${statusIcon} — ${summary}\n\n${output}\n`
);

process.exit(0);
