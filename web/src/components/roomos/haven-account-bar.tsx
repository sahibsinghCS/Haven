"use client"

import { useQuery } from "@tanstack/react-query"
import { LogOut, User } from "lucide-react"
import { useRouter } from "next/navigation"

import { useHavenAuth } from "@/components/auth/haven-auth-provider"
import { fetchCloudStatus } from "@/lib/roomos/api-client"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { roomosUi } from "@/lib/roomos/roomos-ui"

export function HavenAccountBar() {
  const { enabled, user, signOut, loading } = useHavenAuth()
  const router = useRouter()

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
          "border-amber-500/25 bg-amber-50/90 px-5 py-4 text-[13px] text-amber-950",
        )}
      >
        Cloud accounts are off — add Supabase URL and anon key to <span className="font-mono">web/.env.local</span>.
      </section>
    )
  }

  if (loading) return null

  return (
    <section
      className={cn(
        roomosUi.prefsCallout,
        "flex flex-wrap items-center justify-between gap-4 border-teal-800/20 bg-[color-mix(in_oklab,#fffefb_90%,#e8f4f2_12%)] px-5 py-4",
      )}
    >
      <div className="flex items-start gap-3">
        <User className="mt-0.5 size-5 shrink-0 text-teal-800" aria-hidden />
        <div>
          <p className="text-[14px] font-semibold text-[color:var(--haven-ink)]">Your account</p>
          <p className="text-[13px] text-[color:var(--haven-muted)]">
            {user?.email ?? "Not signed in"}
          </p>
          {cloudQuery.data?.message ? (
            <p className="mt-1 text-[12px] text-[color:var(--haven-muted)]">{cloudQuery.data.message}</p>
          ) : null}
        </div>
      </div>
      {user ? (
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="gap-2"
          onClick={async () => {
            await signOut()
            router.replace("/login")
          }}
        >
          <LogOut className="size-4" aria-hidden />
          Sign out
        </Button>
      ) : null}
    </section>
  )
}
