"use client"

import { roomosUi } from "@/lib/roomos/roomos-ui"
import { cn } from "@/lib/utils"

const SHIMMER_DARK = "haven-shimmer haven-shimmer-dark bg-zinc-800/45 motion-reduce:before:hidden"
const SHIMMER_LIGHT =
  "haven-shimmer bg-[linear-gradient(168deg,rgba(255,253,250,0.95)_0%,rgba(245,239,228,0.85)_100%)] motion-reduce:before:hidden"

export type LiveSkeletonVariant = "idle" | "booting" | "error"

const SKELETON_WASH: Record<LiveSkeletonVariant, string> = {
  idle:
    "radial-gradient(ellipse_85%_70%_at_50%_38%,rgba(113,113,122,0.1)_0%,transparent_55%),radial-gradient(ellipse_120%_90%_at_50%_120%,rgba(0,0,0,0.5),transparent_60%)",
  booting:
    "radial-gradient(ellipse_85%_70%_at_50%_38%,rgba(15,118,110,0.16)_0%,transparent_55%),radial-gradient(ellipse_120%_90%_at_50%_120%,rgba(0,0,0,0.5),transparent_60%)",
  error:
    "radial-gradient(ellipse_85%_70%_at_50%_38%,rgba(244,63,94,0.08)_0%,transparent_55%),radial-gradient(ellipse_120%_90%_at_50%_120%,rgba(0,0,0,0.5),transparent_60%)",
}

export function LiveStageSkeleton({
  variant = "booting",
  label = "Loading live view",
}: {
  variant?: LiveSkeletonVariant
  label?: string
}) {
  return (
    <div
      className="relative flex min-h-[calc(100dvh-3.5rem)] flex-1 flex-col overflow-hidden bg-zinc-950"
      role="status"
      aria-busy="true"
      aria-label={label}
    >
      <div
        className="absolute inset-0"
        style={{ background: SKELETON_WASH[variant] }}
      />
      <div className="relative flex flex-1 flex-col justify-between gap-6 p-4 sm:p-6 lg:p-8">
        <div className="flex justify-between gap-2">
          <div className={cn("h-8 w-36 rounded-full border border-white/[0.06]", SHIMMER_DARK)} />
          <div className={cn("h-8 w-44 rounded-full border border-white/[0.06]", SHIMMER_DARK)} />
        </div>
        <div className="pointer-events-none flex flex-1 items-center justify-center">
          <div className="size-20 rounded-full border border-white/[0.08] bg-zinc-900/40 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)] sm:size-24" />
        </div>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className={cn("h-36 max-w-lg flex-1 rounded-2xl border border-white/[0.06]", SHIMMER_DARK)} />
          <div className={cn("h-32 w-full max-w-sm rounded-2xl border border-white/[0.06]", SHIMMER_DARK)} />
        </div>
      </div>
      <p className="sr-only">Opening live view: starting camera and model.</p>
    </div>
  )
}

export function PreferencesSkeleton() {
  return (
    <div
      className="mx-auto flex w-full max-w-5xl flex-col gap-10 pb-28"
      role="status"
      aria-busy="true"
      aria-label="Loading preferences"
    >
      <div className={cn(roomosUi.pageEnter, "space-y-3")}>
        <div className={cn("h-2.5 w-28 rounded-full border border-[color:var(--haven-line-strong)]", SHIMMER_LIGHT)} />
        <div className={cn("h-10 max-w-sm rounded-xl border border-[color:var(--haven-line-strong)]", SHIMMER_LIGHT)} />
        <div className={cn("h-24 max-w-2xl rounded-2xl border border-[color:var(--haven-line-strong)]", SHIMMER_LIGHT)} />
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div
            key={i}
            className={cn("h-20 rounded-2xl border border-[color:var(--haven-line-strong)]", SHIMMER_LIGHT)}
          />
        ))}
      </div>
      <div className="grid gap-5 lg:grid-cols-2 lg:gap-6">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className={cn(
              "h-64 rounded-[1.4rem] border border-[color:var(--haven-line-strong)] shadow-[var(--haven-shadow-card)]",
              SHIMMER_LIGHT,
            )}
          />
        ))}
      </div>
      <span className="sr-only">Loading preferences…</span>
    </div>
  )
}
