import { HavenAuthGate } from "@/components/auth/haven-auth-gate"
import { MarkAppEntry } from "@/components/roomos/mark-app-entry"
import { RoomDashboardShell } from "@/components/roomos/room-dashboard-shell"

export default function DashboardLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <HavenAuthGate>
      <RoomDashboardShell>
        <MarkAppEntry />
        {children}
      </RoomDashboardShell>
    </HavenAuthGate>
  )
}
