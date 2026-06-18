"use client"



import { useMemo, useState } from "react"



import { PreferencesTelegramBanner } from "@/components/roomos/preferences-telegram-banner"

import { TelegramCorrectionBanner } from "@/components/roomos/telegram-correction-banner"

import { LiveExplainPanel } from "@/components/roomos/live-explain-panel"

import { LivePresenceRail } from "@/components/roomos/live-presence-rail"

import { PrimaryStateOverlay } from "@/components/roomos/primary-state-overlay"

import { useInferenceCameraPreview } from "@/hooks/use-inference-camera-preview"

import type { LiveEngineHookStatus } from "@/hooks/use-live-engine"

import type { ModelKind } from "@/lib/roomos/api-client"

import {

  findRunnerUp,

  isUncertainRead,

} from "@/lib/roomos/live-confidence-utils"

import { formatAppliedSceneSummary } from "@/lib/roomos/format-applied-scene"
import { resolveInferenceDisplayMode } from "@/lib/roomos/haven-system-state"

import { roomStateLabel } from "@/lib/roomos/state-meta"

import { useLiveSessionStore } from "@/stores/live-session-store"

import type { LiveFeedbackEvent } from "@/types/feedback-event"

import type { LivePreferencesEvent } from "@/types/preferences-event"

import type { LiveInferenceSnapshot } from "@/types/roomos"

import { cn } from "@/lib/utils"

import { roomosUi } from "@/lib/roomos/roomos-ui"



/**

 * Immersive live: camera fills the viewport; status rail + inspectable HUD.

 */

