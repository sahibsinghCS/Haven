"use client"

import { cn } from "@/lib/utils"
import type { SetupWizardStep } from "@/lib/roomos/setup-session"

const STEPS: { id: SetupWizardStep; label: string }[] = [
  { id: "room", label: "Cameras" },
  { id: "devices", label: "Devices" },
  { id: "live", label: "Go live" },
]

export function SetupStepper({
  current,
  className,
  variant = "dark",
}: {
  current: SetupWizardStep
  className?: string
  variant?: "dark" | "light"
}) {
  const currentIdx = STEPS.findIndex((s) => s.id === current)

  return (
    <ol
      className={cn("flex flex-wrap items-center gap-2", className)}
      aria-label="Setup progress"
    >
      {STEPS.map((step, i) => {
        const done = i < currentIdx
        const active = i === currentIdx
        return (
          <li key={step.id} className="flex items-center gap-2">
            <span
              className={cn(
                "rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em]",
                variant === "dark"
                  ? done
                    ? "border-emerald-400/35 text-emerald-200"
                    : active
                      ? "border-teal-400/45 bg-teal-950/40 text-teal-100"
                      : "border-white/10 text-zinc-600"
                  : done
                    ? "border-teal-600/35 bg-teal-50 text-teal-900"
                    : active
                      ? "border-teal-700/40 bg-teal-50 text-teal-950"
                      : "border-stone-200 text-stone-400",
              )}
              aria-current={active ? "step" : undefined}
            >
              {step.label}
            </span>
            {i < STEPS.length - 1 ? (
              <span
                className={cn(
                  "h-px w-3 sm:w-5",
                  variant === "dark"
                    ? done
                      ? "bg-emerald-400/40"
                      : "bg-white/10"
                    : done
                      ? "bg-teal-600/30"
                      : "bg-stone-200",
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
