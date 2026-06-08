import Image from "next/image"
import Link from "next/link"
import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

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
        "haven-app relative flex min-h-svh flex-col text-[color:var(--haven-ink)]",
        className,
      )}
      style={{
        backgroundColor: "#f7f4ee",
        backgroundImage:
          "radial-gradient(ellipse 90% 60% at 50% -10%, rgba(255,253,250,0.96), transparent 55%), radial-gradient(ellipse 60% 45% at 92% 12%, rgba(167,243,208,0.18), transparent 55%), radial-gradient(ellipse 50% 45% at 4% 75%, rgba(253,230,138,0.14), transparent 55%), linear-gradient(180deg, #fdfcfa 0%, #f7f4ee 38%, #ebe6dc 100%)",
      }}
    >
      <div
        className="pointer-events-none fixed inset-0 bg-gradient-to-b from-white/40 via-transparent to-transparent"
        aria-hidden
      />
      <div className="relative z-10 flex flex-1 flex-col lg:flex-row">
        <aside className="hidden flex-col justify-between border-r border-[color:var(--haven-line)] bg-[color-mix(in_oklab,#fffefb_55%,transparent)] px-10 py-12 lg:flex lg:w-[min(42%,440px)] lg:shrink-0">
          <Link href="/" className="inline-flex items-center gap-3" aria-label="Haven home">
            <span className="relative flex h-11 items-center justify-center overflow-hidden rounded-[0.75rem] bg-[linear-gradient(152deg,#242220_0%,#121110_48%,#0a0908_100%)] px-3 ring-1 ring-white/14 shadow-[inset_0_1px_0_rgba(255,255,255,0.12)]">
              <Image src="/haven-logo.png" alt="" width={424} height={391} className="h-7 w-auto" priority />
            </span>
          </Link>
          <div className="max-w-xs">
            <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-[color:var(--haven-faint)]">
              Haven
            </p>
            <h2 className="mt-3 font-serif text-[2rem] font-medium leading-tight tracking-[-0.03em]">
              Local, private, adaptive
            </h2>
            <p className="mt-3 text-[15px] leading-relaxed text-[color:var(--haven-muted)]">
              Sign in to sync device connections and mood preferences across browsers. Your room data
              stays tied to your account.
            </p>
          </div>
          <p className="text-[12px] text-[color:var(--haven-faint)]">Camera and live inference run on this device.</p>
        </aside>
        <main className="flex flex-1 flex-col items-center justify-center px-5 py-10 sm:px-8">
          <div className="mb-8 flex w-full max-w-md justify-center lg:hidden">
            <Link href="/" aria-label="Haven home" className="inline-flex items-center gap-2.5">
              <span className="relative flex h-10 items-center justify-center overflow-hidden rounded-[0.7rem] bg-[linear-gradient(152deg,#242220_0%,#121110_48%,#0a0908_100%)] px-3 ring-1 ring-white/14">
                <Image src="/haven-logo.png" alt="" width={424} height={391} className="h-6 w-auto" priority />
              </span>
              <span className="text-[11px] font-semibold uppercase tracking-[0.26em] text-[color:var(--haven-faint)]">
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
