/** @file Cross-platform repo paths for RoomOS npm scripts. */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SCRIPTS_DIR = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(SCRIPTS_DIR, "../..");
const BACKEND_DIR = path.join(REPO_ROOT, "backend");
const WEB_DIR = path.join(REPO_ROOT, "web");
const BUNDLE_DIR = path.join(BACKEND_DIR, "data", "models", "latest");

const MODEL_ARTIFACTS = [
  "model.json",
  "label_encoder.json",
  "feature_columns.json",
];

/**
 * @returns {string | null} Absolute path to venv python, or null.
 */
export function resolveVenvPython() {
  const candidates = [
    path.join(BACKEND_DIR, ".venv", "Scripts", "python.exe"),
    path.join(BACKEND_DIR, ".venv", "bin", "python"),
  ];
  for (const p of candidates) {
    if (fs.existsSync(p)) return p;
  }
  return null;
}

export function getRepoRoot() {
  return REPO_ROOT;
}

export function getBackendDir() {
  return BACKEND_DIR;
}

export function getWebDir() {
  return WEB_DIR;
}

export function getBundleDir() {
  return BUNDLE_DIR;
}

/** @returns {string[]} Missing required artifact filenames. */
export function missingModelArtifacts() {
  return MODEL_ARTIFACTS.filter((name) => !fs.existsSync(path.join(BUNDLE_DIR, name)));
}

export function hasNodeModules(dir) {
  return fs.existsSync(path.join(dir, "node_modules"));
}
