"use client"

import { useMutation, useQuery } from "@tanstack/react-query"
import { Home } from "lucide-react"
import { toast } from "sonner"

import { fetchRoomsStatus, updateRoom } from "@/lib/roomos/api-client"
import { cn } from "@/lib/utils"
import { useLiveSessionStore } from "@/stores/live-session-store"
import type { DeviceSettingsDocument } from "@/types/device-settings"

function connectedDeviceOptions(doc: DeviceSettingsDocument) {
  const out: { id: string; label: string; category: string }[] = []
  for (const plug of doc.devices.smartPlugs) {
    if (plug.id && plug.connected)
      out.push({ id: plug.id, label: plug.label || "Plug", category: "plug" })
  }
  for (const lights of doc.devices.lights) {
    if (lights.id && lights.connected)
      out.push({ id: lights.id, label: lights.label || "Lights", category: "lights" })
  }
  for (const thermo of doc.devices.thermostats) {
    if (thermo.id && thermo.connected) {
      out.push({ id: thermo.id, label: thermo.notes || "Thermostat", category: "thermostat" })
    }
  }
  return out
}

export function RoomsSettingsSection({
  devicesDoc,
  variant = "light",
  compact = false,
}: {
  devicesDoc: DeviceSettingsDocument
  variant?: "light" | "dark"
  compact?: boolean
}) {
  const roomsQuery = useQuery({
    queryKey: ["roomos", "rooms"],
    queryFn: ({ signal }) => fetchRoomsStatus(signal),
    staleTime: 10_000,
  })

  const saveDevices = useMutation({
    mutationFn: (args: { roomId: string; deviceIds: string[] }) =>
      updateRoom(args.roomId, { deviceIds: args.deviceIds }),
    onSuccess: (data) => {
      useLiveSessionStore.getState().setRoomsStatus(data)
      void roomsQuery.refetch()
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const deviceOptions = connectedDeviceOptions(devicesDoc)
  const rooms = roomsQuery.data?.rooms ?? []
  const isDark = variant === "dark"

  if (rooms.length === 0) {
    return (
      <p className={cn("text-sm", isDark ? "text-zinc-500" : "text-[color:var(--haven-muted)]")}>
        Add a room in the previous step to assign devices.
      </p>
    )
  }

  return (
    <section className={cn("space-y-4", compact && "space-y-3")}>
      {!compact ? (
        <>
          <div className="flex items-center gap-2">
            <Home
              className={cn("size-4", isDark ? "text-zinc-500" : "text-[color:var(--haven-muted)]")}
              aria-hidden
            />
            <h3
              className={cn(
                "text-sm font-semibold",
                isDark ? "text-zinc-100" : "text-[color:var(--haven-ink)]",
              )}
            >
              Room assignment
            </h3>
          </div>
          <p
            className={cn(
              "text-[13px] leading-relaxed",
              isDark ? "text-zinc-400" : "text-[color:var(--haven-muted)]",
            )}
          >
            Only devices in the active room follow live mood inference.
          </p>
        </>
      ) : null}
      <ul className="space-y-3">
        {rooms.map((room) => (
          <li
            key={room.id}
            className={cn(
              "rounded-xl border px-4 py-3",
              isDark
                ? "border-white/10 bg-black/25"
                : "border-[color:var(--haven-line)] bg-white/50",
            )}
          >
            <p className={cn("mb-2 text-sm font-medium", isDark ? "text-zinc-100" : undefined)}>
              {room.name}
              {room.isActive ? (
                <span className="ml-2 text-[10px] font-semibold uppercase tracking-wider text-teal-400">
                  Active
                </span>
              ) : null}
            </p>
            <div className="space-y-2">
              {deviceOptions.map((dev) => {
                const checked = room.deviceIds.includes(dev.id)
                return (
                  <label
                    key={dev.id}
                    className={cn(
                      "flex cursor-pointer items-center gap-2 text-[13px]",
                      isDark ? "text-zinc-300" : undefined,
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      disabled={saveDevices.isPending}
                      className="size-3.5 rounded border-stone-300"
                      onChange={() => {
                        const next = checked
                          ? room.deviceIds.filter((id) => id !== dev.id)
                          : [...room.deviceIds, dev.id]
                        saveDevices.mutate({ roomId: room.id, deviceIds: next })
                      }}
                    />
                    <span>
                      {dev.label}{" "}
                      <span className={isDark ? "text-zinc-600" : "text-[color:var(--haven-faint)]"}>
                        ({dev.category})
                      </span>
                    </span>
                  </label>
                )
              })}
              {deviceOptions.length === 0 ? (
                <p className={cn("text-xs", isDark ? "text-zinc-500" : "text-[color:var(--haven-muted)]")}>
                  Connect devices on{" "}
                  <a href="/connections" className="text-teal-400 underline-offset-2 hover:underline">
                    Connections
                  </a>{" "}
                  first.
                </p>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
