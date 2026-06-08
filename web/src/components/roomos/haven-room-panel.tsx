"use client"

import { useEffect, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Cloud, CloudOff } from "lucide-react"

import { fetchCloudStatus } from "@/lib/roomos/api-client"
import { getHavenRoomId, setHavenRoomId } from "@/lib/roomos/haven-room"
import { SettingsField, SettingsInput } from "@/components/roomos/settings/device-connection-card"
import { cn } from "@/lib/utils"
import { roomosUi } from "@/lib/roomos/roomos-ui"

export function HavenRoomPanel({ onRoomChange }: { onRoomChange?: () => void }) {
  const [roomId, setRoomId] = useState(getHavenRoomId)

  const cloudQuery = useQuery({
    queryKey: ["haven", "cloud-status"],
    queryFn: () => fetchCloudStatus(),
    staleTime: 60_000,
    retry: 1,
  })

  useEffect(() => {
    setRoomId(getHavenRoomId())
  }, [])

  const cloud = cloudQuery.data
  const supabaseOn = cloud?.supabase ?? false

  return (
    <section
      className={cn(
        roomosUi.prefsCallout,
        "flex flex-col gap-4 border-[color:var(--haven-line-strong)] px-5 py-4 sm:px-6",
        supabaseOn
          ? "bg-[color-mix(in_oklab,#fffefb_90%,#e8f4f2_10%)]"
          : "bg-[color-mix(in_oklab,#fffefb_90%,#fef3c7_12%)]",
      )}
    >
      <div className="flex flex-wrap items-start gap-3">
        {supabaseOn ? (
          <Cloud className="mt-0.5 size-5 text-teal-800" aria-hidden />
        ) : (
          <CloudOff className="mt-0.5 size-5 text-amber-800" aria-hidden />
        )}
        <div className="min-w-0 flex-1">
          <h2 className="text-[14px] font-semibold text-[color:var(--haven-ink)]">
            Your room in the cloud
          </h2>
          <p className="mt-1 text-[13px] leading-relaxed text-[color:var(--haven-muted)]">
            {cloud?.message ??
              "Connect plug, lights, and thermostat below — saves follow this room id."}
          </p>
        </div>
      </div>

      <SettingsField
        label="Room ID"
        hint="Same ID on every device/browser restores your Settings and Preferences (e.g. demo-room, apartment-2)."
      >
        <SettingsInput
          value={roomId}
          onChange={(e) => setRoomId(e.target.value)}
          onBlur={() => {
            const next = roomId.trim() || "default"
            setHavenRoomId(next)
            setRoomId(next)
            onRoomChange?.()
          }}
          className="font-mono text-[13px]"
          placeholder="default"
        />
      </SettingsField>
    </section>
  )
}
