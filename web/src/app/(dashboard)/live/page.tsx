import type { Metadata } from "next"

import { LivePageClient } from "@/components/roomos/live-page-client"

export const metadata: Metadata = {
  title: "Live",
  description: "See how Haven reads your room and suggests a mood — locally and in real time.",
}

export default function LivePage() {
  return <LivePageClient />
}
