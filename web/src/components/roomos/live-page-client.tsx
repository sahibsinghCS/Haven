"use client"

import { useEffect, useMemo } from "react"

import { LiveStageSkeleton } from "@/components/roomos/roomos-loading-states"
import { LiveVideoStage } from "@/components/roomos/live-video-stage"
import { useLiveEngineAutostart } from "@/hooks/use-live-engine"
import { useLiveInference, type LiveInferenceStatus } from "@/hooks/use-live-inference"
import { roomosUi } from "@/lib/roomos/roomos-ui"
import { useRoomOsAmbientStore } from "@/stores/roomos-store"
import { cn } from "@/lib/utils"

/** Live view wired to FastAPI + trained model snapshots (no mock unless API is down). */
export function LivePageClient() {
  const setPrimaryState = useRoomOsAmbientStore((s) => s.setPrimaryState)
  const engine = useLiveEngineAutostart(true)
  const live = useLiveInference()

  const snapshot = live.snapshot
  const dataSource = useMemo((): "ml" | null => (snapshot ? "ml" : null), [snapshot])

  useEffect(() => {
    if (!snapshot) return
    setPrimaryState(snapshot.primaryState)
  }, [snapshot, setPrimaryState])

  useEffect(() => {
    return () => setPrimaryState(null)
  }, [setPrimaryState])

  if (!snapshot && (live.status === "connecting" || engine.status === "starting")) {
    return <LiveStageSkeleton />
  }

  if (!snapshot) {
    return (
      <UnavailablePanel
        engineMessage={engine.message}
        liveMessage={live.message}
        engineStatus={engine.status}
        liveStatus={live.status}
      />
    )
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <LiveVideoStage
        snapshot={snapshot}
        dataSource={dataSource}
        engineStatus={engine.status}
        connectionStatus={live.status}
        statusMessage={live.message ?? engine.message}
      />
    </div>
  )
}

function UnavailablePanel({
  engineMessage,
  liveMessage,
  engineStatus,
  liveStatus,
}: {
  engineMessage: string | null
  liveMessage: string | null
  engineStatus: string
  liveStatus: LiveInferenceStatus
}) {
  const hint =
    liveMessage ??
    engineMessage ??
    (engineStatus === "starting"
      ? "Starting the inference engine…"
      : "Start the RoomOS API (python run.py in backend/) and refresh.")

  return (
    <div className="flex min-h-[40svh] flex-1 items-center justify-center px-4 py-12">
      <div
        className={cn(
          roomosUi.liveOverlayGlass,
          "max-w-md border-amber-500/20 p-6 text-sm text-amber-100",
        )}
      >
        <p className="font-medium text-zinc-100">Waiting for live model</p>
        <p className="mt-2 text-xs leading-relaxed text-amber-200/85">{hint}</p>
        <p className="mt-3 font-mono text-[10px] uppercase tracking-wider text-zinc-500">
          Connection: {liveStatus}
        </p>
      </div>
    </div>
  )
}
