"use client"

import { Lightbulb } from "lucide-react"

import { cn } from "@/lib/utils"
import { roomosUi } from "@/lib/roomos/roomos-ui"

export function LiveRationaleList({
  rationale,
  className,
}: {
  rationale: string[]
  className?: string
}) {
  if (!rationale.length) {
    return (
      <p className={cn("text-[12px] leading-relaxed text-zinc-500", className)}>
        No rationale bullets for this burst yet — the model is still warming up or the
        backend did not attach explainers.
      </p>
    )
  }

  return (
    <ul className={cn("space-y-2", className)} aria-label="Why the model chose this state">
      {rationale.map((line, i) => (
        <li
          key={`${i}-${line.slice(0, 24)}`}
          className="flex gap-2.5 rounded-xl border border-white/[0.08] bg-white/[0.04] px-3 py-2.5 text-[12.5px] leading-relaxed text-zinc-200"
        >
          <Lightbulb className="mt-0.5 size-3.5 shrink-0 text-amber-300/90" aria-hidden />
          <span>{line}</span>
        </li>
      ))}
    </ul>
  )
}
