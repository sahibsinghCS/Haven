"use client"

import { useState } from "react"
import { ChevronDown, ChevronUp } from "lucide-react"

import { PreferencesTelegramBanner } from "@/components/roomos/preferences-telegram-banner"
import { TelegramCorrectionBanner } from "@/components/roomos/telegram-correction-banner"
import { LiveQuickCorrection } from "@/components/roomos/live-quick-correction"
import { PrimaryStateOverlay } from "@/components/roomos/primary-state-overlay"
import { SecondaryStateConfidence } from "@/components/roomos/secondary-state-confidence"
import { useInferenceCameraPreview } from "@/hooks/use-inference-camera-preview"
import type { LiveEngineHookStatus } from "@/hooks/use-live-engine"
import type { ModelKind } from "@/lib/roomos/api-client"
import { cn } from "@/lib/utils"
import { roomosUi } from "@/lib/roomos/roomos-ui"
import type { LiveFeedbackEvent } from "@/types/feedback-event"
import type { LivePreferencesEvent } from "@/types/preferences-event"
import { formatAppliedSceneSummary } from "@/lib/roomos/format-applied-scene"
import type { LiveInferenceSnapshot } from "@/types/roomos"

/**
 * Immersive live: camera fills the viewport; controls sit in a bottom dock only.
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
}) {
  const [controlsOpen, setControlsOpen] = useState(false)
  const primaryState = snapshot.primaryState
  const liveDistribution = snapshot.modelDistribution ?? snapshot.distribution
  const liveConfidence =
    liveDistribution[primaryState] ?? snapshot.primaryConfidence
  const previewEnabled = engineStatus === "running" || snapshot.dataSource === "roomos-ml"
  const preview = useInferenceCameraPreview(previewEnabled, {
    resumeLive: previewResumeLive,
  })
  const feedLive = preview.status === "live"
  const showBootstrapBanner = modelKind === "bootstrap"
  const showDarkWarning = previewDark && feedLive
  const useCover = previewFit === "cover"

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
        className="pointer-events-none absolute inset-0 z-[1] bg-gradient-to-t from-zinc-950 via-zinc-950/20 to-zinc-950/40"
        aria-hidden
      />

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

      {showBootstrapBanner || showDarkWarning ? (
        <div className="pointer-events-auto absolute inset-x-2 top-2 z-20 sm:inset-x-4">
          {showBootstrapBanner ? (
            <p className="rounded-lg border border-amber-400/50 bg-amber-950/95 px-3 py-2 text-center text-[11px] text-amber-50">
              Demo model — run <code className="font-mono">npm run train:multi-room</code>
            </p>
          ) : (
            <p className="rounded-lg border border-rose-400/40 bg-rose-950/95 px-3 py-2 text-center text-[11px] text-rose-50">
              Camera is dark — close other apps using the webcam or pick another device above
            </p>
          )}
        </div>
      ) : null}

      <div className="pointer-events-none absolute inset-x-0 bottom-0 z-20 flex max-h-[min(58vh,520px)] flex-col justify-end">
        <button
          type="button"
          onClick={() => setControlsOpen((o) => !o)}
          className="pointer-events-auto mx-auto mb-1 flex items-center gap-1 rounded-full border border-white/15 bg-zinc-950/80 px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-zinc-300 backdrop-blur-md"
        >
          {controlsOpen ? (
            <>
              Hide controls <ChevronDown className="size-3" />
            </>
          ) : (
            <>
              Show controls <ChevronUp className="size-3" />
            </>
          )}
        </button>

        {controlsOpen ? (
          <div className="pointer-events-auto overflow-y-auto overscroll-contain border-t border-white/10 bg-zinc-950/75 p-2 backdrop-blur-xl sm:p-3">
            <div className="flex min-w-0 flex-col gap-2">
              <LiveQuickCorrection snapshot={snapshot} compact />
              <SecondaryStateConfidence
                variant="overlay"
                distribution={liveDistribution}
                primary={snapshot.primaryState}
                overlayShellClassName={cn(
                  roomosUi.liveOverlayGlassTranslucent,
                  "bg-zinc-950/50",
                )}
                finePercent
                subtitle="Likelihoods"
              />
            </div>
          </div>
        ) : (
          <div className="pointer-events-auto px-2 pb-2 sm:px-3 sm:pb-3">
            <PrimaryStateOverlay
              state={snapshot.primaryState}
              confidence={liveConfidence}
              sceneSummary={formatAppliedSceneSummary(
                snapshot.appliedScene,
                snapshot.connectedCategories,
              )}
              overlayShellClassName={cn(
                roomosUi.liveOverlayGlassTranslucent,
                "bg-zinc-950/50",
              )}
              className="!px-3 !py-2.5 sm:!px-4 [&_#roomos-live-trust]:hidden [&_h3]:!text-2xl [&_h3]:sm:!text-3xl"
            />
          </div>
        )}
      </div>
    </section>
  )
}
