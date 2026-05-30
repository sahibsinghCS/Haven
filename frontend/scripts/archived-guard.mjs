#!/usr/bin/env node
/** Block accidental `npm run dev` in archived Vite scratch UI. */

import { fail, hint } from "../../scripts/lib/print.mjs";

fail("frontend/ is ARCHIVED — not the hackathon demo UI.");
console.log("");
hint("  From repo root, run:");
hint("    npm run demo");
hint("");
hint("  Then open:  http://127.0.0.1:3000/live");
hint("  (Next.js in web/ — not Vite on :5173)");
console.log("");
hint("  See frontend/ARCHIVE.md");
process.exit(1);
