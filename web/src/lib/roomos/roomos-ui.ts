import { cn } from "@/lib/utils"
import type { RoomStateId } from "@/types/roomos"

/**
 * Shared Haven surface recipes (hybrid system).
 * Live = cinematic dark glass; Preferences = warm pearl panels (matching landing).
 */
export const roomosUi = {
  /** Floating panels over the live video stage */
  liveOverlayGlass:
    "rounded-2xl border border-white/[0.11] bg-zinc-950/82 shadow-[0_26px_72px_-18px_rgba(0,0,0,0.72),inset_0_1px_0_0_rgba(255,255,255,0.07)] backdrop-blur-2xl supports-[backdrop-filter]:bg-zinc-950/68",
  /** Compact status / trust chips on Live */
  liveStatusPill:
    "rounded-full border border-white/[0.11] bg-zinc-950/72 text-xs font-medium text-zinc-100 shadow-[0_8px_22px_-12px_rgba(0,0,0,0.65),inset_0_1px_0_rgba(255,255,255,0.05)] backdrop-blur-xl supports-[backdrop-filter]:bg-zinc-950/55",
  /** Preferences: informational callouts, notes */
  prefsCallout:
    "rounded-2xl border border-[color:var(--haven-line-strong)] bg-[color-mix(in_oklab,#fffefb_82%,transparent)] text-[color:var(--haven-muted)] shadow-[var(--haven-shadow-card)] backdrop-blur-sm",
  /** Preferences: preset choice tiles (base) */
  prefsPresetCard:
    "rounded-2xl border border-[color:var(--haven-line-strong)] bg-[color-mix(in_oklab,#fffefb_92%,transparent)] text-left shadow-[var(--haven-shadow-card)] backdrop-blur-sm transition-[border-color,box-shadow,background-color,transform] duration-300 ease-out",
  /** Preferences: sticky save bar */
  prefsStickyBar:
    "rounded-2xl border border-[color:var(--haven-line-strong)] bg-[color-mix(in_oklab,#fffefb_94%,transparent)] text-[color:var(--haven-muted)] shadow-[var(--haven-shadow-float)] backdrop-blur-xl supports-[backdrop-filter]:bg-[color-mix(in_oklab,#fffefb_82%,transparent)] ring-1 ring-[color:var(--haven-edge-light)]",
  /** Preferences: compact error / alert panel */
  prefsAlertPanel:
    "rounded-2xl border border-rose-300/80 bg-rose-50/95 text-rose-950 shadow-[0_18px_42px_-22px_rgba(159,18,57,0.22)] backdrop-blur-sm",
  /** Focus rings: Live (dark offset) */
  focusRingDark:
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/45 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950",
  /** Focus rings: Preferences (light offset) */
  focusRingLight:
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700/40 focus-visible:ring-offset-2 focus-visible:ring-offset-[color:var(--haven-canvas,#f7f4ee)]",
} as const

/** Left accent: visible on light preference cards */
const PREFERENCE_ACCENT_LEFT: Record<RoomStateId, string> = {
  sleep: "before:bg-[linear-gradient(180deg,rgba(99,102,241,0.85)_0%,rgba(99,102,241,0.18)_100%)]",
  gaming:
    "before:bg-[linear-gradient(180deg,rgba(139,92,246,0.85)_0%,rgba(139,92,246,0.18)_100%)]",
  work: "before:bg-[linear-gradient(180deg,rgba(14,165,233,0.85)_0%,rgba(14,165,233,0.18)_100%)]",
  relaxing:
    "before:bg-[linear-gradient(180deg,rgba(20,184,166,0.85)_0%,rgba(20,184,166,0.18)_100%)]",
  away: "before:bg-[linear-gradient(180deg,rgba(120,113,108,0.7)_0%,rgba(120,113,108,0.16)_100%)]",
}

export function preferenceCardShell(stateId: RoomStateId) {
  return cn(
    "relative isolate rounded-[1.4rem] border border-[color:var(--haven-line-strong)] bg-[linear-gradient(168deg,rgba(255,254,251,1)_0%,rgba(252,249,243,0.96)_60%,rgba(245,239,228,0.92)_100%)]",
    "px-5 py-5 sm:px-6 sm:py-6",
    "shadow-[var(--haven-shadow-card)]",
    "ring-1 ring-[color:var(--haven-edge-light)]",
    "before:pointer-events-none before:absolute before:left-0 before:top-5 before:bottom-5 before:w-[3px] before:rounded-full",
    PREFERENCE_ACCENT_LEFT[stateId],
    "focus-within:ring-2 focus-within:ring-teal-700/30 focus-within:ring-offset-2 focus-within:ring-offset-[color:var(--haven-canvas,#f7f4ee)]",
    "transition-shadow duration-300 ease-out hover:shadow-[var(--haven-shadow-float)]",
  )
}
