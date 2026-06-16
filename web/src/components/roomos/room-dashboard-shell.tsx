"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import Image from "next/image"
import { usePathname } from "next/navigation"
import { motion, useReducedMotion } from "framer-motion"
import Link from "next/link"
import { useQueryClient } from "@tanstack/react-query"

import { useHavenAuth } from "@/components/auth/haven-auth-provider"
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
  { href: "/preferences", label: "Moods / Preferences" },
  { href: "/connections", label: "Connections" },
] as const

export function RoomDashboardShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const queryClient = useQueryClient()
  const { user } = useHavenAuth()
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

  return (
    <div
      className={cn(
        "relative flex flex-1 flex-col overflow-x-clip",
        isLive
          ? "h-svh max-h-svh overflow-hidden bg-gradient-to-b from-zinc-950 via-zinc-900 to-zinc-950 text-zinc-100"
          : "haven-app haven-grain min-h-full text-[color:var(--haven-ink)]",
      )}
      data-haven-mood={!isLive && ambientMood ? ambientMood : undefined}
      style={
        isLive
          ? undefined
          : {
              backgroundColor: "#f7f4ee",
              backgroundImage:
                "radial-gradient(ellipse 90% 60% at 50% -10%, rgba(255,253,250,0.96), transparent 55%), radial-gradient(ellipse 60% 45% at 92% 12%, rgba(167,243,208,0.18), transparent 55%), radial-gradient(ellipse 50% 45% at 4% 75%, rgba(253,230,138,0.14), transparent 55%), linear-gradient(180deg, #fdfcfa 0%, #f7f4ee 38%, #ebe6dc 100%)",
            }
      }
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
          className="pointer-events-none fixed -top-24 left-1/2 z-0 h-[320px] w-[min(900px,95vw)] -translate-x-1/2 rounded-full blur-3xl transition-opacity duration-700"
          style={{ background: `radial-gradient(ellipse, var(--haven-ambient) 0%, transparent 68%)` }}
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
            "relative mx-auto flex w-full items-center justify-between gap-4",
            isLive ? "max-w-none px-4 sm:px-5" : "max-w-6xl px-4 sm:px-6",
          )}
        >
          <Link
            href="/"
            aria-label="Haven home"
            className={cn(
              "group inline-flex min-w-0 items-center gap-2.5 rounded-xl py-1 pl-1 pr-2",
              "transition-[background-color] duration-200 ease-out",
              isLive
                ? cn(roomosUi.focusRingDark, "hover:bg-white/[0.04]")
                : cn(roomosUi.focusRingLight, "hover:bg-stone-900/[0.04]"),
            )}
          >
            <span
              className={cn(
                "relative flex h-9 shrink-0 items-center justify-center overflow-hidden rounded-[0.7rem] px-2.5 ring-1",
                isLive
                  ? "bg-[linear-gradient(152deg,#2a2826_0%,#141312_48%,#0a0908_100%)] shadow-[inset_0_1px_0_rgba(255,255,255,0.12),0_10px_22px_-12px_rgba(0,0,0,0.5)] ring-white/12"
                  : "bg-[linear-gradient(152deg,#242220_0%,#121110_48%,#0a0908_100%)] shadow-[inset_0_1px_0_rgba(255,255,255,0.12),0_10px_22px_-12px_rgba(0,0,0,0.45)] ring-white/14",
              )}
            >
              <span className="pointer-events-none absolute inset-[1px] rounded-[0.6rem] bg-gradient-to-br from-white/10 to-transparent opacity-80" aria-hidden />
              <Image
                src="/haven-logo.png"
                alt=""
                width={424}
                height={391}
                className="relative z-[1] h-[26px] w-auto"
                priority
              />
              <span
                className={cn(
                  "pointer-events-none absolute -bottom-0.5 -right-0.5 size-1.5 rounded-full border border-white/25 bg-teal-500",
                  isLive
                    ? "shadow-[0_0_0_2px_rgba(9,9,11,0.95)]"
                    : "shadow-[0_0_0_2px_rgba(247,243,235,0.95)]",
                )}
                aria-hidden
              />
            </span>
            <span className="min-w-0 leading-none">
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

          <div className="flex shrink-0 items-center gap-2">
          <nav
            ref={navWrapRef}
            aria-label="Primary"
            className={cn(
              "relative flex shrink-0 items-center gap-0.5 rounded-full border p-0.5 sm:gap-1 sm:p-1",
              isLive
                ? "border-white/[0.1] bg-zinc-950/58 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.05)] supports-[backdrop-filter]:bg-zinc-950/46"
                : "border-stone-900/[0.1] bg-white/85 shadow-[inset_0_1px_0_0_rgba(255,255,255,1),0_10px_28px_-22px_rgba(15,23,42,0.18)] backdrop-blur-md",
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
                    "relative z-[1] whitespace-nowrap rounded-full px-3 py-1.5 text-[13px] font-semibold tracking-tight transition-colors duration-200 sm:px-4",
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
                  {item.label}
                </Link>
              )
            })}
          </nav>
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
        {children}
      </main>
    </div>
  )
}
