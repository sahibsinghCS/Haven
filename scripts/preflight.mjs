#!/usr/bin/env node
/** @file Pre-demo checks: deps, venv, model bundle. */

import { spawnSync } from "node:child_process";

import {
  getBackendDir,
  getBundleDir,
  getRepoRoot,
  getWebDir,
  hasNodeModules,
  missingModelArtifacts,
  resolveVenvPython,
} from "./lib/paths.mjs";
import { fail, heading, hint, ok, warn } from "./lib/print.mjs";

function venvImportCheck(py) {
  const r = spawnSync(
    py,
    ["-c", "import numpy; import pydantic_core; import fastapi; import typer"],
    { encoding: "utf8", shell: false },
  );
  return r.status === 0;
}

function venvPythonVersion(py) {
  const r = spawnSync(py, ["-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"], {
    encoding: "utf8",
    shell: false,
  });
  if (r.status !== 0) return null;
  return (r.stdout || "").trim();
}

/**
 * @param {{ strict?: boolean, allowDemoReplay?: boolean }} opts
 * @returns {{ ok: boolean, blockers: string[] }}
 */
export function runPreflight(opts = {}) {
  const strict = opts.strict !== false;
  const allowDemoReplay =
    opts.allowDemoReplay === true ||
    process.env.ROOMOS_DEMO_MODE === "replay" ||
    (process.env.ROOMOS_DEMO_MODE || "").toLowerCase() === "demo-replay";
  const blockers = [];

  heading("RoomOS preflight");

  if (!hasNodeModules(getRepoRoot())) {
    blockers.push("root npm dependencies missing");
    fail("Run: npm install  (repo root)");
  } else {
    ok("Root npm dependencies");
  }

  if (!hasNodeModules(getWebDir())) {
    blockers.push("web npm dependencies missing");
    fail("Run: npm install --prefix web");
  } else {
    ok("Web npm dependencies");
  }

  const py = resolveVenvPython();
  if (!py) {
    blockers.push("Python venv missing");
    fail(`No backend/.venv — run from repo root:`);
    hint("  npm run setup:venv");
  } else {
    const ver = venvPythonVersion(py);
    if (ver !== "3.11" || !venvImportCheck(py)) {
      blockers.push("Python venv broken or wrong version");
      fail(`Venv uses Python ${ver ?? "?"} — need 3.11 with working numpy/pydantic`);
      hint("  Common cause: `python -m venv` used Python 3.14 on Windows");
      hint("  Fix: npm run setup:venv");
    } else {
      ok(`Python venv (${py}, ${ver})`);
    }
  }

  const missing = missingModelArtifacts();
  if (missing.length) {
    if (allowDemoReplay) {
      warn("Model bundle missing — OK for demo replay mode");
      hint("  Live camera mode still needs: npm run setup:model");
    } else {
      blockers.push("model bundle missing");
      fail(`Model not ready: backend/data/models/latest/`);
      for (const name of missing) fail(`  missing ${name}`);
      hint("");
      hint("  One-time setup (~5–15 min, downloads OpenCLIP on first train):");
      hint("    npm run setup:model");
      hint("  or:  npm run train:demo");
      hint("");
      hint("  Or deterministic replay (no model):");
      hint("    npm run demo:replay");
      hint("");
      hint("  Then start the demo:");
      hint("    npm run demo");
    }
  } else {
    ok(`Model bundle (${getBundleDir()})`);
  }

  if (blockers.length && strict) {
    console.log("");
    fail("Preflight failed — fix the items above, then run: npm run demo");
    return { ok: false, blockers };
  }

  if (blockers.length) {
    for (const b of blockers) warn(b);
    return { ok: false, blockers };
  }

  ok("Ready for live demo");
  return { ok: true, blockers: [] };
}

import { pathToFileURL } from "node:url";

const isMain =
  process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;

if (isMain) {
  const { ok } = runPreflight({ strict: true });
  process.exit(ok ? 0 : 1);
}
