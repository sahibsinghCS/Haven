#!/usr/bin/env node
/** Open dataset folders in the system file manager (gitignored paths are hidden in Cursor). */

import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { getBackendDir } from "./lib/paths.mjs";

const kind = (process.argv[2] || "base").toLowerCase();
const backend = getBackendDir();

const targets = {
  base: path.join(backend, "data", "base_images"),
  personal: path.join(backend, "data", "raw_images"),
  features: path.join(backend, "data", "features"),
  models: path.join(backend, "data", "models", "latest"),
};

const target = targets[kind] ?? targets.base;
if (!target) {
  console.error(`Unknown folder kind: ${kind}. Use: base | personal | features | models`);
  process.exit(1);
}

const platform = process.platform;
let cmd;
let args;
if (platform === "win32") {
  cmd = "explorer";
  args = [target];
} else if (platform === "darwin") {
  cmd = "open";
  args = [target];
} else {
  cmd = "xdg-open";
  args = [target];
}

console.log(`Opening: ${target}`);
spawn(cmd, args, { detached: true, stdio: "ignore" }).unref();
