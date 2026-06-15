"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Loader2, Power } from "lucide-react"

import { HavenModeBadge } from "@/components/roomos/haven-mode-badge"
import { LiveFailurePanel } from "@/components/roomos/live-failure-panel"
import { HavenStatusChips, HavenSurfaceState } from "@/components/roomos/haven-surface-state"
import { bootPhaseCopy } from "@/lib/roomos/haven-system-state"
import { LiveBootStepper } from "@/components/roomos/live-boot-stepper"

import { HavenSetupWizard } from "@/components/roomos/setup/haven-setup-wizard"
import { RoomViewToggle, RoomsGallery } from "@/components/roomos/rooms-gallery"
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
import { isCameraRelatedMessage } from "@/lib/roomos/haven-system-state"
import { roomosUi } from "@/lib/roomos/roomos-ui"
import {
  consumeLiveStartIntent,
  hasLiveStartQuery,
} from "@/lib/roomos/live-session-start"
import {
  isSetupMarkedComplete,
  markSetupComplete,
} from "@/lib/roomos/setup-session"
import { Button } from "@/components/ui/button"
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
  const cameraSetupRequired = useLiveSessionStore((s) => s.cameraSetupRequired)
  const setCameraEnabled = useLiveSessionStore((s) => s.setCameraEnabled)
  const setEngineWasRunning = useLiveSessionStore((s) => s.setEngineWasRunning)
  const rooms = useLiveSessionStore((s) => s.rooms)
  // Default false so SSR matches the first client paint (localStorage is client-only).
  const [setupWizardOpen, setSetupWizardOpen] = useState(false)
  const activeRoomId = useLiveSessionStore((s) => s.activeRoomId)
  const [liveView, setLiveView] = useState<"gallery" | "focus">("focus")
  const prevActiveRoomRef = useRef<string | null>(null)

  const pendingCollectMoodId = useMoodSessionStore((s) => s.pendingCollectMoodId)
  const pendingCollectDurationSec = useMoodSessionStore((s) => s.pendingCollectDurationSec)
  const pendingCollectRoomIds = useMoodSessionStore((s) => s.pendingCollectRoomIds)
  const clearPendingCollect = useMoodSessionStore((s) => s.clearPendingCollect)
  const { data: moodsData } = useMoods()
  const { startCollection } = useMoodMutations()

  const [collectMoodId, setCollectMoodId] = useState<string | null>(null)
  const [collectDurationSec, setCollectDurationSec] = useState(300)
  const [moodCollectNeedsCamera, setMoodCollectNeedsCamera] = useState(false)
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
      setSetupWizardOpen(true)
      if (hasLiveStartQuery(window.location.search) || moodId) {
        stripCollectQueryFromUrl()
      }
    } else if (!isSetupMarkedComplete()) {
      setSetupWizardOpen(true)
    }
  }, [pendingCollectMoodId, pendingCollectDurationSec, setCameraEnabled])

  useEffect(() => {
    if (engineStatus === "running" && liveStatus === "live") {
      setMoodCollectNeedsCamera(false)
    }
  }, [engineStatus, liveStatus])

  useEffect(() => {
    if (!collectMoodId || collectionStartedRef.current) return
    if (engineStatus === "camera_setup" || cameraSetupRequired) return
    if (engineStatus !== "running" || liveStatus !== "live") return
    if (startCollection.isPending) return

    collectionStartedRef.current = true
    void startCollection
      .mutateAsync({
        moodId: collectMoodId,
        durationSec: collectDurationSec,
        roomIds: pendingCollectRoomIds.length > 0 ? pendingCollectRoomIds : undefined,
      })
      .then(() => {
        clearPendingCollect()
        setMoodCollectNeedsCamera(false)
      })
      .catch((err: Error) => {
        collectionStartedRef.current = false
        if (err.message.toLowerCase().includes("camera")) {
          setMoodCollectNeedsCamera(true)
        }
      })
  }, [
    collectMoodId,
    collectDurationSec,
    engineStatus,
    liveStatus,
    cameraSetupRequired,
    startCollection,
    clearPendingCollect,
    pendingCollectRoomIds,
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
    if (snapshot) markSetupComplete()
  }, [snapshot?.capturedAt])

  const handleSetupGoLive = useCallback(() => {
    setCameraEnabled(true)
    setEngineWasRunning(true)
    setSetupWizardOpen(false)
  }, [setCameraEnabled, setEngineWasRunning])

  /** Follow presence: when the active room changes, show Focus on that feed. */
  useEffect(() => {
    if (!activeRoomId) return
    if (
      prevActiveRoomRef.current &&
      prevActiveRoomRef.current !== activeRoomId &&
      rooms.length > 1
    ) {
      setLiveView("focus")
    }
    prevActiveRoomRef.current = activeRoomId
  }, [activeRoomId, rooms.length])

  useEffect(() => {
    return () => setPrimaryState(null)
  }, [setPrimaryState])

  const coldStart = !engineWasRunning && !snapshot

  const needsCameraSetup = useMemo(() => {
    if (!cameraEnabled) return false
    if (cameraSetupRequired || engineStatus === "camera_setup" || bootPhase === "camera_setup") {
      return true
    }
    if (moodCollectNeedsCamera) return true
    return engineStatus === "error" && isCameraRelatedMessage(engineMessage)
  }, [
    cameraEnabled,
    cameraSetupRequired,
    engineStatus,
    bootPhase,
    moodCollectNeedsCamera,
    engineMessage,
  ])

  const booting = useMemo(() => {
    if (!cameraEnabled) return false
    if (needsCameraSetup) return false
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
  }, [cameraEnabled, needsCameraSetup, snapshot, engineStatus, liveStatus, coldStart, bootPhase])

  const showSetupWizard =
    setupWizardOpen &&
    !snapshot &&
    (!cameraEnabled || needsCameraSetup || rooms.length === 0)

  if (!cameraEnabled && !showSetupWizard) {
    return (
      <div className="relative flex min-h-0 flex-1 flex-col">
        <LiveStageSkeleton variant="idle" label="Camera off" />
        <div className="absolute left-3 top-3 z-30 sm:left-4 sm:top-4">
          <LiveCameraPowerButton />
        </div>
        <div className="absolute inset-0 z-20 flex items-center justify-center p-6">
          <HavenSurfaceState
            variant="dark"
            tone="empty"
            icon={<Power className="size-6 text-zinc-400" />}
            eyebrow={<HavenModeBadge mode="camera_off" size="md" />}
            title="Live view is off"
            description="Nothing is inferred or uploaded until you turn the camera on. Run guided setup for room, camera, and device checks — or use the power button to go straight to live."
            footer={
              <>
                <HavenStatusChips
                  variant="dark"
                  items={[
                    { label: "Camera off", active: true },
                    { label: "Model idle" },
                  ]}
                />
                <Button
                  type="button"
                  className={cn("w-full max-w-xs", roomosUi.havenPrimaryBtn, "text-white")}
                  onClick={() => setSetupWizardOpen(true)}
                >
                  Run guided setup
                </Button>
              </>
            }
          />
        </div>
      </div>
    )
  }

  if (showSetupWizard) {
    return (
      <div className="relative flex min-h-0 flex-1 flex-col">
        <LiveStageSkeleton variant="booting" label="Room setup" />
        <div className="absolute left-3 top-3 z-30 sm:left-4 sm:top-4">
          <LiveCameraPowerButton />
        </div>
        <div className="absolute inset-0 z-20 flex items-start justify-center overflow-y-auto p-4 pt-16 sm:p-6 sm:pt-20">
          <HavenSetupWizard
            variant="live"
            onGoLive={handleSetupGoLive}
            onDismiss={() => setSetupWizardOpen(false)}
          />
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
    const cameraError =
      engineStatus === "error" &&
      [engineMessage, liveMessage].some((m) => isCameraRelatedMessage(m))
    if (cameraError) {
      return (
        <div className="relative flex min-h-0 flex-1 flex-col">
          <LiveStageSkeleton />
          <div className="absolute left-3 top-3 z-30 sm:left-4 sm:top-4">
            <LiveCameraPowerButton />
          </div>
          <div className="absolute inset-0 z-20 flex items-start justify-center overflow-y-auto p-4 pt-16 sm:p-6 sm:pt-20">
            <HavenSetupWizard variant="live" onGoLive={handleSetupGoLive} />
          </div>
        </div>
      )
    }
    return (
      <LiveFailurePanel
        engineMessage={engineMessage}
        liveMessage={liveMessage}
        engineStatus={engineStatus}
        liveStatus={liveStatus}
        compatReport={compatReport}
      />
    )
  }

  const showGallery = liveView === "gallery" && rooms.length > 1

  return (
    <div className="relative flex h-full min-h-0 flex-1 flex-col overflow-hidden">
      <div className="absolute left-3 top-3 z-30 flex flex-wrap items-center gap-2 sm:left-4 sm:top-4">
        <LiveCameraPowerButton />
      </div>
      {activeCollection ? (
        <MoodCollectionOverlay
          moodId={activeCollection}
          previewDark={previewDark}
          onCollectionEnded={handleCollectionEnded}
        />
      ) : null}
      {rooms.length > 1 ? (
        <div className="absolute right-3 top-3 z-30 sm:right-4 sm:top-4">
          <RoomViewToggle view={liveView} onViewChange={setLiveView} />
        </div>
      ) : null}
      {showGallery ? (
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden p-3 pt-14 sm:p-4 sm:pt-16">
          <RoomsGallery snapshot={snapshot} onFocus={() => setLiveView("focus")} />
        </div>
      ) : (
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
          onFocusRoom={rooms.length > 1 ? () => setLiveView("gallery") : undefined}
        />
      )}
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
  const { title: step, description: detail } = bootPhaseCopy(
    bootPhase,
    engineStatus,
    liveStatus,
  )

  return (
    <div className="relative flex min-h-0 flex-1 flex-col">
      <LiveStageSkeleton variant="booting" label="Booting live inference" />
      <div className="absolute left-3 top-3 z-30 sm:left-4 sm:top-4">
        <LiveCameraPowerButton />
      </div>
      <div className="absolute inset-0 z-20 flex items-center justify-center p-6">
        <HavenSurfaceState
          variant="dark"
          tone="loading"
          icon={<Loader2 className="size-6 animate-spin text-teal-300/90" />}
          eyebrow={<HavenModeBadge mode="booting" size="md" />}
          title={step}
          description={detail}
          ariaLive="polite"
          footer={
            <>
              <LiveBootStepper bootPhase={bootPhase} snapshotPresent={snapshotPresent} />
              {inferenceSource ? (
                <p className="font-mono text-[10px] text-zinc-500">{inferenceSource}</p>
              ) : null}
              {modelKind === "bootstrap" ? (
                <div className="flex max-w-sm flex-col items-center gap-2">
                  <HavenModeBadge mode="demo_model" size="md" />
                  <p className="text-left text-[11px] leading-relaxed text-amber-200/90">
                    Bootstrap weights load during boot. Predictions are not trained on your room
                    until you run{" "}
                    <code className="rounded bg-black/30 px-1 py-0.5 font-mono">npm run train:images</code>.
                  </p>
                </div>
              ) : null}
              <p className="max-w-sm break-all rounded-md border border-white/[0.06] bg-black/30 px-2 py-1.5 font-mono text-[10px] leading-snug text-zinc-500">
                engine={engineStatus} · live={liveStatus} · boot={bootPhase}
                {" · "}snapshot={snapshotPresent ? "yes" : "no"}
                {typeof previewMeanLuma === "number" ? ` · luma=${previewMeanLuma.toFixed(1)}` : ""}
              </p>
              <HavenStatusChips
                variant="dark"
                items={[
                  {
                    label: "Camera",
                    active: bootPhase === "warming_up" || bootPhase === "streaming",
                  },
                  { label: "Model", active: bootPhase === "streaming" },
                ]}
              />
            </>
          }
        />
      </div>
    </div>
  )
}

