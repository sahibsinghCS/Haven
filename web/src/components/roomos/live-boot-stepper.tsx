"use client"

import { Camera, Cpu, Radio } from "lucide-react"

import { cn } from "@/lib/utils"
import type { BootPhase } from "@/lib/roomos/api-client"

const STEPS = [
  { id: "camera", label: "Camera", icon: Camera },
  { id: "model", label: "Model", icon: Cpu },
  { id: "burst", label: "First burst", icon: Radio },
] as const

function stepIndex(bootPhase: BootPhase, snapshotPresent: boolean): number {
  if (snapshotPresent || bootPhase === "streaming") return 2
  if (bootPhase === "warming_up") return 2
  if (bootPhase === "opening_camera" || bootPhase === "starting") return 0
  return 1
}

export function LiveBootStepper({
  bootPhase,
  snapshotPresent,
}: {
  bootPhase: BootPhase
  snapshotPresent: boolean
}) {
  const active = stepIndex(bootPhase, snapshotPresent)

  return (
    <ol
      className="mt-6 flex items-center justify-center gap-2 sm:gap-3"
      aria-label="Boot progress"
    >
      {STEPS.map((step, i) => {
        const done = i < active
        const current = i === active
        const Icon = step.icon
        return (
          <li key={step.id} className="flex items-center gap-2 sm:gap-3">
            <span
              className={cn(
                "flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em]",
                done
                  ? "border-emerald-400/40 text-emerald-200"
                  : current
                    ? "border-teal-400/45 bg-teal-950/40 text-teal-100"
                    : "border-white/10 text-zinc-600",
              )}
            >
              <Icon className="size-3" aria-hidden />
              {step.label}
            </span>
            {i < STEPS.length - 1 ? (
              <span
                className={cn(
                  "h-px w-4 sm:w-6",
                  done ? "bg-emerald-400/50" : "bg-white/10",
                )}
                aria-hidden
              />
            ) : null}
          </li>
        )
      })}
    </ol>
  )
}
