/** @file Pre-trained model bundle shipped in backend/shipped_models/ */

import fs from "node:fs";
import path from "node:path";

import { getBackendDir, getBundleDir, missingModelArtifacts } from "./paths.mjs";

export const SHIPPED_VARIANT = "multi_room_v2";

export const SHIPPED_FILES = [
  "model.json",
  "label_encoder.json",
  "feature_columns.json",
  "train_config.json",
  "live_compat.json",
  "metrics.json",
  "training_summary.json",
];

export function getShippedDir(variant = SHIPPED_VARIANT) {
  return path.join(getBackendDir(), "shipped_models", variant);
}

/** @returns {string[]} Missing filenames in the shipped bundle. */
export function missingShippedArtifacts(variant = SHIPPED_VARIANT) {
  const dir = getShippedDir(variant);
  if (!fs.existsSync(dir)) return [...SHIPPED_FILES];
  return SHIPPED_FILES.filter((name) => !fs.existsSync(path.join(dir, name)));
}

/** @returns {boolean} */
export function shippedModelReady(variant = SHIPPED_VARIANT) {
  return missingShippedArtifacts(variant).length === 0;
}

/**
 * Copy shipped bundle → backend/data/models/latest/
 * @returns {{ ok: true } | { ok: false, reason: string }}
 */
export function installShippedModel(variant = SHIPPED_VARIANT) {
  const shippedDir = getShippedDir(variant);
  const missingShipped = missingShippedArtifacts(variant);
  if (missingShipped.length) {
    return {
      ok: false,
      reason:
        missingShipped.length === SHIPPED_FILES.length
          ? `Shipped model not found at ${shippedDir}`
          : `Shipped bundle incomplete: ${missingShipped.join(", ")}`,
    };
  }

  const bundleDir = getBundleDir();
  fs.mkdirSync(bundleDir, { recursive: true });

  for (const name of SHIPPED_FILES) {
    fs.copyFileSync(path.join(shippedDir, name), path.join(bundleDir, name));
  }

  const stillMissing = missingModelArtifacts();
  if (stillMissing.length) {
    return { ok: false, reason: `Install failed; still missing ${stillMissing.join(", ")}` };
  }

  return { ok: true };
}
