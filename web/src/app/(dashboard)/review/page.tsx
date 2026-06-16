import type { Metadata } from "next"

import { TransitionReviewPanel } from "@/components/roomos/transition-review-panel"

export const metadata: Metadata = {
  title: "Review switches",
 description: "Relabel moments when Haven changed your room state. improves memory automatically.",
}

export default function ReviewPage() {
  return (
    <div className="min-h-0 flex-1 overflow-y-auto">
      <TransitionReviewPanel />
    </div>
  )
}
