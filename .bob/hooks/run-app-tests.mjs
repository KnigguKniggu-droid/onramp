#!/usr/bin/env node
/**
 * OnRamp post-tool-use hook: run the app-level test suite whenever a
 * Python source file is written or patched.
 *
 * Profile-driven: reads docs/onramp/profile.json for:
 *   source_roots  — array of root dirs to watch (default ["hc"])
 *   test_runner   — command to run tests
 *   app_root      — prefix used to derive the app label for Django
 *   framework     — "django" (default) or "unittest"
 *
 * Input (stdin): PostToolUse JSON payload from Bob.
 * Output: stdout text is added to Bob's context as a tool annotation.
 * Exit 0 always — this hook reports but never blocks.
 */

import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { join } from "node:path";

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

// Read profile
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

// Only fire for files under one of the watched source roots
const normalized = editedPath.replace(/\\/g, "/");
const sourceRoots = profile.source_roots ?? [profile.app_root ?? "hc"];
const watched = sourceRoots.some((root) => normalized.startsWith(root + "/"));
if (!watched) process.exit(0);

const framework = (profile.framework ?? "django").toLowerCase();
const runner = profile.test_runner ?? "python manage.py test";
const appRoot = profile.app_root ?? sourceRoots[0];

// Derive test target
let testTarget = null;
if (framework === "django") {
  // hc/api/views.py -> hc.api  |  hc/test.py -> run full suite
  const parts = normalized.split("/");
  if (parts.length >= 2 && parts[1] && !parts[1].endsWith(".py")) {
    testTarget = `${parts[0]}.${parts[1]}`;
  }
}
// For plain unittest or unknown frameworks, run the full suite (testTarget stays null)

// Build command — only pass --verbosity=2 for Django
const verbosity = framework === "django" ? " --verbosity=2" : "";
const cmd = testTarget
  ? `${runner} ${testTarget}${verbosity}`
  : `${runner}${verbosity}`;

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

// Extract summary: works for both Django and plain unittest
// Both emit "OK" or "FAILED ..." as the final result line.
const summaryMatch = output.match(/^(OK|FAILED[^\n]*)/m);
const summary = summaryMatch
  ? summaryMatch[1]
  : (output.split("\n").filter((l) => l.trim()).pop() ?? "");

// Determine pass/fail
const passed = /^OK/.test(summary);
const statusIcon = passed ? "PASS" : "FAIL";

process.stdout.write(
  `[OnRamp hook] ${label}: ${statusIcon} — ${summary}\n\n${output}\n`
);

process.exit(0);
