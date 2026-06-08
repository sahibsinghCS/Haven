import type { Metadata } from "next"

import { SettingsPageClient } from "@/components/roomos/settings-page-client"

export const metadata: Metadata = {
  title: "Settings",
  description: "Connect smart plugs, Wi‑Fi lights, and thermostats from popular brands.",
}

export default function SettingsPage() {
  return <SettingsPageClient />
}
