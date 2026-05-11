import { cn } from "@/lib/utils"
import type { RoomStateId } from "@/types/roomos"

/**
 * Shared Haven surface recipes — hybrid system:
 * Live = cinematic dark glass; Preferences = lighter editorial panels.
 */
export const roomosUi = {
  /** Floating panels over the live video stage */
  liveOverlayGlass:
    "rounded-2xl border border-white/[0.11] bg-zinc-900/84 shadow-[0_26px_72px_-18px_rgba(0,0,0,0.72),inset_0_1px_0_0_rgba(255,255,255,0.06)] backdrop-blur-2xl supports-[backdrop-filter]:bg-zinc-900/72",
  /** Compact status / trust chips on Live */
  liveStatusPill:
    "rounded-full border border-white/[0.11] bg-zinc-900/78 text-xs font-medium text-zinc-200 shadow-sm backdrop-blur-xl supports-[backdrop-filter]:bg-zinc-900/64",
  /** Preferences: informational callouts, notes */
  prefsCallout:
    "rounded-2xl border border-zinc-200/90 bg-zinc-50/95 text-zinc-600 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.85)] backdrop-blur-sm",
  /** Preferences: preset choice tiles (base) */
  prefsPresetCard:
    "rounded-2xl border border-zinc-200/88 bg-white text-left shadow-[0_1px_0_0_rgba(255,255,255,1)_inset,0_14px_44px_-30px_rgba(15,23,42,0.14)] backdrop-blur-sm transition-[border-color,box-shadow,background-color] duration-200",
  /** Preferences: sticky save bar */
  prefsStickyBar:
    "rounded-2xl border border-zinc-200/90 bg-white/96 text-zinc-700 shadow-[0_20px_56px_-24px_rgba(15,23,42,0.16),inset_0_1px_0_0_rgba(255,255,255,1)] backdrop-blur-md",
  /** Preferences: compact error / alert panel */
  prefsAlertPanel:
    "rounded-2xl border border-rose-200/90 bg-rose-50/95 text-rose-950 shadow-sm backdrop-blur-sm",
  /** Focus rings — Live (dark offset) */
  focusRingDark:
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/45 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950",
  /** Focus rings — Preferences (light offset) */
  focusRingLight:
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-600/40 focus-visible:ring-offset-2 focus-visible:ring-offset-white",
} as const

/** Left accent — visible on light preference cards */
const PREFERENCE_ACCENT_LEFT: Record<RoomStateId, string> = {
  sleep: "border-l-[3px] border-l-indigo-500/75",
  gaming: "border-l-[3px] border-l-violet-500/70",
  work: "border-l-[3px] border-l-sky-500/75",
  relaxing: "border-l-[3px] border-l-teal-500/72",
  away: "border-l-[3px] border-l-zinc-400/80",
}

export function preferenceCardShell(stateId: RoomStateId) {
  return cn(
    "rounded-2xl border border-zinc-200/92 bg-white pl-5 pr-5 py-5 shadow-[0_1px_0_0_rgba(255,255,255,1)_inset,0_24px_56px_-32px_rgba(15,23,42,0.12)] sm:pl-6 sm:pr-6 sm:py-6",
    PREFERENCE_ACCENT_LEFT[stateId],
    "focus-within:ring-2 focus-within:ring-cyan-500/35 focus-within:ring-offset-2 focus-within:ring-offset-zinc-100",
  )
}
