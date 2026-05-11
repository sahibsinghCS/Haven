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
        className="relative size-14 shrink-0 overflow-hidden rounded-xl border border-zinc-200/95 bg-white shadow-inner sm:size-[4.5rem]"
        aria-hidden
      >
        <div
          className="absolute inset-0"
          style={{
            background: `linear-gradient(155deg, ${normalized}, #e4e4e7)`,
            opacity: 0.25 + level * 0.82,
          }}
        />
        <div
          className="absolute inset-0 bg-zinc-900"
          style={{ opacity: (1 - level) * 0.55 }}
        />
      </div>
      <div className="min-w-0 space-y-1">
        <p className="text-[0.65rem] font-medium uppercase tracking-[0.12em] text-zinc-500">
          Preview
        </p>
        <p className="font-mono text-xs tracking-tight text-zinc-800">{normalized}</p>
        <p className="text-xs tabular-nums text-zinc-600">{Math.round(brightness)}% brightness</p>
      </div>
    </div>
  )
}
