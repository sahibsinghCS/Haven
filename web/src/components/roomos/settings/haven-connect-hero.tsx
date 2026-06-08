"use client"

export function HavenConnectHero() {
  return (
    <header className="max-w-2xl">
      <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-[color:var(--haven-faint)]">
        Settings
      </p>
      <h1 className="mt-2 font-serif text-[clamp(2rem,4vw,2.5rem)] font-medium leading-tight tracking-[-0.03em] text-[color:var(--haven-ink)]">
        Connect devices to HAVEN
      </h1>
      <p className="mt-2 text-[15px] leading-relaxed text-[color:var(--haven-muted)]">
        Fill in three fields and tap <strong className="font-semibold text-[color:var(--haven-ink)]">Connect</strong>.
        Your plug stays in the Tapo app — HAVEN just talks to it over Wi‑Fi.
      </p>
    </header>
  )
}
