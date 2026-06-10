"use client"

import Image from "next/image"
import Link from "next/link"
import { useEffect, useState } from "react"

import {
  landingBtnPrimaryNav,
  landingFocusRing,
  landingLayout,
} from "@/components/landing/landing-primitives"
import { Magnetic } from "@/components/landing/landing-text"
import { LANDING_APP_ENTRY_KEY, getUserHasOpenedApp } from "@/lib/roomos/landing-app-entry"
import { markLiveStartIntent } from "@/lib/roomos/live-session-start"
import { cn } from "@/lib/utils"

const navLinkClass = cn(
  "rounded-full px-3.5 py-2 text-[12.5px] font-semibold tracking-[-0.015em] text-[color:var(--landing-muted)]",
  "transition-[color,background-color,box-shadow] duration-200 ease-out",
  "hover:bg-[color-mix(in_oklab,var(--landing-ink)_5%,transparent)] hover:text-[color:var(--landing-ink)]",
  "sm:px-4 sm:text-[13px]",
)

export function LandingNav() {
  const [showPreferencesNav, setShowPreferencesNav] = useState(false)
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const syncFromStorage = () => setShowPreferencesNav(getUserHasOpenedApp())
    const raf = requestAnimationFrame(syncFromStorage)

    const onStorage = (e: StorageEvent) => {
      if (e.key === LANDING_APP_ENTRY_KEY && e.newValue === "1") {
        setShowPreferencesNav(true)
      }
    }
    const onScroll = () => setScrolled(window.scrollY > 16)
    onScroll()
    window.addEventListener("storage", onStorage)
    window.addEventListener("scroll", onScroll, { passive: true })
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener("storage", onStorage)
      window.removeEventListener("scroll", onScroll)
    }
  }, [])

  return (
    <header className="pointer-events-none fixed inset-x-0 top-0 z-50 pt-2.5 sm:pt-3 lg:pt-3.5">
      <div className={cn(landingLayout.container, "pointer-events-auto")}>
        <div
          className={cn(
            "relative flex h-[3.15rem] items-center rounded-[1.15rem] border border-[color:var(--landing-line-strong)] px-2 backdrop-blur-2xl backdrop-saturate-[1.25] sm:h-[3.45rem] sm:rounded-2xl sm:px-2.5",
            "transition-[box-shadow,background-color,border-color] duration-300 ease-out",
            scrolled
              ? "shadow-[var(--landing-shadow-nav)]"
              : "shadow-[var(--landing-shadow-card)]",
            "bg-[linear-gradient(180deg,color-mix(in_oklab,var(--landing-surface)_86%,transparent)_0%,color-mix(in_oklab,var(--landing-canvas)_68%,rgba(18,17,15,0.03))_100%)]",
            "supports-[backdrop-filter]:bg-[linear-gradient(180deg,color-mix(in_oklab,var(--landing-surface)_78%,transparent)_0%,color-mix(in_oklab,var(--landing-canvas)_58%,rgba(18,17,15,0.035))_100%)]",
            "ring-1 ring-[color:var(--landing-edge-light)]",
          )}
        >
          <div className="absolute inset-x-4 top-0 h-px bg-gradient-to-r from-transparent via-white/55 to-transparent opacity-90 sm:inset-x-5" aria-hidden />

          <div className="relative grid w-full min-w-0 flex-1 grid-cols-2 items-center gap-x-2 px-0.5 sm:gap-x-3 sm:px-1 lg:grid-cols-[1fr_auto_1fr] lg:gap-x-4">
            <div className="min-w-0 justify-self-start">
              <Link
                href="/"
                aria-label="Haven"
                className={cn(
                  "group inline-flex max-w-full items-center gap-2.5 rounded-xl py-1 pl-1 pr-2 sm:gap-3 sm:pl-1.5 sm:pr-2.5",
                  "transition-[background-color,box-shadow] duration-200 ease-out hover:bg-[color-mix(in_oklab,var(--landing-ink)_4%,transparent)]",
                  landingFocusRing,
                )}
              >
                <span
                  className={cn(
                    "relative flex h-8 shrink-0 items-center justify-center overflow-hidden rounded-[0.65rem] px-2 sm:h-9 sm:px-2.5",
                    "bg-[linear-gradient(152deg,#242220_0%,#121110_48%,#0a0908_100%)] shadow-[inset_0_1px_0_rgba(255,255,255,0.12),0_10px_22px_-12px_rgba(0,0,0,0.45)] ring-1 ring-white/14",
                  )}
                >
                  <span className="pointer-events-none absolute inset-[1px] rounded-[0.55rem] bg-gradient-to-br from-white/10 to-transparent opacity-80 sm:rounded-[0.6rem]" aria-hidden />
                  <Image
                    src="/haven-logo.png"
                    alt=""
                    width={424}
                    height={391}
                    className="relative z-[1] h-[22px] w-auto sm:h-[26px]"
                    priority
                  />
                  <span
                    className="pointer-events-none absolute -bottom-0.5 -right-0.5 size-[5px] rounded-full border border-white/25 bg-teal-500 shadow-[0_0_0_2px_rgba(253,252,250,0.92)] sm:size-1.5"
                    aria-hidden
                  />
                </span>
                <span className="min-w-0 leading-none">
                  <span className="mt-[3px] hidden truncate text-[9px] font-semibold uppercase tracking-[0.26em] text-[color:var(--landing-faint)] sm:block sm:text-[10px]">
                    Room OS
                  </span>
                </span>
              </Link>
            </div>

            <nav
              aria-label="Marketing"
              className="hidden max-w-[min(22rem,calc(100vw-12rem))] justify-center justify-self-center lg:flex lg:gap-0.5"
            >
              <a href="#how-it-works" className={cn(navLinkClass, landingFocusRing)}>
                How it works
              </a>
              <a href="#room-states" className={cn(navLinkClass, landingFocusRing)}>
                Moods
              </a>
              {showPreferencesNav ? (
                <Link href="/preferences" className={cn(navLinkClass, landingFocusRing)}>
                  Preferences
                </Link>
              ) : null}
            </nav>

            <div className="flex min-w-0 items-center justify-end gap-1 justify-self-end sm:gap-2">
              {showPreferencesNav ? (
                <Link href="/preferences" className={cn(navLinkClass, landingFocusRing, "lg:hidden")}>
                  Preferences
                </Link>
              ) : null}
              <Magnetic strength={0.24} radius={90}>
                <Link
                  href="/live?start=1"
                  onClick={() => markLiveStartIntent()}
                  data-cursor="hover"
                  className={cn(
                    landingBtnPrimaryNav,
                    landingFocusRing,
                    "group/cta relative isolate overflow-hidden shrink-0",
                  )}
                >
                  <span
                    className="pointer-events-none absolute inset-0 -translate-x-full bg-[linear-gradient(110deg,transparent_0%,rgba(255,255,255,0.22)_50%,transparent_100%)] transition-transform duration-700 ease-out group-hover/cta:translate-x-full"
                    aria-hidden
                  />
                  <span className="relative">Get Started</span>
                </Link>
              </Magnetic>
            </div>
          </div>
        </div>
      </div>
    </header>
  )
}
