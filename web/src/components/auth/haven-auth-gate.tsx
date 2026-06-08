"use client"

import { useEffect } from "react"
import { usePathname, useRouter } from "next/navigation"

import { useHavenAuth } from "@/components/auth/haven-auth-provider"

export function HavenAuthGate({ children }: { children: React.ReactNode }) {
  const { enabled, loading, session } = useHavenAuth()
  const router = useRouter()
  const pathname = usePathname()

  useEffect(() => {
    if (!enabled || loading) return
    if (!session && pathname !== "/login") {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`)
    }
  }, [enabled, loading, session, pathname, router])

  if (!enabled) return <>{children}</>

  if (loading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center text-[14px] text-[color:var(--haven-muted)]">
        Loading your account…
      </div>
    )
  }

  if (!session) return null

  return <>{children}</>
}
