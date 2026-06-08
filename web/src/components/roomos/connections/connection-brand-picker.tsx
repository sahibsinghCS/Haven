"use client"

import { Check, Wifi } from "lucide-react"

import type { DeviceSetupGuide } from "@/lib/roomos/device-setup-guides"
import { CONNECTION_KIND_LABELS } from "@/lib/roomos/device-setup-guides"
import { cn } from "@/lib/utils"

export function ConnectionBrandPicker({
  label,
  guides,
  value,
  onChange,
}: {
  label: string
  guides: DeviceSetupGuide[]
  value: string
  onChange: (brandId: string) => void
}) {
  const options = guides
    .filter((g) => g.id !== "none")
    .sort((a, b) => {
      if (a.id === "tapo") return -1
      if (b.id === "tapo") return 1
      if (a.supportsDirectControl && !b.supportsDirectControl) return -1
      if (!a.supportsDirectControl && b.supportsDirectControl) return 1
      return a.label.localeCompare(b.label)
    })

  return (
    <div className="space-y-3 font-sans">
      <div>
        <p className="text-[13px] font-semibold text-stone-900">{label}</p>
        <p className="mt-1 text-[12px] leading-relaxed text-stone-600">
          Pick the brand that matches your hardware. Tapo P110M is the most tested plug in Haven.
        </p>
      </div>

      <div
        className="grid gap-2.5 sm:grid-cols-2"
        role="radiogroup"
        aria-label={label}
      >
        {options.map((guide) => {
          const selected = value === guide.id
          const ready = Boolean(guide.supportsDirectControl)

          return (
            <button
              key={guide.id}
              type="button"
              role="radio"
              aria-checked={selected}
              onClick={() => onChange(guide.id)}
              className={cn(
                "group relative rounded-xl border px-4 py-3.5 text-left transition-all duration-200",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600/40 focus-visible:ring-offset-2 focus-visible:ring-offset-[#f7f4ee]",
                selected
                  ? "border-teal-600/50 bg-gradient-to-br from-teal-50/95 via-white to-white shadow-[inset_0_1px_0_rgba(255,255,255,0.9),0_8px_24px_-16px_rgba(15,118,110,0.35)]"
                  : "border-stone-200/90 bg-white/90 hover:border-teal-700/25 hover:bg-white hover:shadow-sm",
              )}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[14px] font-semibold tracking-tight text-stone-900">
                    {guide.label}
                  </p>
                  <p className="mt-0.5 line-clamp-2 text-[12px] leading-snug text-stone-600">
                    {guide.featuredModel ?? guide.tagline}
                  </p>
                </div>
                <span
                  className={cn(
                    "flex size-5 shrink-0 items-center justify-center rounded-full border transition-colors",
                    selected
                      ? "border-teal-600 bg-teal-600 text-white"
                      : "border-stone-300 bg-white text-transparent group-hover:border-stone-400",
                  )}
                  aria-hidden
                >
                  <Check className="size-3" strokeWidth={2.5} />
                </span>
              </div>

              <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
                <span
                  className={cn(
                    "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                    ready
                      ? "bg-teal-100/90 text-teal-900"
                      : "bg-stone-100 text-stone-600",
                  )}
                >
                  {ready ? (
                    <>
                      <Wifi className="size-2.5" aria-hidden />
                      Ready in Haven
                    </>
                  ) : (
                    "Coming soon"
                  )}
                </span>
                <span className="rounded-full bg-stone-100 px-2 py-0.5 text-[10px] font-medium text-stone-600">
                  {CONNECTION_KIND_LABELS[guide.connectionKind]}
                </span>
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
