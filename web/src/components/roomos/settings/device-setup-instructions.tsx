"use client"

import { BookOpen, Wifi } from "lucide-react"

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

  return (
    <div
      className="rounded-2xl border border-[color:var(--haven-line)] bg-[color-mix(in_oklab,#fffefb_88%,transparent)] p-4 sm:p-5"
      role="region"
      aria-label={`Setup instructions for ${guide.label}`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <BookOpen className="size-4 text-teal-800/75" aria-hidden />
        <h3 className="text-[13px] font-semibold text-[color:var(--haven-ink)]">
          How to connect {guide.label}
        </h3>
        <span className="rounded-full border border-stone-300/70 bg-stone-100/90 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-stone-600">
          {CONNECTION_KIND_LABELS[guide.connectionKind]}
        </span>
        {guide.supportsDirectControl ? (
          <span className="rounded-full border border-teal-700/20 bg-teal-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-teal-900">
            Ready to test in HAVEN
          </span>
        ) : null}
      </div>

      {guide.prerequisites.length > 0 ? (
        <div className="mt-4">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-[color:var(--haven-faint)]">
            Before you start
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-[13px] leading-relaxed text-[color:var(--haven-muted)]">
            {guide.prerequisites.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {guide.steps.length > 0 &&
      !guide.steps[0].startsWith("You can connect") &&
      !guide.steps[0].startsWith("You can link") ? (
        <ol className="mt-4 list-decimal space-y-2 pl-5 text-[13px] leading-relaxed text-[color:var(--haven-muted)]">
          {guide.steps.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      ) : null}

      {guide.tip ? (
        <p className="mt-4 rounded-xl border border-amber-500/20 bg-amber-50/80 px-3 py-2.5 text-[12px] leading-relaxed text-amber-950">
          <span className="font-semibold">Tip: </span>
          {guide.tip}
        </p>
      ) : null}
    </div>
  )
}
