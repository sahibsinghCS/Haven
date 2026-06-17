import Link from "next/link"
import type { ReactNode } from "react"

import { HavenLogo, HavenLogoBadge } from "@/components/brand/haven-logo"
import { cn } from "@/lib/utils"

const PROOF_BULLETS = [
  "Inference stays on your device — no video warehouse.",
  "Mood presets sync to your account, not a public feed.",
  "You can run Haven fully local when cloud is off.",
] as const

function AuthScenePreview() {
  return (
    <div
      className="relative mt-10 aspect-[4/3] w-full max-w-xs overflow-hidden rounded-[1.35rem] border border-[color:var(--haven-line-strong)] shadow-[var(--haven-shadow-float)] ring-1 ring-[color:var(--haven-edge-light)]"
      aria-hidden
    >
      <div className="absolute inset-0 bg-[linear-gradient(165deg,#1a1917_0%,#0d0c0b_55%,#141210_100%)]" />
      <div className="absolute -left-8 top-6 size-28 rounded-full bg-teal-500/25 blur-2xl" />
      <div className="absolute -right-6 bottom-8 size-24 rounded-full bg-indigo-500/20 blur-2xl" />
      <div className="absolute inset-x-4 bottom-4 rounded-xl border border-white/10 bg-zinc-950/55 px-3 py-2.5 backdrop-blur-md">
        <p className="text-[9px] font-semibold uppercase tracking-[0.2em] text-zinc-500">Right now</p>
        <p className="haven-display mt-1 text-[1.35rem] font-semibold text-zinc-50">Relaxing</p>
        <p className="mt-1 text-[10px] text-zinc-400">Warm lights · 78% confidence</p>
      </div>
      <div className="absolute left-4 top-4 flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-2 py-1">
        <span className="size-1.5 animate-pulse rounded-full bg-emerald-400 motion-reduce:animate-none" />
        <span className="text-[9px] font-semibold uppercase tracking-[0.16em] text-zinc-300">Live preview</span>
      </div>
    </div>
  )
}

export function AuthShell({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        "haven-app surface-pearl-bg haven-grain surface-grain relative flex min-h-svh flex-col text-[color:var(--haven-ink)]",
        className,
      )}
    >
      <div
        className="pointer-events-none fixed inset-0 bg-gradient-to-b from-white/40 via-transparent to-transparent"
        aria-hidden
      />
      <div className="relative z-10 flex flex-1 flex-col lg:flex-row">
        <aside className="hidden flex-col justify-between border-r border-[color:var(--haven-line)] bg-[color-mix(in_oklab,#fffefb_55%,transparent)] px-10 py-12 lg:flex lg:w-[min(42%,440px)] lg:shrink-0">
          <Link href="/" className="inline-flex items-center gap-3" aria-label="Haven home">
            <HavenLogoBadge variant="mark" size="lg" priority badgeClassName="size-11 shrink-0 px-2" />
            <span className="haven-display text-[13px] font-semibold uppercase tracking-[0.24em] text-[color:var(--haven-ink)]">
              Haven
            </span>
          </Link>
          <div className="max-w-xs">
            <HavenLogo
              variant="mark"
              size="2xl"
              aria-hidden
              className="mb-6 opacity-90"
            />
            <p className="haven-eyebrow">Haven</p>
            <h2 className="haven-page-title mt-3 text-[2rem] leading-tight">Local, private, adaptive</h2>
            <p className="haven-lede mt-3 text-[color:var(--haven-muted)]">
              Sign in to sync device connections and mood preferences across browsers. Your room data
              stays tied to your account.
            </p>
            <AuthScenePreview />
            <ul className="mt-6 space-y-3">
              {PROOF_BULLETS.map((line) => (
                <li key={line} className="flex gap-2.5 text-[13px] leading-relaxed text-[color:var(--haven-muted)]">
                  <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-teal-600/70" aria-hidden />
                  {line}
                </li>
              ))}
            </ul>
          </div>
          <p className="text-[12px] text-[color:var(--haven-faint)]">Camera and live inference run on this device.</p>
        </aside>
        <main className="flex flex-1 flex-col items-center justify-center px-5 py-10 sm:px-8">
          <div className="mb-8 flex w-full max-w-md justify-center lg:hidden">
            <Link href="/" aria-label="Haven home" className="inline-flex items-center gap-2.5">
              <HavenLogoBadge variant="mark" size="md" priority badgeClassName="size-10 shrink-0 px-1.5" />
              <span className="haven-display text-[12px] font-semibold uppercase tracking-[0.22em] text-[color:var(--haven-ink)]">
                Haven
              </span>
            </Link>
          </div>
          {children}
        </main>
      </div>
    </div>
  )
}
