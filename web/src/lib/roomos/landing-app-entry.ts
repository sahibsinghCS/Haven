/** Persists after user opens any in-app route (/live, /preferences). Used by marketing nav. */

export const LANDING_APP_ENTRY_KEY = "roomos_has_opened_app" as const

export function markUserHasOpenedApp(): void {
  if (typeof window === "undefined") return
  try {
    window.localStorage.setItem(LANDING_APP_ENTRY_KEY, "1")
  } catch {
    /* quota / private mode */
  }
}

export function getUserHasOpenedApp(): boolean {
  if (typeof window === "undefined") return false
  try {
    return window.localStorage.getItem(LANDING_APP_ENTRY_KEY) === "1"
  } catch {
    return false
  }
}
