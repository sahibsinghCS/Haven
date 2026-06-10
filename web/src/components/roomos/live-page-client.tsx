"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Camera, Loader2, Radio } from "lucide-react"

import { LiveCameraPowerButton } from "@/components/roomos/live-camera-power"
import { MoodBurstReviewPanel } from "@/components/roomos/moods/mood-burst-review-panel"
import { MoodCollectionOverlay } from "@/components/roomos/moods/mood-collection-overlay"
import { MoodTrainingProgress } from "@/components/roomos/moods/mood-training-progress"
import { LiveStageSkeleton } from "@/components/roomos/roomos-loading-states"
import { LiveVideoStage } from "@/components/roomos/live-video-stage"
import type { LiveInferenceStatus } from "@/hooks/use-live-inference"
import { useMoodMutations, useMoods } from "@/hooks/use-moods"
import type { BootPhase, ModelKind } from "@/lib/roomos/api-client"
import {
  moodCollectFromSearch,
  stripCollectQueryFromUrl,
} from "@/lib/roomos/mood-collect-start"
import { roomosUi } from "@/lib/roomos/roomos-ui"
import {
  consumeLiveStartIntent,
  hasLiveStartQuery,
} from "@/lib/roomos/live-session-start"
import { useLiveSessionStore } from "@/stores/live-session-store"
import { useMoodSessionStore } from "@/stores/mood-session-store"
import { useRoomOsAmbientStore } from "@/stores/roomos-store"
import { cn } from "@/lib/utils"

