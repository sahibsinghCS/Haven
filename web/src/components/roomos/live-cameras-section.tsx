"use client"

import { useCallback, useMemo, useState } from "react"
import { Camera, Plus } from "lucide-react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { toast } from "sonner"

import { CameraDeviceRow } from "@/components/roomos/camera-device-row"
import { LiveCameraSelect } from "@/components/roomos/live-camera-select"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  createRoom,
  deleteRoom,
  fetchCameras,
  fetchRoomsStatus,
  setRoomEnabled,
  updateRoom,
  type CameraOption,
} from "@/lib/roomos/api-client"
import { formatCameraDeviceLabel } from "@/lib/roomos/format-camera-device-label"
import { roomosUi } from "@/lib/roomos/roomos-ui"
import { useLiveSessionStore } from "@/stores/live-session-store"
import type { RoomStatus } from "@/types/roomos"
import { cn } from "@/lib/utils"

type DraftCamera = {
  id: string
  name: string
  cameraValue: string | null
}

function cameraValueKey(source: number | string, backend: string): string {
  return `${source}::${backend}`
}

function parseCameraValue(value: string): { source: number | string; backend: string } {
  const [sourceRaw, backend] = value.split("::")
  const source =
    sourceRaw !== undefined && /^\d+$/.test(sourceRaw) ? Number(sourceRaw) : sourceRaw
  return { source: source ?? 0, backend: backend || "auto" }
}

function cameraDetail(
  room: RoomStatus,
  cameras: CameraOption[] | undefined,
): string | null {
  if (!room.enabled) {
    return "Open setup to pick a webcam or phone camera."
  }
  const key = cameraValueKey(room.camera.source, room.camera.backend)
  const match = cameras?.find((c) => cameraValueKey(c.source, c.backend) === key)
  if (match) {
    const label = formatCameraDeviceLabel(match.label)
    if (match.kind === "droidcam" || match.kind === "droidcam_auto") {
      return `${label} · phone stream`
    }
    return `${label} · ${match.backend}`
  }
  if (typeof room.camera.source === "number") {
    return `Webcam index ${room.camera.source}`
  }
  return "Phone camera"
}

function CameraConnectForm({
  name,
  onNameChange,
  cameraValue,
  onCameraChange,
  forNewRoom,
  excludeRoomId,
  initialValue,
  connectLabel,
  connecting,
  onSubmit,
  variant,
}: {
  name: string
  onNameChange: (value: string) => void
  cameraValue: string | null
  onCameraChange: (value: string) => void
  forNewRoom?: boolean
  excludeRoomId?: string
  initialValue?: string
  connectLabel: string
  connecting: boolean
  onSubmit: () => void
  variant: "light" | "dark"
}) {
  const isDark = variant === "dark"

  return (
    <div className="space-y-5 font-sans">
      <div
        className={cn(
          "rounded-xl border px-4 py-3.5 text-[13px] leading-relaxed",
          isDark
            ? "border-white/10 bg-black/30 text-zinc-400"
            : "border-stone-200/80 bg-white/80 text-stone-600 shadow-[inset_0_1px_0_rgba(255,255,255,0.95)]",
        )}
      >
        Pick a webcam or DroidCam feed. For multiple phones, open DroidCam on each device, tap{" "}
        <span className="font-semibold">Rescan</span>, then choose{" "}
        <span className="font-semibold">Phone camera (auto-discover)</span> on every room card — Haven
        assigns the next free phone to each room automatically.
      </div>

      <div className="space-y-2">
        <Label
          htmlFor="camera-room-name"
          className={cn("text-[13px]", isDark ? "text-zinc-400" : "text-stone-700")}
        >
          Room name
        </Label>
        <Input
          id="camera-room-name"
          value={name}
          onChange={(e) => onNameChange(e.target.value)}
          placeholder="Lounge, Bedroom, Office…"
          className={cn(
            isDark ? "border-white/10 bg-black/40 text-zinc-100" : "border-stone-200/80 bg-white/90",
          )}
        />
      </div>

      <div className="space-y-2">
        <p
          className={cn(
            "text-[10px] font-semibold uppercase tracking-[0.16em]",
            isDark ? "text-zinc-500" : "text-stone-500",
          )}
        >
          Camera source
        </p>
        <LiveCameraSelect
          className="w-full max-w-none"
          tone={isDark ? "dark" : "light"}
          pickerOnly
          forNewRoom={forNewRoom}
          excludeRoomId={excludeRoomId}
          initialValue={initialValue}
          onSelectValue={onCameraChange}
        />
      </div>

      <Button
        type="button"
        disabled={!cameraValue || connecting}
        onClick={onSubmit}
        className={cn("gap-2", roomosUi.havenPrimaryBtn)}
      >
        {connectLabel}
      </Button>
    </div>
  )
}

