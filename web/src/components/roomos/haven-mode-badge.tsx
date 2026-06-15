"use client"

import { cn } from "@/lib/utils"
import type { HavenSystemMode } from "@/lib/roomos/haven-system-state"
import { MODE_LABEL } from "@/lib/roomos/haven-system-state"

const MODE_STYLE: Record<
  HavenSystemMode,
  { shell: string; dot?: string; pulse?: boolean }
> = {
  live: {
    shell: "border-emerald-400/45 bg-emerald-950/55 text-emerald-100",
    dot: "bg-emerald-400",
    pulse: true,
  },
  booting: {
    shell: "border-teal-400/40 bg-teal-950/50 text-teal-100",
    dot: "bg-teal-400",
    pulse: true,
  },
  camera_off: {
    shell: "border-zinc-500/40 bg-zinc-900/80 text-zinc-300",
    dot: "bg-zinc-500",
  },
  setup: {
    shell: "border-sky-400/35 bg-sky-950/45 text-sky-100",
    dot: "bg-sky-400",
  },
  demo_model: {
    shell:
      "border-amber-400/55 bg-[repeating-linear-gradient(-45deg,rgba(245,158,11,0.14)_0,rgba(245,158,11,0.14)_6px,transparent_6px,transparent_12px)] text-amber-50 shadow-[inset_0_0_0_1px_rgba(245,158,11,0.25)]",
    dot: "bg-amber-400",
  },
  replay: {
    shell: "border-violet-400/50 bg-violet-950/60 text-violet-100",
    dot: "bg-violet-400",
  },
  api_offline: {
    shell: "border-stone-400/40 bg-stone-900/70 text-stone-200",
    dot: "bg-stone-400",
  },
  compat_error: {
    shell: "border-rose-400/50 bg-rose-950/55 text-rose-100",
    dot: "bg-rose-400",
  },
  model_missing: {
    shell: "border-amber-400/45 bg-amber-950/50 text-amber-100",
    dot: "bg-amber-400",
  },
  engine_error: {
    shell: "border-rose-400/45 bg-rose-950/55 text-rose-100",
    dot: "bg-rose-400",
  },
  camera_error: {
    shell: "border-rose-400/40 bg-rose-950/50 text-rose-100",
    dot: "bg-rose-400",
  },
}

export function HavenModeBadge({
  mode,
  className,
  size = "sm",
}: {
  mode: HavenSystemMode
  className?: string
  size?: "sm" | "md"
}) {
  const style = MODE_STYLE[mode]
  const label = MODE_LABEL[mode]

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border font-bold uppercase tracking-[0.14em]",
        size === "md" ? "px-3 py-1 text-[11px]" : "px-2 py-0.5 text-[9px] sm:text-[10px]",
        style.shell,
        className,
      )}
      role="status"
    >
      {style.dot ? (
        <span className="relative flex size-1.5 shrink-0" aria-hidden>
          {style.pulse ? (
            <span
              className={cn(
                "absolute inline-flex size-full animate-ping rounded-full opacity-70 motion-reduce:hidden",
                style.dot,
              )}
            />
          ) : null}
          <span className={cn("relative inline-flex size-1.5 rounded-full", style.dot)} />
        </span>
      ) : null}
      {label}
    </span>
  )
}
