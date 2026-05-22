#!/usr/bin/env node
/** @file Create backend/.venv with Python 3.11 and install requirements. */

import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { getBackendDir, resolveVenvPython } from "./lib/paths.mjs";
import { fail, heading, hint, ok } from "./lib/print.mjs";

const BACKEND = getBackendDir();
const VENV_DIR = path.join(BACKEND, ".venv");
const REQ = path.join(BACKEND, "requirements.txt");
const WANT_MAJOR = 3;
const WANT_MINOR = 11;

function run(cmd, args, opts = {}) {
  const r = spawnSync(cmd, args, {
    stdio: "inherit",
    shell: process.platform === "win32",
    ...opts,
  });
  return r.status ?? 1;
}

function venvPythonVersion(py) {
  const r = spawnSync(py, ["-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"], {
    encoding: "utf8",
    shell: false,
  });
  if (r.status !== 0) return null;
  return (r.stdout || "").trim();
}

function smokeTest(py) {
  const r = spawnSync(
    py,
    ["-c", "import numpy; import pydantic_core; import fastapi; import typer; print('ok')"],
    { encoding: "utf8", shell: false },
  );
  return r.status === 0;
}

/** @returns {string | null} Launcher for Python 3.11 */
function findPython311() {
  if (process.platform === "win32") {
    const r = spawnSync("py", ["-3.11", "-c", "import sys; print(sys.executable)"], {
      encoding: "utf8",
      shell: false,
    });
    if (r.status === 0) {
      const exe = (r.stdout || "").trim();
      if (exe && fs.existsSync(exe)) return exe;
    }
  }
  for (const cmd of ["python3.11", "python311"]) {
    const r = spawnSync(cmd, ["-c", "import sys; print(sys.executable)"], {
      encoding: "utf8",
      shell: process.platform === "win32",
    });
    if (r.status === 0) {
      const exe = (r.stdout || "").trim();
      if (exe) return exe;
    }
  }
  return null;
}

function removeVenv() {
  if (!fs.existsSync(VENV_DIR)) return;
  fs.rmSync(VENV_DIR, { recursive: true, force: true, maxRetries: 3 });
}

heading("Ensure backend/.venv (Python 3.11)");

const existing = resolveVenvPython();
if (existing) {
  const ver = venvPythonVersion(existing);
  if (ver === `${WANT_MAJOR}.${WANT_MINOR}` && smokeTest(existing)) {
    ok(`Existing venv OK (${existing}, Python ${ver})`);
    process.exit(0);
  }
  fail(`Broken or wrong venv (Python ${ver ?? "unknown"}) — rebuilding with 3.11`);
  removeVenv();
}

const py311 = findPython311();
if (!py311) {
  fail("Python 3.11 not found.");
  hint("  Windows: install from https://www.python.org/downloads/release/python-3119/");
  hint("  Then: py -3.11 --version");
  hint("  Do NOT use bare `python -m venv` if it points to 3.14.");
  process.exit(1);
}

ok(`Using ${py311}`);

if (process.platform === "win32") {
  if (run("py", ["-3.11", "-m", "venv", VENV_DIR], { cwd: BACKEND }) !== 0) {
    fail("venv creation failed");
    process.exit(1);
  }
} else {
  if (run(py311, ["-m", "venv", VENV_DIR], { cwd: BACKEND }) !== 0) {
    fail("venv creation failed");
    process.exit(1);
  }
}

const vpy = resolveVenvPython();
if (!vpy) {
  fail("venv created but python not found");
  process.exit(1);
}

ok(`Created ${vpy} (${venvPythonVersion(vpy)})`);

if (run(vpy, ["-m", "pip", "install", "-U", "pip"], { cwd: BACKEND }) !== 0) process.exit(1);
if (run(vpy, ["-m", "pip", "install", "-r", REQ], { cwd: BACKEND }) !== 0) process.exit(1);

if (!smokeTest(vpy)) {
  fail("Smoke test failed (numpy / pydantic / fastapi)");
  process.exit(1);
}

ok("Dependencies installed and import check passed");
hint("  npm run setup:model");
hint("  npm run demo");
