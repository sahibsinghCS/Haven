/** @file Terminal helpers for demo scripts. */

const useColor = Boolean(process.stdout.isTTY);

const c = {
  reset: "\x1b[0m",
  bold: "\x1b[1m",
  dim: "\x1b[2m",
  red: "\x1b[31m",
  green: "\x1b[32m",
  yellow: "\x1b[33m",
  cyan: "\x1b[36m",
};

function paint(code, text) {
  if (!useColor) return text;
  return `${code}${text}${c.reset}`;
}

export function heading(text) {
  console.log(paint(c.bold + c.cyan, `\n${text}\n`));
}

export function ok(text) {
  console.log(paint(c.green, `  [ok] ${text}`));
}

export function warn(text) {
  console.log(paint(c.yellow, `  [!] ${text}`));
}

export function fail(text) {
  console.error(paint(c.red, `  [x] ${text}`));
}

export function hint(text) {
  console.log(paint(c.dim, text));
}

export function banner(lines) {
  const width = Math.max(...lines.map((l) => l.length), 40);
  const bar = "=".repeat(width);
  console.log(paint(c.bold, bar));
  for (const line of lines) console.log(paint(c.bold, `  ${line}`));
  console.log(paint(c.bold, bar));
}
