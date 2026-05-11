"use client"

import { Sparkles } from "lucide-react"

export function RationaleList({ items }: { items: string[] }) {
  return (
    <div className="border-white/8 bg-white/[0.035] rounded-2xl border p-4 shadow-sm backdrop-blur-md sm:p-5">
      <div className="text-zinc-400 mb-3 flex items-center gap-2 text-xs font-medium tracking-wide uppercase">
        <Sparkles className="size-3.5" aria-hidden />
        Why this state
      </div>
      <ul className="text-zinc-200/90 space-y-2.5 text-sm leading-relaxed">
        {items.map((line) => (
          <li key={line} className="flex gap-2">
            <span className="text-zinc-500 mt-1.5 size-1 shrink-0 rounded-full bg-zinc-500/80" aria-hidden />
            <span>{line}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
