"use client"

import { AlertTriangle, BookOpen, HelpCircle, Wifi } from "lucide-react"

import type { DeviceSetupGuide } from "@/lib/roomos/device-setup-guides"
import { CONNECTION_KIND_LABELS } from "@/lib/roomos/device-setup-guides"
import { cn } from "@/lib/utils"
import { roomosUi } from "@/lib/roomos/roomos-ui"

export function CategoryIntro({
  title,
  paragraphs,
}: {
  title: string
  paragraphs: string[]
}) {
  return (
    <section
      className={cn(
        roomosUi.prefsCallout,
        "border-[color:var(--haven-line-strong)] bg-[color-mix(in_oklab,#fffefb_92%,#e8f4f2_8%)] px-5 py-4 sm:px-6",
      )}
      aria-labelledby="settings-intro-heading"
    >
      <div className="flex gap-3">
        <Wifi className="mt-0.5 size-5 shrink-0 text-teal-800/80" aria-hidden />
        <div>
          <h2
            id="settings-intro-heading"
            className="text-[14px] font-semibold text-[color:var(--haven-ink)]"
          >
            {title}
          </h2>
          {paragraphs.map((p) => (
            <p
              key={p.slice(0, 40)}
              className="mt-2 text-[13px] leading-relaxed text-[color:var(--haven-muted)]"
            >
              {p}
            </p>
          ))}
        </div>
      </div>
    </section>
  )
}

export function DeviceSetupInstructions({ guide }: { guide: DeviceSetupGuide }) {
  if (guide.id === "none") {
    return null
  }

  const showSteps =
    guide.steps.length > 0 &&
    !guide.steps[0].startsWith("You can connect") &&
    !guide.steps[0].startsWith("You can link")

  return (
    <div
      className="overflow-hidden rounded-2xl border border-[color:var(--haven-line)] bg-[linear-gradient(180deg,rgba(255,254,251,0.98)_0%,rgba(248,244,236,0.65)_100%)]"
      role="region"
      aria-label={`Setup instructions for ${guide.label}`}
    >
      <div className="border-b border-[color:var(--haven-line)] px-4 py-4 sm:px-5">
        <div className="flex flex-wrap items-center gap-2">
          <BookOpen className="size-4 text-teal-800/75" aria-hidden />
          <h3 className="text-[14px] font-semibold text-[color:var(--haven-ink)]">
            How to connect {guide.featuredModel ?? guide.label}
          </h3>
          <span className="rounded-full border border-stone-300/70 bg-stone-100/90 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-stone-600">
            {CONNECTION_KIND_LABELS[guide.connectionKind]}
          </span>
          {guide.supportsDirectControl ? (
            <span className="rounded-full border border-teal-700/20 bg-teal-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-teal-900">
              Ready in HAVEN
            </span>
          ) : null}
        </div>
        {guide.directControlNote ? (
          <p className="mt-2 text-[12px] leading-relaxed text-teal-900/85">{guide.directControlNote}</p>
        ) : null}
        {guide.tagline ? (
          <p className="mt-1 text-[12px] text-[color:var(--haven-faint)]">{guide.tagline}</p>
        ) : null}
      </div>

      <div className="space-y-4 p-4 sm:p-5">
        {guide.prerequisites.length > 0 ? (
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[color:var(--haven-faint)]">
              Before you start
            </p>
            <ul className="mt-2 space-y-1.5">
              {guide.prerequisites.map((item) => (
                <li
                  key={item}
                  className="flex gap-2 text-[13px] leading-relaxed text-[color:var(--haven-muted)]"
                >
                  <span className="mt-2 size-1.5 shrink-0 rounded-full bg-teal-700/50" aria-hidden />
                  {item}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {guide.warnings && guide.warnings.length > 0 ? (
          <ul className="space-y-2" aria-label="Important notes">
            {guide.warnings.map((w) => (
              <li
                key={w.slice(0, 48)}
                className="flex gap-2.5 rounded-xl border border-amber-500/25 bg-amber-50/90 px-3 py-2.5 text-[12px] leading-relaxed text-amber-950"
              >
                <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-700" aria-hidden />
                {w}
              </li>
            ))}
          </ul>
        ) : null}

        {showSteps ? (
          <ol className="space-y-3">
            {guide.steps.map((step, i) => (
              <li key={step} className="flex gap-3">
                <span
                  className="flex size-7 shrink-0 items-center justify-center rounded-lg border border-teal-800/15 bg-teal-50/80 font-mono text-[11px] font-semibold text-teal-900"
                  aria-hidden
                >
                  {i + 1}
                </span>
                <p className="pt-0.5 text-[13px] leading-relaxed text-[color:var(--haven-muted)]">{step}</p>
              </li>
            ))}
          </ol>
        ) : null}

        {guide.tip ? (
          <p className="rounded-xl border border-stone-300/60 bg-white/70 px-3 py-2.5 text-[12px] leading-relaxed text-stone-700">
            <span className="font-semibold text-stone-900">Tip: </span>
            {guide.tip}
          </p>
        ) : null}

        {guide.troubleshooting && guide.troubleshooting.length > 0 ? (
          <details className="group rounded-xl border border-[color:var(--haven-line)] bg-white/50">
            <summary className="flex cursor-pointer list-none items-center gap-2 px-3 py-2.5 text-[12px] font-semibold text-[color:var(--haven-ink)] marker:content-none [&::-webkit-details-marker]:hidden">
              <HelpCircle className="size-4 text-[color:var(--haven-muted)]" aria-hidden />
              Troubleshooting
              <span className="ml-auto text-[10px] font-medium uppercase tracking-wide text-[color:var(--haven-faint)] group-open:hidden">
                Show
              </span>
            </summary>
            <ul className="space-y-2 border-t border-[color:var(--haven-line)] px-3 py-3">
              {guide.troubleshooting.map((item) => (
                <li key={item.problem} className="text-[12px] leading-relaxed">
                  <p className="font-semibold text-[color:var(--haven-ink)]">{item.problem}</p>
                  <p className="mt-0.5 text-[color:var(--haven-muted)]">{item.fix}</p>
                </li>
              ))}
            </ul>
          </details>
        ) : null}
      </div>
    </div>
  )
}
