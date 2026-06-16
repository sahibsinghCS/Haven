/** Second pass: line-level em/en dash removal in user copy. */
import fs from "node:fs"
import path from "node:path"

const ROOT = path.join(import.meta.dirname, "..", "src")
const SKIP_DIRS = new Set(["node_modules", "_generated", ".next", "components/ui"])
const SKIP_FILES = new Set(["format-camera-device-label.ts"])

function walk(dir, out = []) {
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    if (SKIP_DIRS.has(ent.name)) continue
    const p = path.join(dir, ent.name)
    if (ent.isDirectory()) walk(p, out)
    else if (/\.(tsx?)$/.test(ent.name)) out.push(p)
  }
  return out
}

function fixLine(line) {
  if (SKIP_FILES.has(path.basename(line))) return null
  return line
}

function transformLine(line) {
  if (/^\s*(\*|\/\/|import )/.test(line)) return line
  if (/className=|cva\(|\.replace\(|\/\[-/.test(line)) return line
  if (!/[—–]/.test(line) && !/Wi[-‑]Fi/i.test(line)) return line
  let t = line
  t = t.replace(/ — /g, ". ")
  t = t.replace(/—/g, ". ")
  t = t.replace(/–/g, " to ")
  t = t.replace(/Wi‑Fi|Wi-Fi/gi, "WiFi")
  t = t.replace(/\s{2,}/g, " ")
  return t
}

let changed = 0
for (const file of walk(ROOT)) {
  if (SKIP_FILES.has(path.basename(file))) continue
  const raw = fs.readFileSync(file, "utf8")
  const next = raw
    .split("\n")
    .map((line) => transformLine(line))
    .join("\n")
  if (next !== raw) {
    fs.writeFileSync(file, next, "utf8")
    changed++
    console.log("updated:", path.relative(ROOT, file))
  }
}
console.log(`Done. ${changed} files updated.`)
