export {
  LiveStageSkeleton,
  PreferencesSkeleton,
} from "@/components/roomos/roomos-loading-states"

import { roomosUi } from "@/lib/roomos/roomos-ui"
import { cn } from "@/lib/utils"

const SHIMMER_LIGHT =
  "haven-shimmer bg-[linear-gradient(168deg,rgba(255,253,250,0.95)_0%,rgba(245,239,228,0.85)_100%)] motion-reduce:before:hidden"

/** Pearl dashboard route skeleton (preferences, rhythm, connections, review). */
export function HavenDashboardSkeleton() {
  return (
    <div
      className="mx-auto flex w-full max-w-5xl flex-col gap-10 pb-28"
      role="status"
      aria-busy="true"
      aria-label="Loading page"
    >
      <div className={cn(roomosUi.pageEnter, "space-y-3")}>
        <div className={cn("h-2.5 w-28 rounded-full border border-[color:var(--haven-line-strong)]", SHIMMER_LIGHT)} />
        <div className={cn("h-10 max-w-sm rounded-xl border border-[color:var(--haven-line-strong)]", SHIMMER_LIGHT)} />
        <div className={cn("h-16 max-w-2xl rounded-2xl border border-[color:var(--haven-line-strong)]", SHIMMER_LIGHT)} />
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div
            key={`stat-${i}`}
            className={cn(
              "h-28 rounded-[1.35rem] border border-[color:var(--haven-line-strong)] shadow-[var(--haven-shadow-card)]",
              SHIMMER_LIGHT,
            )}
          />
        ))}
      </div>
      <div className="grid gap-5 lg:grid-cols-2">
        {Array.from({ length: 2 }).map((_, i) => (
          <div key={`card-${i}`} className="space-y-3 rounded-[1.35rem] border border-[color:var(--haven-line-strong)] p-5 shadow-[var(--haven-shadow-card)]">
            <div className={cn("h-4 w-24 rounded-full border border-[color:var(--haven-line-strong)]", SHIMMER_LIGHT)} />
            <div className={cn("h-8 w-40 rounded-lg border border-[color:var(--haven-line-strong)]", SHIMMER_LIGHT)} />
            <div className={cn("h-24 rounded-xl border border-[color:var(--haven-line-strong)]", SHIMMER_LIGHT)} />
          </div>
        ))}
      </div>
      <span className="sr-only">Loading…</span>
    </div>
  )
}

export { AuthFormSkeleton as HavenAuthSkeleton } from "@/components/auth/auth-form-skeleton"