/** Live view: FastAPI snapshots + backend camera preview only. */
export function LivePageClient() {
  const setPrimaryState = useRoomOsAmbientStore((s) => s.setPrimaryState)
  const cameraEnabled = useLiveSessionStore((s) => s.cameraEnabled)
  const snapshot = useLiveSessionStore((s) => s.snapshot)
  const liveStatus = useLiveSessionStore((s) => s.liveStatus)
  const liveMessage = useLiveSessionStore((s) => s.liveMessage)
  const lastFeedbackEvent = useLiveSessionStore((s) => s.lastFeedbackEvent)
  const lastPreferencesEvent = useLiveSessionStore((s) => s.lastPreferencesEvent)
  const dismissFeedbackEvent = useLiveSessionStore((s) => s.dismissFeedbackEvent)
  const dismissPreferencesEvent = useLiveSessionStore((s) => s.dismissPreferencesEvent)
  const engineStatus = useLiveSessionStore((s) => s.engineStatus)
  const engineMessage = useLiveSessionStore((s) => s.engineMessage)
  const inferenceSource = useLiveSessionStore((s) => s.inferenceSource)
  const previewMeanLuma = useLiveSessionStore((s) => s.previewMeanLuma)
  const previewDark = useLiveSessionStore((s) => s.previewDark)
  const previewFit = useLiveSessionStore((s) => s.previewFit)
  const previewStreamLive = useLiveSessionStore((s) => s.previewStreamLive)
  const bootPhase = useLiveSessionStore((s) => s.bootPhase)
  const modelKind = useLiveSessionStore((s) => s.modelKind)
  const compatReport = useLiveSessionStore((s) => s.compatReport)
  const engineWasRunning = useLiveSessionStore((s) => s.engineWasRunning)
  const setCameraEnabled = useLiveSessionStore((s) => s.setCameraEnabled)

  const pendingCollectMoodId = useMoodSessionStore((s) => s.pendingCollectMoodId)
  const pendingCollectDurationSec = useMoodSessionStore((s) => s.pendingCollectDurationSec)
  const clearPendingCollect = useMoodSessionStore((s) => s.clearPendingCollect)
  const { data: moodsData } = useMoods()
  const { startCollection } = useMoodMutations()

  const [collectMoodId, setCollectMoodId] = useState<string | null>(null)
  const [collectDurationSec, setCollectDurationSec] = useState(300)
  const collectionStartedRef = useRef(false)

  useEffect(() => {
    const shouldStart =
      hasLiveStartQuery(window.location.search) || consumeLiveStartIntent()
    const { moodId, durationSec } = moodCollectFromSearch(window.location.search)
    if (moodId) {
      setCollectMoodId(moodId)
      setCollectDurationSec(durationSec)
      setCameraEnabled(true)
    } else if (pendingCollectMoodId) {
      setCollectMoodId(pendingCollectMoodId)
      setCollectDurationSec(pendingCollectDurationSec)
    }
    if (shouldStart || moodId) {
      setCameraEnabled(true)
      if (hasLiveStartQuery(window.location.search) || moodId) {
        stripCollectQueryFromUrl()
      }
    }
  }, [setCameraEnabled, pendingCollectMoodId, pendingCollectDurationSec])

  useEffect(() => {
    if (!collectMoodId || collectionStartedRef.current) return
    if (engineStatus !== "running" || liveStatus !== "live") return
    if (startCollection.isPending) return

    collectionStartedRef.current = true
    void startCollection
      .mutateAsync({ moodId: collectMoodId, durationSec: collectDurationSec })
      .then(() => {
        clearPendingCollect()
      })
      .catch(() => {
        collectionStartedRef.current = false
      })
  }, [
    collectMoodId,
    collectDurationSec,
    engineStatus,
    liveStatus,
    startCollection,
    clearPendingCollect,
  ])

  const activeCollection =
    moodsData?.collection?.active && moodsData.collection.moodId
      ? moodsData.collection.moodId
      : collectMoodId

  const handleCollectionEnded = useCallback(() => {
    if (!collectMoodId) return
    // Keep overlay visible via moods poll; user can review or train from overlay.
  }, [collectMoodId])

  useEffect(() => {
    document.documentElement.classList.add("live-immersive")
    return () => document.documentElement.classList.remove("live-immersive")
  }, [])

  useEffect(() => {
    if (!snapshot) return
    setPrimaryState(snapshot.primaryState)
  }, [snapshot, setPrimaryState])

  useEffect(() => {
    return () => setPrimaryState(null)
  }, [setPrimaryState])

  const coldStart = !engineWasRunning && !snapshot

  const booting = useMemo(() => {
    if (!cameraEnabled) return false
    if (engineStatus === "error" || liveStatus === "error") return false
    if (snapshot && bootPhase === "streaming") return false
    if (!snapshot) {
      return (
        engineStatus === "starting" ||
        engineStatus === "running" ||
        liveStatus === "connecting"
      )
    }
    if (!coldStart && engineStatus === "running" && bootPhase === "streaming") {
      return false
    }
    return (
      engineStatus === "starting" ||
      (coldStart && liveStatus === "connecting") ||
      (coldStart && engineStatus === "running" && liveStatus !== "no-data")
    )
  }, [cameraEnabled, snapshot, engineStatus, liveStatus, coldStart, bootPhase])

  if (!cameraEnabled) {
    return (
      <div className="relative flex min-h-0 flex-1 flex-col">
        <LiveStageSkeleton />
        <div className="absolute left-3 top-3 z-30 sm:left-4 sm:top-4">
          <LiveCameraPowerButton />
        </div>
        <div className="absolute inset-0 z-20 flex items-center justify-center p-6">
          <div
            className={cn(
              roomosUi.liveOverlayGlass,
              "max-w-md border-white/10 px-6 py-8 text-center shadow-2xl",
            )}
            role="status"
          >
            <p className="text-base font-medium text-zinc-50">Live view is off</p>
            <p className="mt-2 text-sm leading-relaxed text-zinc-400">
              Press the power button or choose Get Started from the home page to connect your
              camera and start inference.
            </p>
          </div>
        </div>
      </div>
    )
  }

  if (booting) {
    return (
      <LiveConnectingPanel
        engineStatus={engineStatus}
        liveStatus={liveStatus}
        inferenceSource={inferenceSource}
        bootPhase={bootPhase}
        modelKind={modelKind}
        previewMeanLuma={previewMeanLuma}
        snapshotPresent={snapshot !== null}
      />
    )
  }

  if (!snapshot) {
    return (
      <UnavailablePanel
        engineMessage={engineMessage}
        liveMessage={liveMessage}
        engineStatus={engineStatus}
        liveStatus={liveStatus}
        compatReport={compatReport}
      />
    )
  }

  return (
    <div className="relative flex h-full min-h-0 flex-1 flex-col overflow-hidden">
      <div className="absolute left-3 top-3 z-30 sm:left-4 sm:top-4">
        <LiveCameraPowerButton />
      </div>
      {activeCollection ? (
        <MoodCollectionOverlay
          moodId={activeCollection}
          previewDark={previewDark}
          onCollectionEnded={handleCollectionEnded}
        />
      ) : null}
      <LiveVideoStage
        snapshot={snapshot}
        engineStatus={engineStatus}
        previewDark={previewDark}
        previewMeanLuma={previewMeanLuma}
        previewFit={previewFit}
        previewResumeLive={previewStreamLive || bootPhase === "streaming"}
        modelKind={modelKind}
        feedbackEvent={lastFeedbackEvent}
        onDismissFeedbackEvent={dismissFeedbackEvent}
        preferencesEvent={lastPreferencesEvent}
        onDismissPreferencesEvent={dismissPreferencesEvent}
      />
      <MoodBurstReviewPanel />
      <MoodTrainingProgress />
    </div>
  )
}

