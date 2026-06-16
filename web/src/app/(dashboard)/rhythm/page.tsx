import type { Metadata } from "next"

import { RhythmPageClient } from "@/components/roomos/rhythm/rhythm-page-client"

export const metadata: Metadata = {
  title: "Rhythm",
  description: "Mood time, sleep patterns, and estimated savings from Haven live inference.",
}

export default function RhythmPage() {
  return (
    <div className="min-h-0 flex-1 overflow-y-auto">
      <RhythmPageClient />
    </div>
  )
}
