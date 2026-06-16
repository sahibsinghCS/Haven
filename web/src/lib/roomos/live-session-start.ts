/** Set when the user clicks Get Started / Open live view. consumed on /live mount. */

export const LIVE_START_INTENT_KEY = "roomos_live_start_intent" as const

export function markLiveStartIntent(): void {
  if (typeof window === "undefined") return
  try {
    window.sessionStorage.setItem(LIVE_START_INTENT_KEY, "1")
  } catch {
    /* private mode */
  }
}

export function consumeLiveStartIntent(): boolean {
  if (typeof window === "undefined") return false
  try {
    const v = window.sessionStorage.getItem(LIVE_START_INTENT_KEY)
    if (v !== "1") return false
    window.sessionStorage.removeItem(LIVE_START_INTENT_KEY)
    return true
  } catch {
    return false
  }
}

export function hasLiveStartQuery(search: string): boolean {
  try {
    return new URLSearchParams(search).get("start") === "1"
  } catch {
    return false
  }
}
