import type { Metadata } from "next"

import { TransitionReviewPanel } from "@/components/roomos/transition-review-panel"

export const metadata: Metadata = {
  title: "Review switches",
  description: "Relabel moments when Haven changed your room state — improves memory automatically.",
}

export default function ReviewPage() {
  return (
    <div className="min-h-0 flex-1 overflow-y-auto rounded-2xl border border-zinc-800/80 bg-gradient-to-b from-zinc-950 via-zinc-900 to-zinc-950 pb-8 text-zinc-100 shadow-inner">
      <TransitionReviewPanel />
    </div>
  )
}
