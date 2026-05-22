#!/usr/bin/env node
/** @file Hackathon demo: preflight then web + API. */

import { spawn } from "node:child_process";
import path from "node:path";
import { getRepoRoot } from "./lib/paths.mjs";
import { banner, hint } from "./lib/print.mjs";
import { runPreflight } from "./preflight.mjs";

const { ok } = runPreflight({ strict: true });
if (!ok) process.exit(1);

banner([
  "RoomOS live demo",
  "Web UI:  http://127.0.0.1:3000/live",
  "API:     http://127.0.0.1:8000/api/health",
  "Stop:    Ctrl+C",
]);

hint("  First OpenCLIP load can take a minute after the engine starts.");
hint("  Allow camera access if prompted by the OS.\n");

const npmCmd = process.platform === "win32" ? "npm.cmd" : "npm";
const child = spawn(npmCmd, ["run", "dev:stack"], {
  cwd: getRepoRoot(),
  stdio: "inherit",
  shell: process.platform === "win32",
});

child.on("exit", (code) => process.exit(code ?? 0));
