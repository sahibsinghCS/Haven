"use client"

import { cn } from "@/lib/utils"

export type LightTonePreviewProps = {
  hex: string
  brightness: number
  className?: string
}

/** Small swatch approximating light color at a given brightness level. */
export function LightTonePreview({ hex, brightness, className }: LightTonePreviewProps) {
  const normalized = /^#[0-9A-Fa-f]{6}$/i.test(hex) ? hex : "#71717a"
  const level = Math.min(100, Math.max(0, brightness)) / 100

  return (
    <div className={cn("flex items-center gap-3", className)}>
      <div
        className="relative size-14 shrink-0 overflow-hidden rounded-2xl border border-[color:var(--haven-line-strong)] bg-stone-900 shadow-[inset_0_1px_2px_rgba(18,17,15,0.18),0_1px_2px_rgba(18,17,15,0.06)] sm:size-[4.25rem]"
        aria-hidden
      >
        <div
          className="absolute inset-0"
          style={{
            background: `radial-gradient(circle at 28% 22%, rgba(255,255,255,0.7), transparent 55%), linear-gradient(155deg, ${normalized}, #1f1d1c)`,
            opacity: 0.32 + level * 0.78,
          }}
        />
        <div
          className="pointer-events-none absolute inset-0 bg-zinc-950"
          style={{ opacity: (1 - level) * 0.6 }}
        />
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 rounded-2xl ring-1 ring-inset ring-white/12"
        />
      </div>
      <div className="min-w-0 space-y-1">
        <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-[color:var(--haven-faint)]">
          Preview
        </p>
        <p className="font-mono text-[12px] tracking-tight text-[color:var(--haven-ink-soft)]">
          {normalized.toUpperCase()}
        </p>
        <p className="text-[12px] tabular-nums text-[color:var(--haven-muted)]">
          {Math.round(brightness)}% brightness
        </p>
      </div>
    </div>
  )
}
