"use client"

import { Check, LayoutTemplate, Palette } from "lucide-react"

import { cn } from "@/lib/utils"
import { roomosUi } from "@/lib/roomos/roomos-ui"

type PreferencesPresetToggleProps = {
  value: string
  onValueChange: (presetId: string) => void
  basicPresetId: string
  customPresetId: string
}

const tiles = [
  {
    id: "basic" as const,
    label: "Basic Preference",
    description: "Calm defaults you can trust day to day. Tuned for real homes, not demos.",
    Icon: LayoutTemplate,
    accentColor: "text-teal-700",
    accentBg: "bg-teal-700",
    activeRing: "ring-teal-700/22",
    activeBorder: "border-teal-700/30",
    activeWash:
      "bg-[linear-gradient(168deg,rgba(255,254,251,1)_0%,rgba(236,253,251,0.86)_60%,rgba(225,247,243,0.78)_100%)]",
  },
  {
    id: "custom" as const,
    label: "Custom",
    description: "Your mix. Tweak light, airflow, and temperature, then save.",
    Icon: Palette,
    accentColor: "text-violet-700",
    accentBg: "bg-violet-700",
    activeRing: "ring-violet-700/22",
    activeBorder: "border-violet-700/30",
    activeWash:
      "bg-[linear-gradient(168deg,rgba(255,254,251,1)_0%,rgba(243,232,255,0.78)_60%,rgba(232,219,254,0.7)_100%)]",
  },
]

export function PreferencesPresetToggle({
  value,
  onValueChange,
  basicPresetId,
  customPresetId,
}: PreferencesPresetToggleProps) {
  const valueByKey: Record<"basic" | "custom", string> = {
    basic: basicPresetId,
    custom: customPresetId,
  }

  return (
    <div
      role="radiogroup"
      aria-label="Room behavior preset"
      className="grid gap-3 sm:grid-cols-2 sm:gap-4"
    >
      {tiles.map((t) => {
        const isActive = value === valueByKey[t.id]
        return (
          <button
            key={t.id}
            type="button"
            role="radio"
            aria-checked={isActive}
            onClick={() => onValueChange(valueByKey[t.id])}
            className={cn(
              "group relative flex min-h-40 flex-col items-start gap-3 overflow-hidden rounded-[1.35rem] border p-5 text-left",
              "transition-[transform,box-shadow,border-color,background-color] duration-300 ease-out",
              "shadow-[var(--haven-shadow-card)]",
              "ring-1 ring-[color:var(--haven-edge-light)]",
              roomosUi.focusRingLight,
              isActive
                ? cn(
                    "border-transparent",
                    t.activeBorder,
                    "ring-2",
                    t.activeRing,
                    t.activeWash,
                  )
                : cn(
                    "border-[color:var(--haven-line-strong)] bg-[color-mix(in_oklab,#fffefb_92%,transparent)]",
                    "hover:-translate-y-0.5 hover:border-[color:var(--haven-line-strong)] hover:bg-[color-mix(in_oklab,#fffefb_98%,transparent)] hover:shadow-[var(--haven-shadow-float)]",
                  ),
            )}
          >
            <span
              aria-hidden
              className="pointer-events-none absolute -right-10 -top-10 size-28 rounded-full bg-[radial-gradient(circle_at_30%_30%,rgba(255,255,255,0.9),transparent_64%)] opacity-70 blur-xl transition-opacity duration-300 group-hover:opacity-100"
            />
            <div className="flex w-full items-start justify-between gap-3">
              <span
                className={cn(
                  "flex size-9 shrink-0 items-center justify-center rounded-xl border border-[color:var(--haven-line-strong)] bg-white shadow-[inset_0_1px_0_rgba(255,255,255,1),0_1px_2px_rgba(18,17,15,0.06)]",
                  t.accentColor,
                )}
                aria-hidden
              >
                <t.Icon className="size-[1.05rem]" strokeWidth={1.85} />
              </span>
              <span
                aria-hidden
                className={cn(
                  "flex size-5 shrink-0 items-center justify-center rounded-full border transition-all duration-200",
                  isActive
                    ? cn("border-transparent text-white", t.accentBg)
                    : "border-[color:var(--haven-line-strong)] bg-white text-transparent",
                )}
              >
                <Check className="size-3" strokeWidth={3} />
              </span>
            </div>
            <div className="space-y-1.5">
              <p className="haven-display text-[1.0625rem] font-semibold tracking-[-0.018em] text-[color:var(--haven-ink)]">
                {t.label}
              </p>
              <p className="text-[12.5px] leading-relaxed text-[color:var(--haven-muted)]">
                {t.description}
              </p>
            </div>
            <span
              aria-hidden
              className={cn(
                "absolute inset-x-0 bottom-0 h-px origin-left scale-x-0 transition-transform duration-500 ease-out",
                t.accentBg,
                "opacity-50",
                isActive && "scale-x-100",
              )}
            />
          </button>
        )
      })}
    </div>
  )
}
