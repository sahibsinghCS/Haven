"use client"

import { useQuery } from "@tanstack/react-query"
import { Cloud, LogOut } from "lucide-react"

import { signOutAction } from "@/app/(auth)/actions"
import { useHavenAuth } from "@/components/auth/haven-auth-provider"
import { fetchCloudStatus } from "@/lib/roomos/api-client"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { roomosUi } from "@/lib/roomos/roomos-ui"

function userInitial(email: string | undefined): string {
  const ch = email?.trim().charAt(0).toUpperCase()
  return ch && /[A-Z0-9]/i.test(ch) ? ch : "?"
}

export function HavenAccountBar() {
  const { enabled, user, loading } = useHavenAuth()

  const cloudQuery = useQuery({
    queryKey: ["haven", "cloud-status", user?.id],
    queryFn: () => fetchCloudStatus(),
    enabled: enabled && !!user,
    staleTime: 60_000,
  })

  if (!enabled) {
    return (
      <section
        className={cn(
          roomosUi.prefsCallout,
          "border-amber-500/25 bg-amber-50/90 px-5 py-4 text-[13px] leading-relaxed text-amber-950",
        )}
      >
        <strong className="font-semibold">Local mode.</strong> Cloud sign in is off. Settings stay on
        this device. Add Supabase keys to <span className="font-mono">web/.env.local</span> to enable
        accounts.
      </section>
    )
  }

  if (loading) {
    return (
      <section
        className={cn(
          roomosUi.prefsCallout,
          "flex items-center gap-3 border-[color:var(--haven-line-strong)] px-5 py-4",
        )}
        aria-busy="true"
        aria-label="Loading account"
      >
        <div className="haven-shimmer size-10 shrink-0 rounded-full border border-[color:var(--haven-line-strong)]" />
        <div className="min-w-0 flex-1 space-y-2">
          <div className="haven-shimmer h-3 w-28 rounded-md border border-[color:var(--haven-line-strong)]" />
          <div className="haven-shimmer h-3 w-40 max-w-full rounded-md border border-[color:var(--haven-line-strong)]" />
        </div>
      </section>
    )
  }

  if (!user) return null

  return (
    <section
      className={cn(
        roomosUi.prefsCallout,
        "flex flex-wrap items-center justify-between gap-4 border-teal-800/20 bg-[color-mix(in_oklab,#fffefb_90%,#e8f4f2_12%)] px-5 py-4",
      )}
    >
      <div className="flex items-start gap-3">
        <span
          className="flex size-10 shrink-0 items-center justify-center rounded-full bg-teal-800 text-[14px] font-semibold text-white"
          aria-hidden
        >
          {userInitial(user.email)}
        </span>
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-[14px] font-semibold text-[color:var(--haven-ink)]">Your account</p>
            <span className="inline-flex items-center gap-1 rounded-full border border-teal-700/25 bg-teal-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-teal-900">
              <Cloud className="size-3" aria-hidden />
              Cloud sync on
            </span>
          </div>
          <p className="text-[13px] text-[color:var(--haven-muted)]">{user.email}</p>
          {cloudQuery.data?.message ? (
            <p className="mt-1 text-[12px] text-[color:var(--haven-muted)]">{cloudQuery.data.message}</p>
          ) : null}
        </div>
      </div>
      <form action={signOutAction}>
        <Button type="submit" variant="outline" size="sm" className="gap-2">
          <LogOut className="size-4" aria-hidden />
          Sign out
        </Button>
      </form>
    </section>
  )
}
