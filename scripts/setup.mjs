#!/usr/bin/env node
/** @file One-time / repair setup guide for local demo. */

import { execSync } from "node:child_process";
import {
  getBackendDir,
  getRepoRoot,
  getWebDir,
  hasNodeModules,
  missingModelArtifacts,
  resolveVenvPython,
} from "./lib/paths.mjs";
import { banner, fail, heading, hint, ok } from "./lib/print.mjs";

heading("RoomOS setup");

const steps = [];

if (!hasNodeModules(getRepoRoot())) {
  steps.push("npm install");
}
if (!hasNodeModules(getWebDir())) {
  steps.push("npm install --prefix web");
}
if (!resolveVenvPython()) {
  steps.push("create backend venv + pip install");
  hint("  cd backend");
  hint("  python -m venv .venv");
  hint("  # activate venv, then: pip install -r requirements.txt");
}
if (missingModelArtifacts().length) {
  steps.push("npm run setup:model");
}

if (!steps.length) {
  ok("Everything looks installed. Start the demo with: npm run demo");
  process.exit(0);
}

banner(["Setup needed before demo"]);

for (const s of steps) hint(`  - ${s}`);

hint("");
hint("Quick path (run from repo root):");

if (!hasNodeModules(getRepoRoot()) || !hasNodeModules(getWebDir())) {
  hint("  npm install");
  hint("  npm install --prefix web");
}

if (!resolveVenvPython()) {
  hint("  cd backend && python -m venv .venv");
  hint("  # activate, then: pip install -r requirements.txt");
}

if (missingModelArtifacts().length) {
  hint("  npm run setup:model   # trains demo model to backend/data/models/latest");
}

hint("");
hint("Then:  npm run demo");

if (process.argv.includes("--install-deps")) {
  heading("Installing npm dependencies");
  try {
    if (!hasNodeModules(getRepoRoot())) {
      execSync("npm install", { cwd: getRepoRoot(), stdio: "inherit" });
      ok("Root dependencies");
    }
    if (!hasNodeModules(getWebDir())) {
      execSync("npm install", { cwd: getWebDir(), stdio: "inherit" });
      ok("Web dependencies");
    }
  } catch {
    fail("npm install failed");
    process.exit(1);
  }
}

process.exit(steps.length ? 1 : 0);
