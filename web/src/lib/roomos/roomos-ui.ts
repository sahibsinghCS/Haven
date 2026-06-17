import { cn } from "@/lib/utils"
import type { KnownRoomStateId, RoomStateId } from "@/types/roomos"

/**
 * Shared Haven surface recipes (hybrid system).
 * Live = cinematic dark glass; Preferences = warm pearl panels (matching landing).
 */
export const roomosUi = {
  /** Floating panels over the live video stage */
  liveOverlayGlass:
    "rounded-[1.35rem] border border-white/[0.12] bg-zinc-950/84 shadow-[0_28px_80px_-20px_rgba(0,0,0,0.74),inset_0_1px_0_0_rgba(255,255,255,0.075),inset_0_-1px_0_rgba(255,255,255,0.035)] backdrop-blur-2xl supports-[backdrop-filter]:bg-zinc-950/66 ring-1 ring-white/[0.035]",
  /** Compact status / trust chips on Live */
  liveStatusPill:
    "rounded-full border border-white/[0.12] bg-zinc-950/74 text-xs font-medium text-zinc-100 shadow-[0_10px_28px_-14px_rgba(0,0,0,0.68),inset_0_1px_0_rgba(255,255,255,0.06)] backdrop-blur-xl supports-[backdrop-filter]:bg-zinc-950/55 ring-1 ring-white/[0.025]",
  /** Live HUD over full-bleed video: glass with modest see-through */
  liveOverlayGlassTranslucent:
    "rounded-[1.35rem] border border-white/[0.12] bg-zinc-950/82 shadow-[0_28px_80px_-20px_rgba(0,0,0,0.68),inset_0_1px_0_0_rgba(255,255,255,0.07)] backdrop-blur-2xl supports-[backdrop-filter]:bg-zinc-950/72 ring-1 ring-white/[0.06]",
  liveStatusPillTranslucent:
    "rounded-full border border-white/[0.12] bg-zinc-950/76 text-xs font-medium text-zinc-100 shadow-[0_10px_28px_-14px_rgba(0,0,0,0.58),inset_0_1px_0_rgba(255,255,255,0.06)] backdrop-blur-xl supports-[backdrop-filter]:bg-zinc-950/64 ring-1 ring-white/[0.05]",
  /** Preferences: informational callouts, notes */
  prefsCallout:
    "rounded-2xl border border-[color:var(--haven-line-strong)] bg-[color-mix(in_oklab,#fffefb_82%,transparent)] text-[color:var(--haven-muted)] shadow-[var(--haven-shadow-card)] backdrop-blur-sm",
  /** Preferences: preset choice tiles (base) */
  prefsPresetCard:
    "rounded-[1.35rem] border border-[color:var(--haven-line-strong)] bg-[color-mix(in_oklab,#fffefb_92%,transparent)] text-left shadow-[var(--haven-shadow-card)] backdrop-blur-sm transition-[border-color,box-shadow,background-color,transform] duration-300 ease-out",
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
 /** Primary CTA on light Haven pages. overrides shadcn dark `default` variant. */
  havenPrimaryBtn:
    "!border-0 !bg-teal-800 !text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.22),0_10px_22px_-10px_rgba(15,118,110,0.65)] hover:!bg-teal-900 hover:!text-white dark:!bg-teal-800 dark:!text-white dark:hover:!bg-teal-900",
  havenOutlineBtn:
    "border-stone-300/90 bg-white/90 text-stone-800 shadow-sm hover:bg-white hover:text-stone-900 dark:border-stone-400/40 dark:bg-white/95 dark:text-stone-900",
  /** Page section rhythm */
  pageEnter: "haven-enter",
  pageEnterStagger1: "haven-enter haven-enter-delay-1",
  pageEnterStagger2: "haven-enter haven-enter-delay-2",
  /** Dense metadata row (live HUD, teaching stats) */
  metaRow:
    "flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5 text-[11px] leading-snug",
  metaLabel: "font-semibold uppercase tracking-[0.12em] text-[color:var(--haven-faint)]",
  metaValue: "font-medium tabular-nums text-[color:var(--haven-ink-soft)]",
} as const

/** Left accent: visible on light preference cards */
const PREFERENCE_ACCENT_LEFT: Record<KnownRoomStateId, string> = {
  sleep: "before:bg-[linear-gradient(180deg,rgba(99,102,241,0.85)_0%,rgba(99,102,241,0.18)_100%)]",
  work: "before:bg-[linear-gradient(180deg,rgba(14,165,233,0.85)_0%,rgba(14,165,233,0.18)_100%)]",
  relaxing:
    "before:bg-[linear-gradient(180deg,rgba(20,184,166,0.85)_0%,rgba(20,184,166,0.18)_100%)]",
  away: "before:bg-[linear-gradient(180deg,rgba(120,113,108,0.7)_0%,rgba(120,113,108,0.16)_100%)]",
}

/** Generic warm accent for user-created moods. */
const PREFERENCE_ACCENT_LEFT_CUSTOM =
  "before:bg-[linear-gradient(180deg,rgba(217,119,6,0.8)_0%,rgba(217,119,6,0.16)_100%)]"

export function preferenceCardShell(stateId: RoomStateId) {
  const accent =
    stateId in PREFERENCE_ACCENT_LEFT
      ? PREFERENCE_ACCENT_LEFT[stateId as KnownRoomStateId]
      : PREFERENCE_ACCENT_LEFT_CUSTOM
  return cn(
    "relative isolate rounded-[1.55rem] border border-[color:var(--haven-line-strong)] bg-[linear-gradient(168deg,rgba(255,254,251,1)_0%,rgba(252,249,243,0.96)_58%,rgba(245,239,228,0.92)_100%)]",
    "px-5 py-5 sm:px-6 sm:py-6",
    "shadow-[var(--haven-shadow-card)]",
    "ring-1 ring-[color:var(--haven-edge-light)]",
    "before:pointer-events-none before:absolute before:left-0 before:top-5 before:bottom-5 before:w-[3px] before:rounded-full",
    accent,
    "focus-within:ring-2 focus-within:ring-teal-700/30 focus-within:ring-offset-2 focus-within:ring-offset-[color:var(--haven-canvas,#f7f4ee)]",
    "transition-shadow duration-300 ease-out hover:shadow-[var(--haven-shadow-float)]",
  )
}
