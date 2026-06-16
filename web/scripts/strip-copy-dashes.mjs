/**
 * Strip em/en dashes from user-facing copy. Safe for Tailwind, className, imports, comments.
 */
import fs from "node:fs"
import path from "node:path"

const ROOT = path.join(import.meta.dirname, "..", "src")
const SKIP_DIRS = new Set(["node_modules", "_generated", ".next", "components/ui"])

function walk(dir, out = []) {
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    if (SKIP_DIRS.has(ent.name)) continue
    const p = path.join(dir, ent.name)
    if (ent.isDirectory()) walk(p, out)
    else if (/\.(tsx?)$/.test(ent.name)) out.push(p)
  }
  return out
}

function isTailwindOrCss(s) {
  if (/\[[\w%-]+\]/.test(s)) return true
  if (/(?:^|\s)(?:bg|text|border|hover|dark|focus|aria|data|from|to|via|ring|shadow|rounded|flex|grid|gap|px|py|pt|pb|pl|pr|mt|mb|ml|mr|h|w|min|max|size|opacity|tracking|leading|font|uppercase|lowercase|whitespace|overflow|absolute|relative|fixed|sticky|inset|z|col|row|space|divide|transition|animate|group|has|in-data|supports|not-|sm:|md:|lg:|xl:)/.test(s))
    return true
  if ((s.match(/-/g) ?? []).length >= 3 && !/[—–]/.test(s)) return true
  return false
}

function looksLikeCodeToken(s) {
  if (!s || s.length < 2) return true
  if (isTailwindOrCss(s)) return true
  if (/^https?:\/\//.test(s)) return true
  if (/^[@#/]/.test(s)) return true
  if (/^(var\(--|color-mix|oklab|in_oklab)/.test(s)) return true
  if (/^[a-z0-9]+(-[a-z0-9]+)+$/.test(s) && !/\s/.test(s) && s.length < 48) return true
  if (/\.(tsx?|css|json|yaml|md|png|jpg|svg)$/.test(s)) return true
  return false
}

function polishCopy(s) {
  let t = s
  t = t.replace(/—/g, ". ")
  t = t.replace(/–/g, " to ")
  t = t.replace(/Wi‑Fi|Wi-Fi/gi, "WiFi")
  if (!looksLikeCodeToken(t)) {
    t = t.replace(/(\p{L})-(\p{L})/gu, "$1 $2")
  }
  t = t.replace(/\s{2,}/g, " ")
  t = t.replace(/\.\s+\./g, ".")
  t = t.replace(/\s+([,.!?;:])/g, "$1")
  return t
}

function polishTemplate(body) {
  const parts = body.split(/(\$\{[^}]+\})/g)
  return parts.map((part) => (part.startsWith("${") ? part : polishCopy(part))).join("")
}

function transformQuoted(content, quote) {
  if (looksLikeCodeToken(content)) return content
  if (quote === "`") return polishTemplate(content)
  return polishCopy(content)
}

function transformFile(text) {
  let out = ""
  let i = 0
  while (i < text.length) {
    const ch = text[i]
    if (ch === '"' || ch === "'" || ch === "`") {
      const quote = ch
      let j = i + 1
      let body = ""
      while (j < text.length) {
        if (text[j] === "\\") {
          body += text[j] + (text[j + 1] ?? "")
          j += 2
          continue
        }
        if (text[j] === quote) break
        body += text[j]
        j++
      }
      const before = text.slice(Math.max(0, i - 32), i)
      const isClassName =
        /className\s*=\s*$/.test(before) ||
        /cn\(\s*$/.test(before) ||
        /cva\(\s*$/.test(before) ||
        /classNames?\s*=\s*$/.test(before)
      const lineStart = text.lastIndexOf("\n", i) + 1
      const linePrefix = text.slice(lineStart, i)
      const isImport = /^\s*import\s/.test(linePrefix)
      const isComment = /^\s*(\/\/|\/\*|\*)/.test(linePrefix)
      const transformed =
        isClassName || isImport || isComment ? body : transformQuoted(body, quote)
      out += quote + transformed + quote
      i = j + 1
      continue
    }
    out += ch
    i++
  }
  return out
}

let changed = 0
for (const file of walk(ROOT)) {
  const raw = fs.readFileSync(file, "utf8")
  const next = transformFile(raw)
  if (next !== raw) {
    fs.writeFileSync(file, next, "utf8")
    changed++
    console.log("updated:", path.relative(ROOT, file))
  }
}
console.log(`Done. ${changed} files updated.`)
