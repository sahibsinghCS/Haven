"use client"

import { useState } from "react"
import { Loader2, Power } from "lucide-react"
import { toast } from "sonner"

import { stopEngine } from "@/lib/roomos/api-client"
import { cn } from "@/lib/utils"
import { useLiveSessionStore } from "@/stores/live-session-store"
import { useRoomOsAmbientStore } from "@/stores/roomos-store"

export function LiveCameraPowerButton({ className }: { className?: string }) {
  const [busy, setBusy] = useState(false)
  const cameraEnabled = useLiveSessionStore((s) => s.cameraEnabled)
  const setCameraEnabled = useLiveSessionStore((s) => s.setCameraEnabled)
  const setEngineWasRunning = useLiveSessionStore((s) => s.setEngineWasRunning)
  const setPreviewStreamLive = useLiveSessionStore((s) => s.setPreviewStreamLive)
  const resetForCameraOff = useLiveSessionStore((s) => s.resetForCameraOff)
  const bumpCameraRefresh = useRoomOsAmbientStore((s) => s.bumpCameraRefresh)

  const isOn = cameraEnabled

  const toggle = async () => {
    if (busy) return
    setBusy(true)
    try {
      if (isOn) {
        await stopEngine()
        setCameraEnabled(false)
        setEngineWasRunning(false)
        setPreviewStreamLive(false)
        resetForCameraOff()
        toast.message("Camera stopped")
      } else {
        setCameraEnabled(true)
        setEngineWasRunning(true)
        setPreviewStreamLive(false)
        bumpCameraRefresh()
        toast.success("Camera starting…")
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Camera power toggle failed")
    } finally {
      setBusy(false)
    }
  }

  return (
    <button
      type="button"
      onClick={() => void toggle()}
      disabled={busy}
      aria-pressed={isOn}
      aria-label={isOn ? "Stop inference camera" : "Start inference camera"}
      title={isOn ? "Stop camera" : "Start camera"}
      className={cn(
        "inline-flex size-10 items-center justify-center rounded-full border backdrop-blur-md transition",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-400/50 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950",
        isOn
          ? "border-teal-400/35 bg-teal-950/80 text-teal-100 hover:bg-teal-900/90"
          : "border-white/15 bg-zinc-950/80 text-zinc-300 hover:bg-zinc-900/90 hover:text-zinc-50",
        className,
      )}
    >
      {busy ? (
        <Loader2 className="size-4 animate-spin" aria-hidden />
      ) : (
        <Power className="size-4" strokeWidth={2.25} aria-hidden />
      )}
    </button>
  )
}