export function LiveCamerasSection({
  className,
  variant = "light",
}: {
  className?: string
  variant?: "light" | "dark"
}) {
  const setRoomsStatus = useLiveSessionStore((s) => s.setRoomsStatus)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [drafts, setDrafts] = useState<DraftCamera[]>([])
  const [draftEdits, setDraftEdits] = useState<Record<string, DraftCamera>>({})
  const [roomEdits, setRoomEdits] = useState<Record<string, { name: string; cameraValue: string }>>(
    {},
  )
  const [busyId, setBusyId] = useState<string | null>(null)
  const [renamingId, setRenamingId] = useState<string | null>(null)

  const isDark = variant === "dark"

  const roomsQuery = useQuery({
    queryKey: ["roomos", "rooms"],
    queryFn: ({ signal }) => fetchRoomsStatus(signal),
    staleTime: 5_000,
  })

  const camerasQuery = useQuery({
    queryKey: ["roomos", "cameras"],
    queryFn: ({ signal }) => fetchCameras(signal),
    staleTime: 10_000,
  })

  const rooms = roomsQuery.data?.rooms ?? []
  const cameras = camerasQuery.data?.cameras

  const syncRooms = useCallback(
    (data: Awaited<ReturnType<typeof fetchRoomsStatus>>) => {
      setRoomsStatus(data)
      void roomsQuery.refetch()
    },
    [roomsQuery, setRoomsStatus],
  )

  const create = useMutation({
    mutationFn: async (draft: DraftCamera) => {
      if (!draft.cameraValue) throw new Error("Pick a camera first")
      const { source, backend } = parseCameraValue(draft.cameraValue)
      return createRoom({
        name: draft.name.trim() || "Room",
        camera: { source, backend },
      })
    },
    onSuccess: (data, draft) => {
      syncRooms(data)
      setDrafts((prev) => prev.filter((d) => d.id !== draft.id))
      setDraftEdits((prev) => {
        const next = { ...prev }
        delete next[draft.id]
        return next
      })
      setExpandedId(null)
      toast.success("Camera connected")
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const saveRoom = useMutation({
    mutationFn: async ({
      roomId,
      name,
      cameraValue,
    }: {
      roomId: string
      name: string
      cameraValue: string
    }) => {
      const { source, backend } = parseCameraValue(cameraValue)
      return updateRoom(roomId, {
        name: name.trim() || undefined,
        camera: { source, backend },
        enabled: true,
      })
    },
    onSuccess: (data) => {
      syncRooms(data)
      setExpandedId(null)
      toast.success("Camera updated")
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const renameRoom = useMutation({
    mutationFn: ({ roomId, name }: { roomId: string; name: string }) =>
      updateRoom(roomId, { name }),
    onSuccess: (data) => {
      syncRooms(data)
      setRenamingId(null)
    },
    onError: (e: Error) => {
      setRenamingId(null)
      toast.error(e.message)
    },
  })

  const disconnect = useMutation({
    mutationFn: (roomId: string) => setRoomEnabled(roomId, false),
    onSuccess: syncRooms,
    onError: (e: Error) => toast.error(e.message),
  })

  const remove = useMutation({
    mutationFn: (roomId: string) => deleteRoom(roomId),
    onSuccess: (data) => {
      syncRooms(data)
      toast.success("Camera removed")
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const addDraft = useCallback(() => {
    const id = `draft-${crypto.randomUUID()}`
    const draft: DraftCamera = { id, name: "", cameraValue: null }
    setDrafts((prev) => [...prev, draft])
    setDraftEdits((prev) => ({ ...prev, [id]: draft }))
    setExpandedId(id)
  }, [])

  const getDraft = useCallback(
    (id: string): DraftCamera => {
      const edit = draftEdits[id]
      const base = drafts.find((d) => d.id === id)
      return edit ?? base ?? { id, name: "", cameraValue: null }
    },
    [draftEdits, drafts],
  )

  const getRoomEdit = useCallback(
    (room: RoomStatus) => {
      const edit = roomEdits[room.id]
      if (edit) return edit
      return {
        name: room.name,
        cameraValue: cameraValueKey(room.camera.source, room.camera.backend),
      }
    },
    [roomEdits],
  )

  const connectedCount = useMemo(() => rooms.filter((r) => r.enabled).length, [rooms])

  return (
    <section className={cn("flex flex-col gap-4", className)}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <Camera
            className={cn("size-4", isDark ? "text-zinc-500" : "text-stone-500")}
            aria-hidden
          />
          <h3
            className={cn(
              "text-[13px] font-semibold uppercase tracking-[0.2em]",
              isDark ? "text-zinc-400" : "text-stone-600",
            )}
          >
            Cameras
          </h3>
          <span
            className={cn(
              "rounded-full border px-2 py-0.5 text-[11px] font-semibold",
              isDark
                ? "border-white/10 bg-black/25 text-zinc-400"
                : "border-stone-200/80 bg-stone-100/90 text-stone-600",
            )}
          >
            {connectedCount} connected
          </span>
        </div>
        <button
          type="button"
          onClick={addDraft}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-[12px] font-semibold transition",
            isDark
              ? "border-white/15 bg-black/25 text-zinc-200 hover:border-teal-500/35 hover:bg-teal-950/30"
              : "border-stone-300/90 bg-white/90 text-stone-800 hover:border-teal-700/30 hover:bg-teal-50/60",
          )}
        >
          <Plus className="size-3.5" aria-hidden />
          Add camera
        </button>
      </div>

      <p
        className={cn(
          "text-[13px] leading-relaxed",
          isDark ? "text-zinc-500" : "text-stone-600",
        )}
      >
        One card per camera feed. Each DroidCam phone needs its own card — rescan after opening
        the app on every phone, then pick a different stream per room.
      </p>

      {rooms.length === 0 && drafts.length === 0 ? (
        <p
          className={cn(
            "rounded-xl border border-dashed px-4 py-6 text-center text-[13px]",
            isDark
              ? "border-white/15 bg-black/20 text-zinc-500"
              : "border-stone-300/80 bg-white/50 text-stone-500",
          )}
        >
          No cameras yet. Click{" "}
          <span className={cn("font-semibold", isDark ? "text-zinc-300" : "text-stone-700")}>
            Add camera
          </span>{" "}
          to connect your first feed.
        </p>
      ) : null}

      <div className="flex flex-col gap-3">
        {rooms.map((room) => {
          const isOpen = expandedId === room.id
          const edit = getRoomEdit(room)
          const busy =
            busyId === room.id && (saveRoom.isPending || disconnect.isPending || remove.isPending)

          return (
            <CameraDeviceRow
              key={room.id}
              variant={variant}
              icon={Camera}
              eyebrow="Camera"
              headline={room.name}
              onRename={(name) => {
                setRenamingId(room.id)
                renameRoom.mutate({ roomId: room.id, name })
              }}
              renaming={renamingId === room.id && renameRoom.isPending}
              detail={cameraDetail(room, cameras)}
              connected={room.enabled}
              expanded={isOpen}
              onToggleSetup={() => setExpandedId(isOpen ? null : room.id)}
              onDisconnect={
                room.enabled
                  ? () => {
                      setBusyId(room.id)
                      disconnect.mutate(room.id, { onSettled: () => setBusyId(null) })
                    }
                  : undefined
              }
              disconnecting={busyId === room.id && disconnect.isPending}
              onRemove={() => {
                setBusyId(room.id)
                remove.mutate(room.id, { onSettled: () => setBusyId(null) })
              }}
              removing={busyId === room.id && remove.isPending}
            >
              <CameraConnectForm
                variant={variant}
                name={edit.name}
                onNameChange={(name) =>
                  setRoomEdits((prev) => ({
                    ...prev,
                    [room.id]: { ...getRoomEdit(room), name },
                  }))
                }
                cameraValue={edit.cameraValue}
                onCameraChange={(cameraValue) =>
                  setRoomEdits((prev) => ({
                    ...prev,
                    [room.id]: { ...getRoomEdit(room), cameraValue },
                  }))
                }
                excludeRoomId={room.id}
                initialValue={edit.cameraValue}
                connectLabel={room.enabled ? "Save camera" : "Connect camera"}
                connecting={busy}
                onSubmit={() => {
                  setBusyId(room.id)
                  saveRoom.mutate(
                    { roomId: room.id, name: edit.name, cameraValue: edit.cameraValue },
                    { onSettled: () => setBusyId(null) },
                  )
                }}
              />
            </CameraDeviceRow>
          )
        })}

        {drafts.map((draft) => {
          const isOpen = expandedId === draft.id
          const edit = getDraft(draft.id)
          const busy = busyId === draft.id && create.isPending

          return (
            <CameraDeviceRow
              key={draft.id}
              variant={variant}
              icon={Camera}
              eyebrow="Camera"
              headline={edit.name.trim() || "New camera"}
              detail="Open setup to pick a webcam or phone camera."
              connected={false}
              expanded={isOpen}
              onToggleSetup={() => setExpandedId(isOpen ? null : draft.id)}
              onRemove={() => {
                setDrafts((prev) => prev.filter((d) => d.id !== draft.id))
                setDraftEdits((prev) => {
                  const next = { ...prev }
                  delete next[draft.id]
                  return next
                })
                if (expandedId === draft.id) setExpandedId(null)
              }}
            >
              <CameraConnectForm
                variant={variant}
                name={edit.name}
                onNameChange={(name) =>
                  setDraftEdits((prev) => ({
                    ...prev,
                    [draft.id]: { ...getDraft(draft.id), name },
                  }))
                }
                cameraValue={edit.cameraValue}
                onCameraChange={(cameraValue) =>
                  setDraftEdits((prev) => ({
                    ...prev,
                    [draft.id]: { ...getDraft(draft.id), cameraValue },
                  }))
                }
                forNewRoom
                connectLabel="Connect camera"
                connecting={busy}
                onSubmit={() => {
                  setBusyId(draft.id)
                  create.mutate(getDraft(draft.id), { onSettled: () => setBusyId(null) })
                }}
              />
            </CameraDeviceRow>
          )
        })}
      </div>
    </section>
  )
}
