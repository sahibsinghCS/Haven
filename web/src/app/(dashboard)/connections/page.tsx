import type { Metadata } from "next"

import { ConnectionsPageClient } from "@/components/roomos/connections-page-client"

export const metadata: Metadata = {
  title: "Connections",
  description: "Connect smart plugs, lights, and thermostats to HAVEN.",
}

export default function ConnectionsPage() {
  return <ConnectionsPageClient />
}
