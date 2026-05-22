#!/usr/bin/env node
/** @file Deterministic demo: replay fixture (no camera/model required). */

import { spawn } from "node:child_process";
import path from "node:path";
import { getRepoRoot } from "./lib/paths.mjs";
import { banner, hint } from "./lib/print.mjs";
import { runPreflight } from "./preflight.mjs";

process.env.ROOMOS_DEMO_MODE = "replay";

const { ok } = runPreflight({ strict: true, allowDemoReplay: true });
if (!ok) process.exit(1);

banner([
  "RoomOS DEMO REPLAY mode",
  "Web UI:  http://127.0.0.1:3000/live",
  "API:     http://127.0.0.1:8000/api/live/status",
  "Banner on /live says: Demo replay active (not live inference)",
  "Stop:    Ctrl+C",
]);

hint("  No webcam or trained model required.");
hint("  Toggle Live camera vs Demo replay on /live if the API is up.\n");

const npmCmd = process.platform === "win32" ? "npm.cmd" : "npm";
const child = spawn(npmCmd, ["run", "dev:stack"], {
  cwd: getRepoRoot(),
  stdio: "inherit",
  shell: process.platform === "win32",
  env: { ...process.env, ROOMOS_DEMO_MODE: "replay" },
});

child.on("exit", (code) => process.exit(code ?? 0));
