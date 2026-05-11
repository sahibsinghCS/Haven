"use client"

import { cn } from "@/lib/utils"

const SHIMMER_DARK =
  "relative overflow-hidden bg-zinc-800/45 before:absolute before:inset-0 before:-translate-x-full before:bg-gradient-to-r before:from-transparent before:via-white/[0.06] before:to-transparent before:[animation:shimmer_2.4s_ease-in-out_infinite] motion-reduce:before:hidden"

const SHIMMER_LIGHT =
  "relative overflow-hidden bg-[linear-gradient(168deg,rgba(255,253,250,0.95)_0%,rgba(245,239,228,0.85)_100%)] before:absolute before:inset-0 before:-translate-x-full before:bg-gradient-to-r before:from-transparent before:via-white/55 before:to-transparent before:[animation:shimmer_2.4s_ease-in-out_infinite] motion-reduce:before:hidden"

export function LiveStageSkeleton() {
  return (
    <>
      <style>{`@keyframes shimmer { 100% { transform: translateX(100%); } }`}</style>
      <div
        className="relative flex min-h-[calc(100dvh-3.5rem)] flex-1 flex-col overflow-hidden bg-zinc-950"
        role="status"
        aria-busy="true"
        aria-label="Loading live view"
      >
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_85%_70%_at_50%_38%,rgba(15,118,110,0.12)_0%,transparent_55%),radial-gradient(ellipse_120%_90%_at_50%_120%,rgba(0,0,0,0.5),transparent_60%)]" />
        <div className="relative flex flex-1 flex-col justify-between gap-8 p-4 sm:p-6 lg:p-8">
          <div className="flex justify-between gap-3">
            <div className={cn("h-9 w-40 rounded-full border border-white/[0.06]", SHIMMER_DARK)} />
            <div className={cn("h-9 w-48 rounded-full border border-white/[0.06]", SHIMMER_DARK)} />
          </div>
          <div className="pointer-events-none flex flex-1 items-center justify-center">
            <div className="size-24 rounded-full border border-white/[0.08] bg-zinc-900/40 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]" />
          </div>
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div className={cn("h-44 max-w-lg flex-1 rounded-2xl border border-white/[0.06]", SHIMMER_DARK)} />
            <div className={cn("h-40 w-full max-w-md rounded-2xl border border-white/[0.06] lg:max-w-sm", SHIMMER_DARK)} />
          </div>
        </div>
        <span className="sr-only">Opening live view…</span>
      </div>
    </>
  )
}

export function PreferencesSkeleton() {
  return (
    <>
      <style>{`@keyframes shimmer { 100% { transform: translateX(100%); } }`}</style>
      <div
        className="mx-auto flex w-full max-w-5xl flex-col gap-12 pb-28"
        role="status"
        aria-busy="true"
        aria-label="Loading preferences"
      >
        <div className="space-y-4">
          <div className={cn("h-3 w-24 rounded-full border border-[color:var(--haven-line-strong)]", SHIMMER_LIGHT)} />
          <div className={cn("h-12 max-w-md rounded-xl border border-[color:var(--haven-line-strong)]", SHIMMER_LIGHT)} />
          <div className={cn("h-16 max-w-2xl rounded-xl border border-[color:var(--haven-line-strong)]", SHIMMER_LIGHT)} />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className={cn("h-32 rounded-2xl border border-[color:var(--haven-line-strong)]", SHIMMER_LIGHT)} />
          <div className={cn("h-32 rounded-2xl border border-[color:var(--haven-line-strong)]", SHIMMER_LIGHT)} />
        </div>
        <div className="grid gap-5 lg:grid-cols-2 lg:gap-6">
          {Array.from({ length: 4 }).map((_, i) => (
            <div
              key={i}
              className={cn(
                "h-72 rounded-[1.4rem] border border-[color:var(--haven-line-strong)] shadow-[var(--haven-shadow-card)]",
                SHIMMER_LIGHT,
              )}
            />
          ))}
        </div>
        <span className="sr-only">Loading preferences…</span>
      </div>
    </>
  )
}
