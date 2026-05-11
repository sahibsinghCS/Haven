import { MarkAppEntry } from "@/components/roomos/mark-app-entry"
import { RoomDashboardShell } from "@/components/roomos/room-dashboard-shell"

export default function DashboardLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <RoomDashboardShell>
      <MarkAppEntry />
      {children}
    </RoomDashboardShell>
  )
}
