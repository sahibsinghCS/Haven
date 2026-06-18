"use client"

import { useCallback, useMemo, useState } from "react"
import { Camera, Loader2, Plus } from "lucide-react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { toast } from "sonner"

import { CameraDeviceRow } from "@/components/roomos/camera-device-row"
import { LiveCameraSelect } from "@/components/roomos/live-camera-select"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  createRoom,
  deleteRoom,
  fetchCameras,
  fetchRoomsStatus,
  setRoomEnabled,
  updateRoom,
  validateCameraSource,
  type CameraOption,
  type CamerasResponse,
} from "@/lib/roomos/api-client"
import {
  buildCameraSource,
  CAMERA_CONNECTION_TYPES,
  cameraValueKey,
  defaultManualFields,
  inferConnectionType,
  manualFieldsFromSource,
  WIFI_CAMERA_BRANDS,
  wifiBrandOption,
  type CameraConnectionType,
  type CameraManualFields,
  type WifiCameraBrand,
} from "@/lib/roomos/camera-connection-fields"
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
  const src = String(room.camera.source)
  if (src.startsWith("rtsp://")) {
    return `WiFi camera · ${src.replace(/^rtsp:\/\/[^@]*@/, "rtsp://")}`
  }
  if (src.startsWith("http://") || src.startsWith("https://")) {
    return `Network camera · ${src.replace(/^https?:\/\//, "").split("/")[0]}`
  }
  return "Network camera"
}

