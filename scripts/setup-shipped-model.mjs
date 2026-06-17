#!/usr/bin/env node
/** @file Install the pre-trained multi-room model from backend/shipped_models/ */

import { getBundleDir } from "./lib/paths.mjs";
import { installShippedModel, SHIPPED_VARIANT } from "./lib/shipped-model.mjs";
import { fail, heading, hint, ok } from "./lib/print.mjs";

heading("Install pre-trained multi-room model");

const result = installShippedModel();
if (!result.ok) {
  fail(result.reason);
  hint(`  This repo should include backend/shipped_models/${SHIPPED_VARIANT}/`);
  process.exit(1);
}

ok(`Pre-trained model installed to ${getBundleDir()}`);
hint("  Trained on public multi-room photos (base_images), not synthetic bootstrap.");
hint("  Next: npm run train:verify");
hint("  Then: npm run demo");
hint("");
hint("  Fallback only (weaker on real rooms): npm run setup:model");
