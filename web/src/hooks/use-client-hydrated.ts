"use client"

import { useEffect, useState } from "react"

/** True after the first client paint — use to gate browser-only state (localStorage, etc.). */
export function useClientHydrated() {
  const [hydrated, setHydrated] = useState(false)
  useEffect(() => {
    setHydrated(true)
  }, [])
  return hydrated
}
