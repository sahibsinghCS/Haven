"use client"

import { useEffect, useState } from "react"

import { landingFocusRing } from "@/components/landing/landing-primitives"
import { cn } from "@/lib/utils"

const CHAPTERS = [
  { id: "hero", href: "#hero", num: "01", label: "Haven" },
  { id: "how-it-works", href: "#how-it-works", num: "02", label: "System" },
  { id: "room-states", href: "#room-states", num: "03", label: "Moods" },
  { id: "privacy", href: "#privacy", num: "04", label: "Privacy" },
  { id: "personalization", href: "#personalization", num: "05", label: "Learn" },
  { id: "final-cta", href: "#final-cta", num: "06", label: "Start" },
] as const

export function LandingChapterRail() {
  const [active, setActive] = useState<string>("hero")

  useEffect(() => {
    const ids = CHAPTERS.map((c) => c.id)
    const elements = ids
      .map((id) => document.getElementById(id))
      .filter((el): el is HTMLElement => el != null)
    if (!elements.length) return

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)
        if (visible[0]?.target.id) {
          setActive(visible[0].target.id)
        }
      },
      { rootMargin: "-20% 0px -55% 0px", threshold: [0, 0.15, 0.4] },
    )
    for (const el of elements) observer.observe(el)
    return () => observer.disconnect()
  }, [])

  return (
    <nav
      aria-label="Page chapters"
      className="pointer-events-none fixed left-4 top-1/2 z-40 hidden -translate-y-1/2 xl:block"
    >
      <ol className="pointer-events-auto flex flex-col gap-2">
        {CHAPTERS.map((chapter) => {
          const isActive = active === chapter.id
          return (
            <li key={chapter.id}>
              <a
                href={chapter.href}
                className={cn(
                  "group flex items-center gap-2 rounded-lg px-2 py-1.5 transition-colors duration-200",
                  landingFocusRing,
                  isActive
                    ? "text-[color:var(--landing-ink)]"
                    : "text-[color:var(--landing-faint)] hover:text-[color:var(--landing-muted)]",
                )}
              >
                <span
                  className={cn(
                    "font-mono text-[9px] font-semibold tabular-nums tracking-[0.12em]",
                    isActive && "text-teal-800",
                  )}
                >
                  {chapter.num}
                </span>
                <span
                  className={cn(
                    "text-[10px] font-semibold uppercase tracking-[0.18em] opacity-0 transition-opacity duration-200 group-hover:opacity-100",
                    isActive && "opacity-100",
                  )}
                >
                  {chapter.label}
                </span>
              </a>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
