"use client"

import { Fan, Lightbulb, Thermometer } from "lucide-react"

import type { RoomDeviceTargets } from "@/types/roomos"

export function AppliedSceneStrip({ scene }: { scene: RoomDeviceTargets }) {
  return (
    <div className="border-white/8 bg-zinc-950/40 text-zinc-200/90 flex flex-wrap items-center gap-3 rounded-2xl border px-4 py-3 text-sm shadow-sm backdrop-blur-md">
      <div className="flex items-center gap-2">
        <span className="bg-white/6 flex size-8 items-center justify-center rounded-lg border border-white/10">
          <Lightbulb className="size-4 text-amber-200/90" aria-hidden />
        </span>
        <div className="flex flex-col">
          <span className="text-zinc-500 text-xs uppercase">Lights</span>
          <span className="font-medium tabular-nums">
            {scene.brightness}% ·{" "}
            <span className="text-zinc-300">{scene.lightColorHex}</span>
          </span>
        </div>
      </div>
      <span className="bg-white/10 hidden h-8 w-px sm:block" aria-hidden />
      <div className="flex items-center gap-2">
        <span className="bg-white/6 flex size-8 items-center justify-center rounded-lg border border-white/10">
          <Fan className="size-4 text-sky-200/90" aria-hidden />
        </span>
        <div className="flex flex-col">
          <span className="text-zinc-500 text-xs uppercase">Fan</span>
          <span className="font-medium">{scene.fanOn ? "On" : "Off"}</span>
        </div>
      </div>
      <span className="bg-white/10 hidden h-8 w-px sm:block" aria-hidden />
      <div className="flex items-center gap-2">
        <span className="bg-white/6 flex size-8 items-center justify-center rounded-lg border border-white/10">
          <Thermometer className="size-4 text-rose-200/90" aria-hidden />
        </span>
        <div className="flex flex-col">
          <span className="text-zinc-500 text-xs uppercase">Target</span>
          <span className="font-medium tabular-nums">{scene.temperatureF}°F</span>
        </div>
      </div>
    </div>
  )
}