function WifiCameraFields({
  variant,
  streamKind,
  fields,
  discoveredWifi,
  onChange,
  onPickDiscoveredHost,
}: {
  variant: "light" | "dark"
  streamKind: "rtsp" | "http"
  fields: CameraManualFields
  discoveredWifi: NonNullable<CamerasResponse["discoveredWifi"]>
  onChange: (fields: CameraManualFields) => void
  onPickDiscoveredHost: (host: string) => void
}) {
  const isDark = variant === "dark"
  const brand = wifiBrandOption(
    streamKind === "http" ? "generic_http" : fields.wifiBrand,
  )
  const brands = WIFI_CAMERA_BRANDS.filter((b) =>
    streamKind === "http" ? b.id === "generic_http" : b.id !== "generic_http",
  )

  const inputClass = cn(
    "font-mono text-sm",
    isDark ? "border-white/10 bg-black/40 text-zinc-100" : "border-stone-200/80 bg-white/90",
  )

  return (
    <div className="space-y-4">
      {discoveredWifi.length > 0 && streamKind === "rtsp" ? (
        <div className="space-y-2">
          <p className={cn("text-[12px] font-medium", isDark ? "text-zinc-400" : "text-stone-600")}>
            Found on your network (ONVIF)
          </p>
          <div className="flex flex-wrap gap-2">
            {discoveredWifi.map((cam) => (
              <button
                key={cam.host}
                type="button"
                onClick={() => onPickDiscoveredHost(cam.host)}
                className={cn(
                  "rounded-lg border px-3 py-1.5 text-[12px] font-medium transition",
                  isDark
                    ? "border-white/15 bg-black/30 text-zinc-200 hover:border-teal-500/40"
                    : "border-stone-200 bg-white text-stone-800 hover:border-teal-600/40",
                )}
              >
                {cam.label || cam.host}
              </button>
            ))}
          </div>
          <p className={cn("text-[11px]", isDark ? "text-zinc-500" : "text-stone-500")}>
            Tap a camera, then enter its username and password below (same as Home Assistant ONVIF).
          </p>
        </div>
      ) : null}

      {streamKind === "rtsp" ? (
        <div className="space-y-2">
          <Label className={cn("text-[12px]", isDark ? "text-zinc-400" : "text-stone-600")}>
            Camera brand
          </Label>
          <Select
            value={fields.wifiBrand}
            onValueChange={(v) =>
              onChange({
                ...fields,
                wifiBrand: v as WifiCameraBrand,
                port: wifiBrandOption(v as WifiCameraBrand).defaultPort,
              })
            }
          >
            <SelectTrigger className={cn("w-full text-xs", inputClass)}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent
              className={cn(
                isDark
                  ? "border-white/10 bg-zinc-950 text-zinc-100"
                  : "border-stone-200/80 bg-white text-stone-900",
              )}
            >
              {brands.map((b) => (
                <SelectItem key={b.id} value={b.id} className="text-xs">
                  <span className="flex flex-col gap-0.5">
                    <span>{b.label}</span>
                    <span className="text-[10px] font-normal text-zinc-500">{b.hint}</span>
                  </span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      ) : null}

      {!fields.useAdvancedUrl ? (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="space-y-1.5 sm:col-span-2">
              <Label className={cn("text-[12px]", isDark ? "text-zinc-400" : "text-stone-600")}>
                Camera IP address
              </Label>
              <Input
                value={fields.host}
                onChange={(e) => onChange({ ...fields, host: e.target.value })}
                placeholder="192.168.1.50"
                className={inputClass}
              />
            </div>
            <div className="space-y-1.5">
              <Label className={cn("text-[12px]", isDark ? "text-zinc-400" : "text-stone-600")}>
                Port
              </Label>
              <Input
                value={fields.port}
                onChange={(e) => onChange({ ...fields, port: e.target.value })}
                placeholder={brand.defaultPort}
                className={inputClass}
              />
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label className={cn("text-[12px]", isDark ? "text-zinc-400" : "text-stone-600")}>
                Username
              </Label>
              <Input
                value={fields.username}
                onChange={(e) => onChange({ ...fields, username: e.target.value })}
                placeholder="admin"
                className={inputClass}
                autoComplete="off"
              />
            </div>
            <div className="space-y-1.5">
              <Label className={cn("text-[12px]", isDark ? "text-zinc-400" : "text-stone-600")}>
                Password
              </Label>
              <Input
                type="password"
                value={fields.password}
                onChange={(e) => onChange({ ...fields, password: e.target.value })}
                placeholder="••••••••"
                className={inputClass}
                autoComplete="off"
              />
            </div>
          </div>
          {streamKind === "rtsp" &&
          ["hikvision", "reolink", "amcrest", "dahua"].includes(fields.wifiBrand) ? (
            <label
              className={cn(
                "flex cursor-pointer items-center gap-2 text-[12px]",
                isDark ? "text-zinc-400" : "text-stone-600",
              )}
            >
              <input
                type="checkbox"
                checked={fields.substream}
                onChange={(e) => onChange({ ...fields, substream: e.target.checked })}
                className="size-3.5 rounded border-stone-300"
              />
              Use substream (lower resolution, less bandwidth)
            </label>
          ) : null}
          <div className="space-y-1.5">
            <Label className={cn("text-[12px]", isDark ? "text-zinc-400" : "text-stone-600")}>
              {brand.streamLabel}
            </Label>
            <Input
              value={fields.path}
              onChange={(e) => onChange({ ...fields, path: e.target.value })}
              placeholder={
                streamKind === "rtsp" ? "/stream1 or leave blank for brand default" : "/mjpeg"
              }
              className={inputClass}
            />
          </div>
        </>
      ) : (
        <div className="space-y-1.5">
          <Label className={cn("text-[12px]", isDark ? "text-zinc-400" : "text-stone-600")}>
            {streamKind === "rtsp" ? "Full RTSP URL" : "Full HTTP URL"}
          </Label>
          <Input
            value={streamKind === "rtsp" ? fields.rtspUrl : fields.httpUrl}
            onChange={(e) =>
              onChange(
                streamKind === "rtsp"
                  ? { ...fields, rtspUrl: e.target.value }
                  : { ...fields, httpUrl: e.target.value },
              )
            }
            placeholder={
              streamKind === "rtsp"
                ? "rtsp://user:pass@192.168.1.50:554/stream1"
                : "http://192.168.1.50/mjpeg"
            }
            className={inputClass}
          />
        </div>
      )}

      <label
        className={cn(
          "flex cursor-pointer items-center gap-2 text-[12px]",
          isDark ? "text-zinc-500" : "text-stone-500",
        )}
      >
        <input
          type="checkbox"
          checked={fields.useAdvancedUrl}
          onChange={(e) => onChange({ ...fields, useAdvancedUrl: e.target.checked })}
          className="size-3.5 rounded border-stone-300"
        />
        Advanced: paste full {streamKind === "rtsp" ? "RTSP" : "HTTP"} URL (Home Assistant Generic
        Camera style)
      </label>
    </div>
  )
}

function CameraConnectForm({
  name,
  onNameChange,
  cameraValue,
  onCameraChange,
  forNewRoom,
  excludeRoomId,
  initialValue,
  initialSource,
  connectLabel,
  connecting,
  onConnect,
  variant,
}: {
  name: string
  onNameChange: (value: string) => void
  cameraValue: string | null
  onCameraChange: (value: string) => void
  forNewRoom?: boolean
  excludeRoomId?: string
  initialValue?: string
  initialSource?: number | string
  connectLabel: string
  connecting: boolean
  onConnect: (payload: { name: string; source: number | string; backend: string }) => void
  variant: "light" | "dark"
}) {
  const isDark = variant === "dark"
  const [connectionType, setConnectionType] = useState<CameraConnectionType>(() =>
    initialSource !== undefined ? inferConnectionType(initialSource) : "scan",
  )
  const [manualFields, setManualFields] = useState<CameraManualFields>(() =>
    initialSource !== undefined ? manualFieldsFromSource(initialSource) : defaultManualFields(),
  )
  const [validating, setValidating] = useState(false)
  const [scanSummary, setScanSummary] = useState<string | null>(null)
  const [discoveredWifi, setDiscoveredWifi] = useState<
    NonNullable<CamerasResponse["discoveredWifi"]>
  >([])

  const onScanComplete = useCallback((data: CamerasResponse) => {
    const scan = data.scan
    if (data.discoveredWifi?.length) {
      setDiscoveredWifi(data.discoveredWifi)
    }
    if (!scan) return
    const parts: string[] = []
    if (scan.phonesFound > 0) {
      parts.push(
        `${scan.phonesFound} phone${scan.phonesFound === 1 ? "" : "s"} on Wi‑Fi`,
      )
      if (scan.phonesAvailable > 0) {
        parts.push(`${scan.phonesAvailable} available for this room`)
      }
      if (scan.phonesAssigned > 0) {
        parts.push(`${scan.phonesAssigned} already assigned to other rooms`)
      }
    }
    if (scan.onvifFound && scan.onvifFound > 0) {
      parts.push(
        `${scan.onvifFound} ONVIF camera${scan.onvifFound === 1 ? "" : "s"} on LAN — use WiFi (RTSP) and enter credentials`,
      )
    }
    if (scan.usbProbeSkipped) {
      parts.push("USB scan skipped so your live feed stays connected")
    }
    setScanSummary(parts.length > 0 ? parts.join(" · ") : null)
  }, [])

  const applyDiscoveredHost = (host: string) => {
    setConnectionType("wifi_rtsp")
    setManualFields((f) => ({
      ...f,
      host,
      port: "554",
      wifiBrand: "onvif",
    }))
  }

  const canConnect =
    connectionType === "scan"
      ? Boolean(cameraValue)
      : connectionType === "phone_ip"
        ? Boolean(manualFields.host.trim())
        : connectionType === "wifi_rtsp"
          ? manualFields.useAdvancedUrl
            ? Boolean(manualFields.rtspUrl.trim())
            : Boolean(manualFields.host.trim())
          : manualFields.useAdvancedUrl
            ? Boolean(manualFields.httpUrl.trim())
            : Boolean(manualFields.host.trim())

  const handleConnect = async () => {
    const built = buildCameraSource(connectionType, manualFields, cameraValue)
    if (!built) {
      toast.error("Complete the camera fields before connecting.")
      return
    }
    setValidating(true)
    try {
      const result = await validateCameraSource(built.source)
      if (!result.ok) {
        toast.error(result.message)
        return
      }
      onConnect({
        name,
        source: built.source,
        backend: built.backend,
      })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not verify camera")
    } finally {
      setValidating(false)
    }
  }

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
        One card per camera feed — like Home Assistant&apos;s one entity per camera. Adding a
        second camera does <span className="font-semibold">not</span> switch the live view on{" "}
        <span className="font-semibold">/live</span>. Use <span className="font-semibold">WiFi
        (RTSP)</span> for IP cameras (Reolink, Hikvision, Tapo, ONVIF). Rescan finds ONVIF devices
        on your LAN; then enter the camera username and password. Bluetooth cameras: use the
        manufacturer app&apos;s Wi‑Fi stream URL here.
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
          Connection type
        </p>
        <Select
          value={connectionType}
          onValueChange={(v) => setConnectionType(v as CameraConnectionType)}
        >
          <SelectTrigger
            className={cn(
              "w-full text-xs",
              isDark
                ? "border-white/10 bg-zinc-950/70 text-zinc-100"
                : "border-stone-200/80 bg-white/90 text-stone-900",
            )}
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent
            className={cn(
              isDark
                ? "border-white/10 bg-zinc-950 text-zinc-100"
                : "border-stone-200/80 bg-white text-stone-900",
            )}
          >
            {CAMERA_CONNECTION_TYPES.map((opt) => (
              <SelectItem key={opt.id} value={opt.id} className="text-xs">
                <span className="flex flex-col gap-0.5">
                  <span>{opt.label}</span>
                  <span className="text-[10px] font-normal text-zinc-500">{opt.hint}</span>
                </span>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {connectionType === "scan" ? (
        <div className="space-y-2">
          <p
            className={cn(
              "text-[10px] font-semibold uppercase tracking-[0.16em]",
              isDark ? "text-zinc-500" : "text-stone-500",
            )}
          >
            Scanned devices
          </p>
          <LiveCameraSelect
            className="w-full max-w-none"
            tone={isDark ? "dark" : "light"}
            pickerOnly
            forNewRoom={forNewRoom}
            excludeRoomId={excludeRoomId}
            initialValue={initialValue}
            onSelectValue={onCameraChange}
            onScanComplete={onScanComplete}
          />
          {scanSummary ? (
            <p className={cn("text-[12px] leading-relaxed", isDark ? "text-zinc-500" : "text-stone-500")}>
              {scanSummary}
            </p>
          ) : null}
        </div>
      ) : null}

      {connectionType === "phone_ip" ? (
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="space-y-1.5 sm:col-span-2">
            <Label className={cn("text-[12px]", isDark ? "text-zinc-400" : "text-stone-600")}>
              Phone IP address
            </Label>
            <Input
              value={manualFields.host}
              onChange={(e) => setManualFields((f) => ({ ...f, host: e.target.value }))}
              placeholder="192.168.1.10"
              className={cn(
                "font-mono text-sm",
                isDark ? "border-white/10 bg-black/40 text-zinc-100" : "border-stone-200/80 bg-white/90",
              )}
            />
          </div>
          <div className="space-y-1.5">
            <Label className={cn("text-[12px]", isDark ? "text-zinc-400" : "text-stone-600")}>
              Port
            </Label>
            <Input
              value={manualFields.port}
              onChange={(e) => setManualFields((f) => ({ ...f, port: e.target.value }))}
              placeholder="4747"
              className={cn(
                "font-mono text-sm",
                isDark ? "border-white/10 bg-black/40 text-zinc-100" : "border-stone-200/80 bg-white/90",
              )}
            />
          </div>
        </div>
      ) : null}

      {connectionType === "wifi_rtsp" || connectionType === "wifi_http" ? (
        <WifiCameraFields
          variant={variant}
          streamKind={connectionType === "wifi_rtsp" ? "rtsp" : "http"}
          fields={manualFields}
          discoveredWifi={discoveredWifi}
          onChange={setManualFields}
          onPickDiscoveredHost={applyDiscoveredHost}
        />
      ) : null}

      <Button
        type="button"
        disabled={!canConnect || connecting || validating}
        onClick={() => void handleConnect()}
        className={cn("gap-2", roomosUi.havenPrimaryBtn)}
      >
        {validating ? (
          <>
            <Loader2 className="size-4 animate-spin" aria-hidden />
            Checking camera…
          </>
        ) : (
          connectLabel
        )}
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
    mutationFn: async (payload: {
      name: string
      source: number | string
      backend: string
      draftId: string
    }) => {
      return createRoom({
        name: payload.name.trim() || "Room",
        camera: { source: payload.source, backend: payload.backend },
      })
    },
    onSuccess: (data, payload) => {
      syncRooms(data)
      setDrafts((prev) => prev.filter((d) => d.id !== payload.draftId))
      setDraftEdits((prev) => {
        const next = { ...prev }
        delete next[payload.draftId]
        return next
      })
      setExpandedId(null)
      toast.success("Camera connected")
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const saveRoom = useMutation({
    mutationFn: async (payload: {
      roomId: string
      name: string
      source: number | string
      backend: string
    }) => {
      return updateRoom(payload.roomId, {
        name: payload.name.trim() || undefined,
        camera: { source: payload.source, backend: payload.backend },
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
        One card per camera feed. Each phone or WiFi camera needs its own card — use{" "}
        <span className="font-semibold">Phone by IP</span> for DroidCam at a fixed address like
        192.168.1.10, or Rescan after opening the app on every phone.
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
                initialSource={room.camera.source}
                connectLabel={room.enabled ? "Save camera" : "Connect camera"}
                connecting={busy}
                onConnect={(payload) => {
                  setBusyId(room.id)
                  saveRoom.mutate(
                    {
                      roomId: room.id,
                      name: payload.name,
                      source: payload.source,
                      backend: payload.backend,
                    },
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
                onConnect={(payload) => {
                  setBusyId(draft.id)
                  create.mutate(
                    {
                      draftId: draft.id,
                      name: payload.name,
                      source: payload.source,
                      backend: payload.backend,
                    },
                    { onSettled: () => setBusyId(null) },
                  )
                }}
              />
            </CameraDeviceRow>
          )
        })}
      </div>
    </section>
  )
}
