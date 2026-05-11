"use client"

import { cn } from "@/lib/utils"

export function LiveStageSkeleton() {
  return (
    <div
      className="flex min-h-[calc(100dvh-3.25rem)] flex-1 flex-col overflow-hidden rounded-none border border-white/[0.06] bg-zinc-900/85 sm:min-h-[calc(100dvh-3.5rem)]"
      role="status"
      aria-busy="true"
      aria-label="Loading live view"
    >
      <div className="relative flex flex-1 flex-col justify-between gap-8 bg-gradient-to-b from-zinc-900/60 to-zinc-950/90 p-4 sm:p-6 lg:p-8">
        <div className="flex justify-between gap-3">
          <div className="h-8 w-36 animate-pulse rounded-full bg-zinc-700/55 motion-reduce:animate-none" />
          <div className="h-8 w-44 animate-pulse rounded-full bg-zinc-700/55 motion-reduce:animate-none" />
        </div>
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="h-40 max-w-lg flex-1 animate-pulse rounded-2xl bg-zinc-800/50 motion-reduce:animate-none" />
          <div className="h-36 w-full max-w-md animate-pulse rounded-2xl bg-zinc-800/45 motion-reduce:animate-none lg:max-w-sm" />
        </div>
      </div>
      <span className="sr-only">Opening live view…</span>
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
      <div className="space-y-3">
        <div className="h-3 w-20 animate-pulse rounded bg-zinc-300/90 motion-reduce:animate-none" />
        <div className="h-10 max-w-md animate-pulse rounded-lg bg-zinc-200/95 motion-reduce:animate-none" />
        <div className="h-16 max-w-2xl animate-pulse rounded-lg bg-zinc-200/80 motion-reduce:animate-none" />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="h-28 animate-pulse rounded-2xl border border-zinc-200/70 bg-white/70 motion-reduce:animate-none" />
        <div className="h-28 animate-pulse rounded-2xl border border-zinc-200/70 bg-white/70 motion-reduce:animate-none" />
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className={cn(
              "h-72 animate-pulse rounded-2xl border border-zinc-200/80 bg-white/80 motion-reduce:animate-none",
            )}
          />
        ))}
      </div>
      <span className="sr-only">Loading preferences…</span>
    </div>
  )
}
