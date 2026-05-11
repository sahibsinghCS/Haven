import type { Metadata } from "next"

import { PreferencesPageClient } from "@/components/roomos/preferences-page-client"

export const metadata: Metadata = {
  title: "Preferences",
  description: "Tune lights, fan, and temperature for each mood — saved on this device.",
}

export default function PreferencesPage() {
  return <PreferencesPageClient />
}
