"use client"

import type { CompatMismatch } from "@/lib/roomos/api-client"

export function HavenCompatDetails({ mismatches }: { mismatches: CompatMismatch[] }) {
  if (!mismatches.length) return null

  return (
    <div className="space-y-2">
      <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-rose-200/80">
        Config mismatches
      </p>
      <ul className="max-h-48 space-y-2 overflow-y-auto rounded-lg border border-rose-400/25 bg-rose-950/45 p-3 text-[11px] text-rose-100/95">
        {mismatches.slice(0, 6).map((m) => (
          <li key={`${m.category}-${m.field}`} className="space-y-1 border-b border-rose-400/10 pb-2 last:border-0 last:pb-0">
            <p>
              <span className="font-semibold uppercase text-rose-200/90">{m.category}</span>
              <span className="text-rose-300/70"> · {m.field}</span>
            </p>
            <p className="font-mono text-[10px] leading-snug text-rose-200/80">
              train: {m.train}
            </p>
            <p className="font-mono text-[10px] leading-snug text-rose-200/80">
              inference: {m.inference}
            </p>
            {m.detail ? (
              <p className="text-[10px] text-rose-200/70">{m.detail}</p>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  )
}
