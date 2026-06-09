#!/usr/bin/env node
/** @file Start FastAPI with backend/.venv (cross-platform). */

import { spawn } from "node:child_process";
import { getBackendDir, resolveVenvPython } from "./lib/paths.mjs";
import { fail, hint } from "./lib/print.mjs";

const py = resolveVenvPython();
if (!py) {
  fail("backend/.venv not found — run: npm run setup");
  process.exit(1);
}

// Whitelist the source dirs so uvicorn's --reload watcher ignores the engine's
// per-burst writes to data/logs/predictions.jsonl, which otherwise spam
// "INFO 1 change detected" every ~1.5 s and drown out the access log.
// (Wildcard patterns get glob-expanded by Python on Windows before uvicorn
// sees them, so we avoid --reload-include/--reload-exclude entirely.)
const child = spawn(
  py,
  [
    "-m",
    "uvicorn",
    "app.main:app",
    "--reload",
    "--reload-dir",
    "app",
    "--reload-dir",
    "roomos",
    "--reload-dir",
    "configs",
    "--host",
    "127.0.0.1",
    "--port",
    "8000",
    "--no-access-log",
    "--log-level",
    "warning",
  ],
  {
    cwd: getBackendDir(),
    stdio: "inherit",
    env: {
      ...process.env,
      OPENCV_LOG_LEVEL: process.env.OPENCV_LOG_LEVEL || "ERROR",
      ROOMOS_LOG_RICH: process.env.ROOMOS_LOG_RICH || "0",
    },
  },
);

child.on("exit", (code) => process.exit(code ?? 1));
