"use client"

import { useEffect } from "react"
import { usePathname } from "next/navigation"
import { motion, useReducedMotion } from "framer-motion"
import Link from "next/link"

import { cn } from "@/lib/utils"
import { ROOM_STATE_ACCENT } from "@/lib/roomos/state-meta"
import { roomosUi } from "@/lib/roomos/roomos-ui"
import { useRoomOsAmbientStore } from "@/stores/roomos-store"

const nav = [
  { href: "/live", label: "Live" },
  { href: "/preferences", label: "Preferences" },
] as const

export function RoomDashboardShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const primaryState = useRoomOsAmbientStore((s) => s.primaryState)
  const isLive = pathname === "/live"
  const reduceMotion = useReducedMotion()

  useEffect(() => {
    if (pathname !== "/live") {
      useRoomOsAmbientStore.getState().setPrimaryState(null)
    }
  }, [pathname])

  const accent = primaryState ? ROOM_STATE_ACCENT[primaryState] : null

  return (
    <div
      className={cn(
        "relative flex min-h-full flex-1 flex-col",
        isLive
          ? "bg-gradient-to-b from-zinc-950 via-zinc-900 to-zinc-950 text-zinc-100"
          : "bg-gradient-to-b from-zinc-100 via-neutral-50 to-zinc-200/90 text-zinc-900",
      )}
    >
      <div
        className={cn(
          "pointer-events-none fixed inset-0 bg-gradient-to-b transition-opacity duration-700",
          isLive ? "opacity-90" : "opacity-100",
          isLive
            ? accent
              ? accent.glow
              : "from-zinc-800/30 via-transparent to-transparent"
            : "from-white/55 via-zinc-100/20 to-transparent",
        )}
        aria-hidden
      />
      {accent && isLive ? (
        <motion.div
          key={primaryState ?? "none"}
          className={cn(
            "pointer-events-none fixed -top-32 left-1/2 h-[380px] w-[min(1100px,100vw)] -translate-x-1/2 rounded-full blur-3xl",
            "bg-gradient-to-r",
            primaryState === "sleep" && "from-indigo-600/18 via-indigo-950/6 to-transparent",
            primaryState === "gaming" &&
              "from-violet-600/14 via-blue-950/8 to-transparent",
            primaryState === "work" && "from-sky-500/12 via-cyan-950/6 to-transparent",
            primaryState === "relaxing" &&
              "from-teal-500/11 via-emerald-950/5 to-transparent",
            primaryState === "away" && "from-zinc-500/10 via-zinc-800/4 to-transparent",
          )}
          initial={{ opacity: 0 }}
          animate={{ opacity: reduceMotion ? 0.18 : 0.3 }}
          transition={{ duration: reduceMotion ? 0.1 : 0.75, ease: "easeOut" }}
          aria-hidden
        />
      ) : null}

      <header
        className={cn(
          "sticky top-0 z-30 border-b backdrop-blur-xl",
          isLive
            ? "border-white/[0.07] bg-zinc-950/58 py-2.5 supports-[backdrop-filter]:bg-zinc-950/48"
            : "border-zinc-200/80 bg-white/78 py-3.5 supports-[backdrop-filter]:bg-white/65 sm:py-4",
        )}
      >
        <div
          className={cn(
            "mx-auto flex w-full items-center justify-between gap-4",
            isLive ? "max-w-none px-4 sm:px-5" : "max-w-6xl px-4 sm:px-6",
          )}
        >
          <div className="flex min-w-0 flex-col gap-0.5">
            <Link
              href="/live"
              className={cn(
                "truncate font-semibold tracking-tight text-base sm:text-lg",
                isLive ? "text-zinc-50" : "text-zinc-900",
                isLive ? roomosUi.focusRingDark : roomosUi.focusRingLight,
                "rounded-md",
              )}
            >
              Haven
            </Link>
            <p
              className={cn(
                "text-[0.6875rem] font-medium tracking-[0.12em] uppercase",
                isLive ? "text-zinc-500" : "text-zinc-500",
              )}
            >
              {isLive ? "Adaptive room intelligence" : "Local · Private · Adaptive"}
            </p>
          </div>
          <nav
            aria-label="Primary"
            className={cn(
              "flex shrink-0 items-center gap-0.5 rounded-xl border p-0.5 sm:gap-1 sm:p-1",
              isLive
                ? "border-white/[0.08] bg-zinc-950/45"
                : "border-zinc-200/90 bg-white/90 shadow-sm",
            )}
          >
            {nav.map((item) => {
              const active = pathname === item.href
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    isLive ? roomosUi.focusRingDark : roomosUi.focusRingLight,
                    "rounded-lg px-2.5 py-1.5 text-sm font-medium transition-colors sm:px-3",
                    isLive
                      ? active
                        ? "bg-white/[0.11] text-zinc-50"
                        : "text-zinc-500 transition-colors duration-200 hover:bg-white/[0.06] hover:text-zinc-200"
                      : active
                        ? "bg-zinc-900 text-white shadow-sm"
                        : "text-zinc-600 transition-colors duration-200 hover:bg-zinc-100 hover:text-zinc-900",
                  )}
                >
                  {item.label}
                </Link>
              )
            })}
          </nav>
        </div>
      </header>

      <main
        className={cn(
          "relative z-10 flex w-full flex-1 flex-col",
          isLive ? "max-w-none min-h-0 p-0" : "mx-auto max-w-6xl min-h-0 px-4 py-8 sm:px-6 sm:py-10",
        )}
      >
        {children}
      </main>
    </div>
  )
}
