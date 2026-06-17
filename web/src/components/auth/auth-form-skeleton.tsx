import { cn } from "@/lib/utils"
import { roomosUi } from "@/lib/roomos/roomos-ui"

const SHIMMER =
  "haven-shimmer bg-[linear-gradient(168deg,rgba(255,253,250,0.95)_0%,rgba(245,239,228,0.85)_100%)] motion-reduce:before:hidden"

export function AuthFormSkeleton() {
  return (
    <div
      className={cn(roomosUi.prefsPresetCard, "w-full max-w-md p-6 sm:p-8")}
      role="status"
      aria-busy="true"
      aria-label="Loading sign in form"
    >
      <div className={cn("h-8 w-40 rounded-lg border border-[color:var(--haven-line-strong)]", SHIMMER)} />
      <div className={cn("mt-3 h-4 w-full max-w-xs rounded-md border border-[color:var(--haven-line-strong)]", SHIMMER)} />
      <div className="mt-8 space-y-4">
        <div className={cn("h-10 rounded-lg border border-[color:var(--haven-line-strong)]", SHIMMER)} />
        <div className={cn("h-10 rounded-lg border border-[color:var(--haven-line-strong)]", SHIMMER)} />
        <div className={cn("h-11 rounded-full border border-[color:var(--haven-line-strong)]", SHIMMER)} />
      </div>
      <span className="sr-only">Loading…</span>
    </div>
  )
}