export function LiveVideoStage({

  snapshot,

  engineStatus = "running",

  previewDark = false,

  previewFit = "contain",

  previewResumeLive = false,

  modelKind = "unknown",

  feedbackEvent = null,

  onDismissFeedbackEvent,

  preferencesEvent = null,

  onDismissPreferencesEvent,

  onFocusRoom,

}: {

  snapshot: LiveInferenceSnapshot

  engineStatus?: LiveEngineHookStatus

  previewDark?: boolean

  previewMeanLuma?: number | null

  previewFit?: "cover" | "contain"

  previewResumeLive?: boolean

  modelKind?: ModelKind

  feedbackEvent?: LiveFeedbackEvent | null

  onDismissFeedbackEvent?: () => void

  preferencesEvent?: LivePreferencesEvent | null

  onDismissPreferencesEvent?: () => void

  onFocusRoom?: () => void

}) {

  const [inspectOpen, setInspectOpen] = useState(false)

  const activeRoomId = useLiveSessionStore((s) => s.activeRoomId)

  const rooms = useLiveSessionStore((s) => s.rooms)

  const activeRoomName =

    rooms.find((r) => r.id === activeRoomId)?.name ??

    (snapshot.roomId ? rooms.find((r) => r.id === snapshot.roomId)?.name : null)



  const liveDistribution = snapshot.modelDistribution ?? snapshot.distribution

  const primaryState = snapshot.primaryState

  const liveConfidence =

    liveDistribution[primaryState] ?? snapshot.primaryConfidence

  const confidencePct = Math.round(liveConfidence * 100)

  const uncertain = isUncertainRead(liveDistribution, primaryState)

  const runnerUp = findRunnerUp(liveDistribution, primaryState)



  const uncertaintyNote = useMemo(() => {

    if (!uncertain) return null

    if (runnerUp && runnerUp.value >= liveConfidence - 0.15) {

      const runnerPct = Math.round(runnerUp.value * 100)

      return `Mixed read. ${roomStateLabel(runnerUp.id)} is close at ${runnerPct}%. Open Why · Right now for the breakdown.`

    }

    if (confidencePct < 55) {

      return `Low confidence (${confidencePct}%). Open Why · Right now before trusting automation.`

    }

    return "Signals are mixed this burst. Check Why · Right now before trusting automation."

  }, [uncertain, runnerUp, liveConfidence, confidencePct])



  const previewEnabled = engineStatus === "running" || snapshot.dataSource === "roomos-ml"

  const preview = useInferenceCameraPreview(previewEnabled, {

    resumeLive: previewResumeLive,

  })

  const feedLive = preview.status === "live"



  const showDarkWarning = previewDark && feedLive

  const useCover = previewFit === "cover"

  const multiRoom = rooms.length > 1

  const inferenceMode = resolveInferenceDisplayMode(modelKind, snapshot.dataSource)
  const trustLine =
    inferenceMode === "replay"
 ? "Replay source. not reading your webcam this session"
      : inferenceMode === "demo_model"
 ? "Demo/bootstrap model. live camera, synthetic weights"
        : undefined



  return (

    <section

      aria-labelledby="roomos-live-title"

      className="relative size-full min-h-0 overflow-hidden bg-black"

    >

      <h2 id="roomos-live-title" className="sr-only">

        Live room view and inferred activity

      </h2>



      <div className="absolute inset-0 z-0 flex items-center justify-center bg-black">

        {preview.streamSrc ? (

          // eslint-disable-next-line @next/next/no-img-element

          <img

            src={preview.streamSrc}

            alt=""

            decoding="async"

            onLoad={preview.onStreamLoad}

            onError={preview.onStreamError}

            className={cn(

              "object-center",

              useCover

                ? "size-full object-cover"

                : "h-full w-auto max-w-full object-contain",

              feedLive || preview.status !== "waiting" ? "opacity-100" : "opacity-40",

            )}

          />

        ) : (

          <div className="size-full bg-zinc-900" aria-hidden />

        )}

      </div>



      <div

        className="pointer-events-none absolute inset-0 z-[1] bg-gradient-to-t from-zinc-950 via-zinc-950/25 to-zinc-950/55"

        aria-hidden

      />



      <div className="pointer-events-none absolute inset-x-0 top-0 z-20 flex flex-col gap-2 px-3 pb-2 pl-14 pr-24 pt-3 sm:px-4 sm:pl-16 sm:pr-28 sm:pt-4">

        {multiRoom ? (

          <LivePresenceRail

            rooms={rooms}

            activeRoomId={activeRoomId}

            snapshot={snapshot}

            onOpenGallery={onFocusRoom}

          />

        ) : null}

      </div>



      {!feedLive && preview.message ? (

        <p

          className="absolute left-1/2 top-1/2 z-20 max-w-md -translate-x-1/2 -translate-y-1/2 rounded-xl border border-white/10 bg-zinc-950/90 px-4 py-3 text-center text-sm text-zinc-200 backdrop-blur-md"

          role="status"

        >

          {preview.status === "waiting"

            ? "Connecting to inference camera…"

            : preview.message}

        </p>

      ) : null}



      {feedbackEvent && onDismissFeedbackEvent ? (

        <TelegramCorrectionBanner event={feedbackEvent} onDismiss={onDismissFeedbackEvent} />

      ) : null}



      {preferencesEvent && onDismissPreferencesEvent ? (

        <PreferencesTelegramBanner

          event={preferencesEvent}

          onDismiss={onDismissPreferencesEvent}

        />

      ) : null}



      {showDarkWarning ? (
        <div className="pointer-events-auto absolute inset-x-2 top-[4.5rem] z-20 sm:inset-x-4 sm:top-20">
          <p className="rounded-lg border border-rose-400/40 bg-rose-950/95 px-3 py-2 text-center text-[11px] text-rose-50">
 Camera is dark. close other apps using the webcam or pick another device
          </p>
        </div>
      ) : null}



      <div
        className={cn(
          "pointer-events-none absolute inset-x-0 bottom-0 z-20 flex flex-col justify-end",
          inspectOpen ? "max-h-[min(78vh,640px)]" : "max-h-[min(52vh,420px)]",
        )}
      >

        <div
          className={cn(
            "pointer-events-auto flex flex-col gap-0 px-2 pb-2 sm:px-3 sm:pb-3",
            inspectOpen && "gap-1",
          )}
        >
          <PrimaryStateOverlay
            state={snapshot.primaryState}
            confidence={liveConfidence}
            uncertaintyNote={uncertaintyNote}
            trustLine={trustLine}
            sceneSummary={formatAppliedSceneSummary(
              snapshot.appliedScene,
              snapshot.connectedCategories,
            )}
            overlayShellClassName={cn(
              roomosUi.liveOverlayGlassTranslucent,
              "bg-zinc-950/55",
            )}
            className={cn(
              "!px-3 !py-2 sm:!px-4",
              inspectOpen
                ? "[&_h3]:!text-lg [&_h3]:sm:!text-xl"
                : "[&_h3]:!text-2xl [&_h3]:sm:!text-3xl",
            )}
          />
          <LiveExplainPanel
            snapshot={snapshot}
            open={inspectOpen}
            onToggle={() => setInspectOpen((o) => !o)}
            roomName={activeRoomName}
            multiRoom={multiRoom}
          />
        </div>

      </div>

    </section>

  )

}