function LiveConnectingPanel({
  engineStatus,
  liveStatus,
  inferenceSource,
  bootPhase,
  modelKind,
  previewMeanLuma,
  snapshotPresent,
}: {
  engineStatus: string
  liveStatus: LiveInferenceStatus
  inferenceSource: string | null
  bootPhase: BootPhase
  modelKind: ModelKind
  previewMeanLuma: number | null
  snapshotPresent: boolean
}) {
  const step =
    bootPhase === "opening_camera"
      ? "Opening camera…"
      : bootPhase === "warming_up"
        ? "Loading first burst (OpenCLIP)…"
        : bootPhase === "starting"
          ? "Starting inference engine…"
          : engineStatus === "starting"
            ? "Starting inference engine and camera…"
            : liveStatus === "connecting"
              ? "Waiting for first room-state prediction…"
              : "Almost ready…"

  const detail =
    bootPhase === "warming_up"
      ? "First 2.5-second burst is being captured and pushed through OpenCLIP + the XGBoost head. This takes ~10–25 s the first time."
      : bootPhase === "opening_camera"
        ? "Negotiating a video format with the OS. Close Teams/Zoom/OBS if this hangs."
        : "Burst classifier runs on this machine. The video preview is the same camera the model uses."

  return (
    <div className="relative flex min-h-0 flex-1 flex-col">
      <LiveStageSkeleton />
      <div className="absolute left-3 top-3 z-30 sm:left-4 sm:top-4">
        <LiveCameraPowerButton />
      </div>
      <div className="absolute inset-0 z-20 flex items-center justify-center p-6">
        <div
          className={cn(
            roomosUi.liveOverlayGlass,
            "max-w-md border-teal-500/20 px-6 py-8 text-center shadow-2xl",
          )}
          role="status"
          aria-live="polite"
        >
          <Loader2 className="mx-auto size-8 animate-spin text-teal-300/90" aria-hidden />
          <p className="mt-4 text-base font-medium text-zinc-50">{step}</p>
          <p className="mt-2 text-sm leading-relaxed text-zinc-400">{detail}</p>
          {inferenceSource ? (
            <p className="mt-3 font-mono text-[11px] text-zinc-500">{inferenceSource}</p>
          ) : null}
          {modelKind === "bootstrap" ? (
            <p className="mt-3 rounded-lg border border-amber-400/30 bg-amber-950/40 px-3 py-2 text-[11px] leading-relaxed text-amber-200/90">
              Loaded the bootstrap demo model (synthetic stills). Run{" "}
              <code className="rounded bg-black/30 px-1 py-0.5 font-mono">npm run train:images</code>{" "}
              with photos of your room for accurate live predictions.
            </p>
          ) : null}
          <p className="mt-4 break-all rounded-md border border-white/[0.06] bg-black/30 px-2 py-1.5 font-mono text-[10px] leading-snug text-zinc-500">
            engine={engineStatus} · live={liveStatus} · boot={bootPhase}
            {" · "}snapshot={snapshotPresent ? "yes" : "no"}
            {typeof previewMeanLuma === "number" ? ` · luma=${previewMeanLuma.toFixed(1)}` : ""}
          </p>
          <div className="mt-5 flex flex-wrap justify-center gap-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-500">
            <span
              className={cn(
                "inline-flex items-center gap-1 rounded-full border px-2 py-1",
                bootPhase === "warming_up" || bootPhase === "streaming"
                  ? "border-emerald-400/40 text-emerald-200"
                  : "border-white/10",
              )}
            >
              <Camera className="size-3" aria-hidden />
              Camera
            </span>
            <span
              className={cn(
                "inline-flex items-center gap-1 rounded-full border px-2 py-1",
                bootPhase === "streaming"
                  ? "border-emerald-400/40 text-emerald-200"
                  : "border-white/10",
              )}
            >
              <Radio className="size-3" aria-hidden />
              Model
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}

function UnavailablePanel({
  engineMessage,
  liveMessage,
  engineStatus,
  liveStatus,
  compatReport,
}: {
  engineMessage: string | null
  liveMessage: string | null
  engineStatus: string
  liveStatus: LiveInferenceStatus
  compatReport?: import("@/lib/roomos/api-client").CompatReport | null
}) {
  const isCompatFailure =
    Boolean(compatReport?.mismatches?.length) ||
    (engineMessage?.toLowerCase().includes("compatibility") ?? false)
  const needsModel =
    [engineMessage, liveMessage].some(
      (m) => m && (m.toLowerCase().includes("model") || m.toLowerCase().includes("bundle")),
    )

  const title = isCompatFailure
    ? "Model not ready for live inference"
    : needsModel
      ? "Train a model to start the demo"
      : engineStatus === "error"
        ? "Inference engine could not start"
        : "Cannot reach RoomOS API"

  const hint = isCompatFailure
    ? (engineMessage ?? "Train/serve configs do not match.")
    : needsModel
      ? "From repo root: npm run setup:model then npm run demo"
      : (liveMessage ?? engineMessage ?? "Run npm run demo from the repo root.")

  return (
    <div className="relative flex min-h-[50svh] flex-1 items-center justify-center px-4 py-16 2xl:py-24">
      <div className="absolute left-3 top-3 z-30 sm:left-4 sm:top-4">
        <LiveCameraPowerButton />
      </div>
      <div
        className={cn(
          roomosUi.liveOverlayGlass,
          "w-full max-w-xl border-amber-500/20 p-8 text-sm text-amber-100 2xl:max-w-2xl 2xl:p-10",
        )}
        role="alert"
      >
        <p className="text-lg font-semibold text-zinc-50">{title}</p>
        <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-amber-200/90">{hint}</p>

        {isCompatFailure && compatReport?.mismatches?.length ? (
          <ul className="mt-4 max-h-40 space-y-2 overflow-y-auto rounded-lg border border-rose-400/20 bg-rose-950/40 p-3 text-[11px] text-rose-100/90">
            {compatReport.mismatches.slice(0, 4).map((m) => (
              <li key={`${m.category}-${m.field}`}>
                <span className="font-semibold uppercase text-rose-200/80">{m.category}</span>:{" "}
                {m.field}
              </li>
            ))}
          </ul>
        ) : null}

        <ol className="mt-6 space-y-2 border-t border-white/[0.08] pt-5 text-left text-[13px] text-zinc-300">
          <li>
            <span className="font-semibold text-zinc-100">1.</span> Terminal:{" "}
            <code className="rounded bg-black/30 px-1.5 py-0.5 font-mono text-[12px]">npm run demo</code>
          </li>
          <li>
            <span className="font-semibold text-zinc-100">2.</span> Open{" "}
            <code className="rounded bg-black/30 px-1.5 py-0.5 font-mono text-[12px]">/live</code>{" "}
            and allow the webcam if prompted
          </li>
          <li>
            <span className="font-semibold text-zinc-100">3.</span> First prediction may take 15–30s
            (OpenCLIP load)
          </li>
        </ol>

        <p className="mt-5 font-mono text-[10px] uppercase tracking-wider text-zinc-600">
          API {liveStatus} · engine {engineStatus}
        </p>
      </div>
    </div>
  )
}
