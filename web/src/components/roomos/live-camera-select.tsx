"use client"

import { useCallback, useEffect, useState } from "react"
import { Camera, Loader2, RefreshCw } from "lucide-react"
import { toast } from "sonner"

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  fetchCameras,
  fetchEngineStatus,
  setCamera,
  type CameraOption,
} from "@/lib/roomos/api-client"
import { formatCameraDeviceLabel } from "@/lib/roomos/format-camera-device-label"
import { useRoomOsAmbientStore } from "@/stores/roomos-store"
import { cn } from "@/lib/utils"

function cameraValue(cam: CameraOption): string {
  return `${cam.source}::${cam.backend}`
}

function parseCameraValue(value: string): { source: number | string; backend: string } {
  const [sourceRaw, backend] = value.split("::")
  const source =
    sourceRaw !== undefined && /^\d+$/.test(sourceRaw) ? Number(sourceRaw) : sourceRaw
  return { source: source ?? 0, backend: backend || "auto" }
}

export function LiveCameraSelect({
  onChanged,
  onSelectValue,
  pickerOnly = false,
  forNewRoom = false,
  excludeRoomId,
  initialValue,
  tone = "dark",
  className,
}: {
  onChanged?: () => void
  /** When ``pickerOnly``, called with value instead of POST /camera. */
  onSelectValue?: (value: string) => void
  pickerOnly?: boolean
  /** Hide cameras already assigned to other rooms (multi-DroidCam setup). */
  forNewRoom?: boolean
  /** When editing a room, keep its camera in the list but hide other rooms' picks. */
  excludeRoomId?: string
  initialValue?: string
  tone?: "dark" | "light"
  className?: string
}) {
  const [loading, setLoading] = useState(false)
  const [scanned, setScanned] = useState(false)
  const [busy, setBusy] = useState(false)
  const [cameras, setCameras] = useState<CameraOption[]>([])
  const [selected, setSelected] = useState<string | undefined>(undefined)
  const [currentLabel, setCurrentLabel] = useState("Camera")
  const bumpCameraRefresh = useRoomOsAmbientStore((s) => s.bumpCameraRefresh)

  useEffect(() => {
    if (initialValue) {
      setSelected(initialValue)
      return
    }
    let cancelled = false
    ;(async () => {
      try {
        const st = await fetchEngineStatus()
        if (cancelled) return
        const src = st.video_source
        const backend = st.video_backend ?? "auto"
        if (src !== undefined && src !== null) {
          setSelected(`${src}::${backend}`)
        }
        if (st.inference_source) {
          setCurrentLabel(st.inference_source)
        }
      } catch {
 /* API not up yet. full scan on open will surface errors */
      }
    })()
    return () => {
      cancelled = true
    }
  }, [initialValue])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchCameras(undefined, {
        forNewRoom: pickerOnly && forNewRoom,
        excludeRoomId,
      })
      setCameras(data.cameras)
      setScanned(true)
      if (pickerOnly && forNewRoom && !selected) {
        const autoPick =
          data.cameras.find((c) => c.kind === "droidcam_auto") ??
          data.cameras.find((c) => c.available)
        if (autoPick) {
          const value = cameraValue(autoPick)
          setSelected(value)
          setCurrentLabel(formatCameraDeviceLabel(autoPick.label))
          onSelectValue?.(value)
        }
      }
      const match = data.cameras.find((c) => c.source === data.current.source)
      if (match) {
        setSelected(cameraValue(match))
        setCurrentLabel(formatCameraDeviceLabel(match.label))
      } else {
        setSelected(`${data.current.source}::${data.current.backend}`)
        setCurrentLabel(formatCameraDeviceLabel(data.current.label))
      }
    } catch (err) {
      toast.error(
 err instanceof Error ? err.message : "Could not list cameras. is the API running?",
      )
    } finally {
      setLoading(false)
    }
  }, [excludeRoomId, forNewRoom, onSelectValue, pickerOnly, selected])

  const onOpenChange = (open: boolean) => {
    if (open && !scanned && !loading) {
      void load()
    }
  }

  const onSelect = async (value: string) => {
    if (busy || value === selected) return
    if (pickerOnly) {
      setSelected(value)
      const cam = cameras.find((c) => cameraValue(c) === value)
      if (cam) {
        setCurrentLabel(formatCameraDeviceLabel(cam.label))
      }
      onSelectValue?.(value)
      return
    }
    const { source, backend } = parseCameraValue(value)
    setBusy(true)
    try {
      await setCamera({ source, backend })
      setSelected(value)
      const cam = cameras.find((c) => cameraValue(c) === value)
      if (cam) {
        setCurrentLabel(formatCameraDeviceLabel(cam.label))
      }
 toast.success("Camera switched. reconnecting preview…")
      bumpCameraRefresh()
      onChanged?.()
      onSelectValue?.(value)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not switch camera")
    } finally {
      setBusy(false)
    }
  }

  const noneAvailable = scanned && !loading && cameras.length === 0

  return (
    <div
      className={cn("flex shrink-0 items-center gap-1.5", className)}
      role="group"
      aria-label="Webcam selection"
    >
      <Camera
        className={cn("size-3.5 shrink-0", tone === "light" ? "text-stone-500" : "text-zinc-500")}
        aria-hidden
      />
      <Select
        value={selected}
        onValueChange={(v) => void onSelect(v)}
        onOpenChange={onOpenChange}
        disabled={busy || (scanned && noneAvailable)}
      >
        <SelectTrigger
          size="sm"
          className={cn(
            "h-8 min-w-[9.5rem] max-w-[14rem] text-xs",
            tone === "light"
              ? "border-stone-200/80 bg-white/90 text-stone-900 hover:bg-white"
              : "border-white/10 bg-zinc-950/70 text-zinc-100 hover:bg-zinc-900/80",
          )}
          aria-label="Select webcam"
        >
          {busy ? (
            <span className="flex items-center gap-1.5 text-zinc-400">
              <Loader2 className="size-3 animate-spin" aria-hidden />
              Switching…
            </span>
          ) : loading ? (
            <span className="flex items-center gap-1.5 text-zinc-400">
              <Loader2 className="size-3 animate-spin" aria-hidden />
              Scanning…
            </span>
          ) : (
            <SelectValue
              placeholder={noneAvailable ? "No cameras found" : currentLabel}
            />
          )}
        </SelectTrigger>
        <SelectContent
          className={cn(
            "max-h-72",
            tone === "light"
              ? "border-stone-200/80 bg-white text-stone-900"
              : "border-white/10 bg-zinc-950 text-zinc-100",
          )}
        >
          {!scanned && !loading ? (
            <p className="px-2 py-3 text-[11px] text-zinc-500">Opening list scans devices…</p>
          ) : null}
          {noneAvailable ? (
            <p className="px-2 py-3 text-[11px] leading-relaxed text-zinc-500">
 No cameras found. plug in a USB webcam and tap rescan.
            </p>
          ) : null}
          {cameras.map((cam) => {
            const label = formatCameraDeviceLabel(cam.label)
            const dark =
              cam.available &&
              cam.mean_luma != null &&
              cam.mean_luma < 20
            return (
              <SelectItem
                key={cameraValue(cam)}
                value={cameraValue(cam)}
                disabled={!cam.available}
                className="text-xs"
              >
                <span className="flex flex-col gap-0.5">
                  <span>{label}</span>
                  <span className="text-[10px] font-normal text-zinc-500">
                    {!cam.available
 ? "Not available. try another device"
                      : cam.kind === "droidcam" || cam.kind === "droidcam_auto"
                        ? cam.kind === "droidcam_auto"
 ? "Next free phone on WiFi (one per room)"
                          : "Phone stream · HTTP"
                        : dark
                          ? `Index ${cam.index} · very dark`
                          : `Index ${cam.index} · ${cam.backend}`}
                  </span>
                </span>
              </SelectItem>
            )
          })}
        </SelectContent>
      </Select>
      <button
        type="button"
        onClick={() => void load()}
        disabled={loading || busy}
        className={cn(
          "inline-flex h-8 w-8 items-center justify-center rounded-lg border transition-colors disabled:opacity-50",
          tone === "light"
            ? "border-stone-200/80 bg-white/90 text-stone-500 hover:bg-white hover:text-stone-800"
            : "border-white/10 bg-zinc-950/70 text-zinc-400 hover:bg-zinc-900/80 hover:text-zinc-200",
        )}
        aria-label="Rescan cameras"
      >
        <RefreshCw className={cn("size-3.5", loading && "animate-spin")} aria-hidden />
      </button>
    </div>
  )
}
