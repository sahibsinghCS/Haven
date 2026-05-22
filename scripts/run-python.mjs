#!/usr/bin/env node
/** @file Run a Python script with backend/.venv (cross-platform). */

import { spawn } from "node:child_process";
import path from "node:path";
import { getBackendDir, resolveVenvPython } from "./lib/paths.mjs";
import { fail, hint } from "./lib/print.mjs";

const py = resolveVenvPython();
if (!py) {
  fail("backend/.venv not found.");
  hint("  npm run setup:venv");
  process.exit(1);
}

const args = process.argv.slice(2);
if (!args.length) {
  fail("Usage: node scripts/run-python.mjs <script.py> [args...]");
  process.exit(1);
}

const child = spawn(py, args, {
  cwd: getBackendDir(),
  stdio: "inherit",
  env: { ...process.env },
});

child.on("exit", (code) => process.exit(code ?? 1));
