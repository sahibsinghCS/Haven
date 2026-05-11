"use client"

import { LayoutTemplate, Palette } from "lucide-react"

import { cn } from "@/lib/utils"
import { roomosUi } from "@/lib/roomos/roomos-ui"

type PreferencesPresetToggleProps = {
  value: string
  onValueChange: (presetId: string) => void
  basicPresetId: string
  customPresetId: string
}

export function PreferencesPresetToggle({
  value,
  onValueChange,
  basicPresetId,
  customPresetId,
}: PreferencesPresetToggleProps) {
  return (
    <div
      role="radiogroup"
      aria-label="Room behavior preset"
      className="grid gap-3 sm:grid-cols-2"
    >
      <button
        type="button"
        role="radio"
        aria-checked={value === basicPresetId}
        onClick={() => onValueChange(basicPresetId)}
        className={cn(
          roomosUi.prefsPresetCard,
          roomosUi.focusRingLight,
          "flex flex-col items-start gap-2.5 p-5 text-left",
          value === basicPresetId
            ? "border-cyan-500/35 bg-gradient-to-br from-cyan-50/95 via-white to-white shadow-md ring-1 ring-cyan-600/12"
            : "hover:border-zinc-300 hover:bg-zinc-50/90",
        )}
      >
        <span className="flex items-center gap-2 text-sm font-semibold text-zinc-900">
          <LayoutTemplate
            className={cn(
              "size-4 shrink-0",
              value === basicPresetId ? "text-cyan-700" : "text-cyan-600/85",
            )}
            aria-hidden
          />
          Basic Preference
        </span>
        <span className="text-sm leading-snug text-zinc-600">
          Calm defaults you can trust day to day.
        </span>
      </button>
      <button
        type="button"
        role="radio"
        aria-checked={value === customPresetId}
        onClick={() => onValueChange(customPresetId)}
        className={cn(
          roomosUi.prefsPresetCard,
          roomosUi.focusRingLight,
          "flex flex-col items-start gap-2.5 p-5 text-left",
          value === customPresetId
            ? "border-violet-500/32 bg-gradient-to-br from-violet-50/90 via-white to-white shadow-md ring-1 ring-violet-600/10"
            : "hover:border-zinc-300 hover:bg-zinc-50/90",
        )}
      >
        <span className="flex items-center gap-2 text-sm font-semibold text-zinc-900">
          <Palette
            className={cn(
              "size-4 shrink-0",
              value === customPresetId ? "text-violet-700" : "text-violet-600/80",
            )}
            aria-hidden
          />
          Custom
        </span>
        <span className="text-sm leading-snug text-zinc-600">
          Your mix — tweak anything, then save.
        </span>
      </button>
    </div>
  )
}
