"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import { usePathname } from "next/navigation"
import { motion, useReducedMotion } from "framer-motion"
import Link from "next/link"
import { LogOut } from "lucide-react"
import { useQueryClient } from "@tanstack/react-query"

import { signOutAction } from "@/app/(auth)/actions"
import { useHavenAuth } from "@/components/auth/haven-auth-provider"
import { HavenLogoBadge } from "@/components/brand/haven-logo"
import { havenNavIsland } from "@/components/roomos/haven-primitives"
import { LiveCameraSelect } from "@/components/roomos/live-camera-select"
import { LiveSessionBridge } from "@/components/roomos/live-session-bridge"
import { cn } from "@/lib/utils"
import {
  prefetchDashboardCore,
  prefetchDashboardRoute,
} from "@/lib/roomos/dashboard-queries"
import { roomStateAccent } from "@/lib/roomos/state-meta"
import { roomosUi } from "@/lib/roomos/roomos-ui"
import { useRoomOsAmbientStore } from "@/stores/roomos-store"

const nav = [
  { href: "/live", label: "Live" },
  { href: "/review", label: "Review" },
  { href: "/rhythm", label: "Rhythm" },
  { href: "/preferences", label: "Moods", wideLabel: "Moods / Preferences" },
  { href: "/connections", label: "Connections" },
] as const

const BREADCRUMB_LABEL: Record<string, string> = {
  "/review": "Review",
  "/rhythm": "Rhythm",
  "/preferences": "Moods / Preferences",
  "/connections": "Connections",
}

function userInitial(email: string | undefined): string {
  const ch = email?.trim().charAt(0).toUpperCase()
  return ch && /[A-Z0-9]/i.test(ch) ? ch : "?"
}

