/** Client-side setup progress (local-first; not synced). */

const SETUP_COMPLETE_KEY = "haven.setup.complete.v1"
const SETUP_STEP_KEY = "haven.setup.step.v1"

export type SetupWizardStep = "room" | "devices" | "live"

export function isSetupMarkedComplete(): boolean {
  if (typeof window === "undefined") return false
  try {
    return window.localStorage.getItem(SETUP_COMPLETE_KEY) === "1"
  } catch {
    return false
  }
}

export function markSetupComplete(): void {
  if (typeof window === "undefined") return
  try {
    window.localStorage.setItem(SETUP_COMPLETE_KEY, "1")
  } catch {
    /* private mode */
  }
}

export function clearSetupComplete(): void {
  if (typeof window === "undefined") return
  try {
    window.localStorage.removeItem(SETUP_COMPLETE_KEY)
    window.localStorage.removeItem(SETUP_STEP_KEY)
  } catch {
    /* ignore */
  }
}

export function loadSetupStep(): SetupWizardStep | null {
  if (typeof window === "undefined") return null
  try {
    const v = window.localStorage.getItem(SETUP_STEP_KEY)
    if (v === "health") return "devices"
    if (v === "room" || v === "devices" || v === "live") return v
    return null
  } catch {
    return null
  }
}

export function saveSetupStep(step: SetupWizardStep): void {
  if (typeof window === "undefined") return
  try {
    window.localStorage.setItem(SETUP_STEP_KEY, step)
  } catch {
    /* ignore */
  }
}
