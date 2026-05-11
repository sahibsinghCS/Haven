"use client"

import { useEffect } from "react"

import { markUserHasOpenedApp } from "@/lib/roomos/landing-app-entry"

/** Call once when user enters an in-app surface so marketing nav can reveal Preferences. */
export function MarkAppEntry() {
  useEffect(() => {
    markUserHasOpenedApp()
  }, [])
  return null
}