export function RoomDashboardShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const queryClient = useQueryClient()
  const { user, loading: authLoading, enabled: authEnabled } = useHavenAuth()
  const userId = user?.id ?? null
  const primaryState = useRoomOsAmbientStore((s) => s.primaryState)
  const lastAmbientMood = useRoomOsAmbientStore((s) => s.lastAmbientMood)
  const isLive = pathname === "/live"
  const ambientMood = isLive ? primaryState : lastAmbientMood
  const reduceMotion = useReducedMotion()

  useEffect(() => {
    if (pathname !== "/live") {
      useRoomOsAmbientStore.getState().setPrimaryState(null)
    }
  }, [pathname])

  const accent = primaryState ? roomStateAccent(primaryState) : null

  // Segmented-nav active indicator: measures the active tab and animates
  const navWrapRef = useRef<HTMLDivElement | null>(null)
  const tabRefs = useRef<Record<string, HTMLAnchorElement | null>>({})
  const [indicator, setIndicator] = useState<{ left: number; width: number } | null>(null)
  const activeKey = useMemo(() => nav.find((n) => n.href === pathname)?.href, [pathname])

  useEffect(() => {
    prefetchDashboardCore(queryClient, userId)
  }, [queryClient, userId])

  const prefetchRoute = (href: string) => {
    prefetchDashboardRoute(queryClient, href, userId)
  }

  useEffect(() => {
    const measure = () => {
      const wrap = navWrapRef.current
      const el = activeKey ? tabRefs.current[activeKey] : null
      if (!wrap || !el) {
        setIndicator(null)
        return
      }
      const wrapRect = wrap.getBoundingClientRect()
      const tabRect = el.getBoundingClientRect()
      setIndicator({
        left: tabRect.left - wrapRect.left,
        width: tabRect.width,
      })
    }
    measure()
    window.addEventListener("resize", measure)
    return () => window.removeEventListener("resize", measure)
  }, [activeKey])

  const breadcrumb = !isLive ? BREADCRUMB_LABEL[pathname] : null
  const moodAccent = ambientMood ? roomStateAccent(ambientMood) : null

  useEffect(() => {
    document.documentElement.classList.toggle("dark", isLive)
    return () => {
      document.documentElement.classList.remove("dark")
    }
  }, [isLive])

  return (
    <div
      className={cn(
        "relative flex flex-1 flex-col overflow-x-clip",
        isLive
          ? "dark h-svh max-h-svh overflow-hidden bg-gradient-to-b from-zinc-950 via-zinc-900 to-zinc-950 text-zinc-100"
          : "haven-app haven-grain surface-grain surface-pearl-bg min-h-full text-[color:var(--haven-ink)]",
      )}
      data-haven-mood={!isLive && ambientMood ? ambientMood : undefined}
    >
      <div
        className={cn(
          "pointer-events-none fixed inset-0 bg-gradient-to-b transition-opacity duration-700",
          isLive ? "opacity-90" : "opacity-100",
          isLive
            ? accent
              ? accent.glow
              : "from-zinc-800/30 via-transparent to-transparent"
            : "from-white/40 via-transparent to-transparent",
        )}
        aria-hidden
      />
      {!isLive && ambientMood ? (
        <div
          className="pointer-events-none fixed -top-28 left-1/2 z-0 h-[min(380px,55vh)] w-[min(960px,98vw)] -translate-x-1/2 rounded-full blur-3xl transition-all duration-500 ease-out"
          style={{
            background: `radial-gradient(ellipse, var(--haven-ambient) 0%, transparent 70%)`,
            opacity: reduceMotion ? 0.35 : 0.55,
          }}
          aria-hidden
        />
      ) : null}
      {accent && isLive ? (
        <motion.div
          key={primaryState ?? "none"}
          className={cn(
            "pointer-events-none fixed -top-32 left-1/2 h-[380px] w-[min(1100px,100vw)] -translate-x-1/2 rounded-full blur-3xl",
            "bg-gradient-to-r",
            primaryState === "sleep" && "from-indigo-600/18 via-indigo-950/6 to-transparent",
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
          "sticky top-0 z-30 backdrop-blur-2xl",
          isLive
            ? "border-b border-white/[0.07] bg-zinc-950/55 py-2.5 supports-[backdrop-filter]:bg-zinc-950/44"
            : "py-3 sm:py-3.5",
        )}
      >
        {!isLive ? (
          <>
            <div
              aria-hidden
              className="pointer-events-none absolute inset-x-0 top-0 h-full bg-[linear-gradient(180deg,color-mix(in_oklab,#fffefb_85%,transparent)_0%,color-mix(in_oklab,#fdfcfa_55%,transparent)_100%)] supports-[backdrop-filter]:bg-[linear-gradient(180deg,color-mix(in_oklab,#fffefb_72%,transparent)_0%,color-mix(in_oklab,#fdfcfa_42%,transparent)_100%)]"
            />
            <div
              aria-hidden
              className="pointer-events-none absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-stone-900/12 to-transparent"
            />
          </>
        ) : null}
        <div
          className={cn(
            "relative mx-auto grid w-full grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-2 sm:gap-3",
            isLive ? "max-w-none px-4 sm:px-5" : "max-w-6xl px-4 sm:px-6",
          )}
        >
          <div className="flex min-w-0 justify-start">
          <Link
            href="/"
            aria-label="Haven home"
            className={cn(
              "group inline-flex shrink-0 items-center gap-2 rounded-xl py-1 pl-1 pr-2",
              "transition-[background-color] duration-200 ease-out",
              isLive
                ? cn(roomosUi.focusRingDark, "hover:bg-white/[0.04]")
                : cn(roomosUi.focusRingLight, "hover:bg-stone-900/[0.04]"),
            )}
          >
            <HavenLogoBadge variant="mark" size="sm" priority badgeClassName="size-9 shrink-0 px-1.5" />
            <span className="hidden min-w-0 leading-none lg:block">
              <span
                className={cn(
                  "mt-[3px] block truncate text-[10px] font-semibold uppercase tracking-[0.26em]",
                  isLive ? "text-zinc-500" : "text-[color:var(--haven-faint)]",
                )}
              >
                {isLive ? "Live demo" : "Local, private, adaptive"}
              </span>
            </span>
          </Link>
          </div>

          <nav
            ref={navWrapRef}
            aria-label="Primary"
            className={cn(
              "relative flex w-max max-w-full shrink-0 items-center justify-center gap-0.5 p-0.5 sm:gap-0.5 sm:p-1",
              isLive
                ? "rounded-full border border-white/[0.1] bg-zinc-950/58 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.05),0_12px_40px_-18px_rgba(0,0,0,0.65)] supports-[backdrop-filter]:bg-zinc-950/46"
                : havenNavIsland,
            )}
          >
            {indicator ? (
              <motion.span
                aria-hidden
                className={cn(
                  "absolute top-0.5 bottom-0.5 sm:top-1 sm:bottom-1 rounded-full",
                  isLive
                    ? "bg-white/[0.11] shadow-[inset_0_1px_0_0_rgba(255,255,255,0.06)]"
                    : "bg-[linear-gradient(168deg,#1d1c1a_0%,#0d0c0b_100%)] shadow-[inset_0_1px_0_rgba(255,255,255,0.18),0_8px_22px_-10px_rgba(0,0,0,0.45)]",
                )}
                initial={false}
                animate={{ left: indicator.left, width: indicator.width }}
                transition={
                  reduceMotion
                    ? { duration: 0 }
                    : { type: "spring", stiffness: 380, damping: 32 }
                }
              />
            ) : null}
            {nav.map((item) => {
              const active = pathname === item.href
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  ref={(el) => {
                    tabRefs.current[item.href] = el
                  }}
                  onMouseEnter={() => prefetchRoute(item.href)}
                  onFocus={() => prefetchRoute(item.href)}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "relative z-[1] whitespace-nowrap rounded-full px-2.5 py-2 text-[11px] font-semibold tracking-tight transition-colors duration-200 sm:px-3 sm:text-[12px] lg:px-3.5 lg:text-[13px] min-h-9",
                    isLive ? roomosUi.focusRingDark : roomosUi.focusRingLight,
                    isLive
                      ? active
                        ? "text-zinc-50"
                        : "text-zinc-400 hover:text-zinc-200"
                      : active
                        ? "text-white"
                        : "text-[color:var(--haven-muted)] hover:text-[color:var(--haven-ink)]",
                  )}
                >
                  {"wideLabel" in item && item.wideLabel ? (
                    <>
                      <span className="xl:hidden">{item.label}</span>
                      <span className="hidden xl:inline">{item.wideLabel}</span>
                    </>
                  ) : (
                    item.label
                  )}
                </Link>
              )
            })}
          </nav>

          <div className="flex min-w-0 items-center justify-end gap-1.5 sm:gap-2">
          {authEnabled ? (
            authLoading ? (
              <div
                className={cn(
                  "h-9 w-24 shrink-0 rounded-full border",
                  isLive ? "border-white/10 bg-white/[0.04]" : "border-stone-900/10 bg-white/60",
                  "haven-shimmer",
                )}
                aria-hidden
              />
            ) : user ? (
              <div
                className={cn(
                  "flex shrink-0 items-center gap-1.5 rounded-full border py-0.5 pl-1 pr-0.5 sm:gap-2 sm:pl-1.5",
                  isLive
                    ? "border-white/10 bg-white/[0.04]"
                    : "border-[color:var(--haven-line-strong)] bg-[color-mix(in_oklab,#fffefb_88%,transparent)] shadow-[var(--haven-shadow-card)]",
                )}
              >
                <span
                  className={cn(
                    "hidden max-w-[8rem] truncate text-[12px] font-medium xl:inline",
                    isLive ? "text-zinc-400" : "text-[color:var(--haven-muted)]",
                  )}
                  title={user.email ?? undefined}
                >
                  {user.email}
                </span>
                <span
                  className={cn(
                    "flex size-9 shrink-0 items-center justify-center rounded-full text-[12px] font-semibold ring-2 ring-offset-1",
                    isLive
                      ? "bg-white/10 text-zinc-100 ring-white/20 ring-offset-zinc-950"
                      : cn(
                          "bg-teal-800 text-white",
                          moodAccent
                            ? "ring-[color:var(--haven-ambient)] ring-offset-[color:var(--haven-canvas)]"
                            : "ring-teal-700/30 ring-offset-[color:var(--haven-canvas)]",
                        ),
                  )}
                  aria-hidden
                >
                  {userInitial(user.email)}
                </span>
                <form action={signOutAction}>
                  <button
                    type="submit"
                    className={cn(
                      "inline-flex size-9 min-h-9 min-w-9 items-center justify-center rounded-full border transition-colors",
                      isLive
                        ? "border-white/10 text-zinc-400 hover:bg-white/[0.06] hover:text-zinc-200"
                        : "border-stone-900/10 text-[color:var(--haven-muted)] hover:bg-stone-900/[0.04] hover:text-[color:var(--haven-ink)]",
                      isLive ? roomosUi.focusRingDark : roomosUi.focusRingLight,
                    )}
                    aria-label="Sign out"
                  >
                    <LogOut className="size-3.5" aria-hidden />
                  </button>
                </form>
              </div>
            ) : null
          ) : null}
          {isLive ? <LiveCameraSelect /> : null}
          </div>
        </div>
      </header>

      <LiveSessionBridge />

      <main
        className={cn(
          "relative z-10 flex w-full flex-1 flex-col",
          isLive
            ? "max-w-none min-h-0 p-0"
            : cn(
                "mx-auto w-full max-w-6xl min-h-0 px-4 py-8 sm:px-6 sm:py-12",
                roomosUi.pageEnter,
              ),
        )}
      >
        {breadcrumb && !isLive ? (
          <p className={cn("mb-6 font-mono text-[10px] font-semibold uppercase tracking-[0.22em] text-[color:var(--haven-faint)]", roomosUi.pageEnter)}>
            Haven <span className="mx-1.5 text-[color:var(--haven-line-strong)]">/</span> {breadcrumb}
          </p>
        ) : null}
        {isLive ? (
          children
        ) : (
          <div className={cn(roomosUi.pageEnterStagger1)}>{children}</div>
        )}
      </main>
    </div>
  )
}
