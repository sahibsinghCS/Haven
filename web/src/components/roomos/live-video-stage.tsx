"use client"

import Link from "next/link"
import { useState } from "react"
import { ChevronDown, ChevronRight, ChevronUp } from "lucide-react"

import { PreferencesTelegramBanner } from "@/components/roomos/preferences-telegram-banner"
import { TelegramCorrectionBanner } from "@/components/roomos/telegram-correction-banner"
import { LiveModeControl } from "@/components/roomos/live-mode-control"
import { LiveQuickCorrection } from "@/components/roomos/live-quick-correction"
import { PrimaryStateOverlay } from "@/components/roomos/primary-state-overlay"
import { SecondaryStateConfidence } from "@/components/roomos/secondary-state-confidence"
import { useInferenceCameraPreview } from "@/hooks/use-inference-camera-preview"
import type { LiveEngineHookStatus } from "@/hooks/use-live-engine"
import type { LiveMode, ModelKind } from "@/lib/roomos/api-client"
import { cn } from "@/lib/utils"
import { roomosUi } from "@/lib/roomos/roomos-ui"
import type { LiveFeedbackEvent } from "@/types/feedback-event"
import type { LivePreferencesEvent } from "@/types/preferences-event"
import type { LiveInferenceSnapshot } from "@/types/roomos"

/**
 * Immersive live: camera fills the viewport; controls sit in a bottom dock only.
 */
export function LiveVideoStage({
  snapshot,
  engineStatus = "running",
  liveMode = "live",
  demoMode = false,
  previewDark = false,
  previewMeanLuma = null,
  previewFit = "cover",
  modelKind = "unknown",
  onModeChanged,
  feedbackEvent = null,
  onDismissFeedbackEvent,
  preferencesEvent = null,
  onDismissPreferencesEvent,
}: {
  snapshot: LiveInferenceSnapshot
  engineStatus?: LiveEngineHookStatus
  liveMode?: LiveMode
  demoMode?: boolean
  previewDark?: boolean
  previewMeanLuma?: number | null
  previewFit?: "cover" | "contain"
  modelKind?: ModelKind
  onModeChanged?: () => void
  feedbackEvent?: LiveFeedbackEvent | null
  onDismissFeedbackEvent?: () => void
  preferencesEvent?: LivePreferencesEvent | null
  onDismissPreferencesEvent?: () => void
}) {
  const [dockOpen, setDockOpen] = useState(true)
  const isReplay = demoMode || liveMode === "replay" || snapshot.dataSource === "demo-replay"
  const primaryState = snapshot.primaryState
  const liveDistribution = snapshot.modelDistribution ?? snapshot.distribution
  const liveConfidence =
    liveDistribution[primaryState] ?? snapshot.primaryConfidence
  const previewEnabled = engineStatus === "running"
  const preview = useInferenceCameraPreview(previewEnabled, snapshot.sequence)
  const feedLive = preview.status === "live"
  const showBootstrapBanner = !isReplay && modelKind === "bootstrap"
  const showDarkWarning = !isReplay && previewDark && feedLive
  const useCover = previewFit !== "contain"

  return (
    <section
      aria-labelledby="roomos-live-title"
      className="relative size-full min-h-0 overflow-hidden bg-black"
    >
      <h2 id="roomos-live-title" className="sr-only">
        Live room view and inferred activity
      </h2>

      {preview.objectUrl ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={preview.objectUrl}
          alt=""
          className={cn(
            "absolute inset-0 z-0 size-full min-h-full min-w-full object-center",
            useCover ? "object-cover" : "object-contain",
            feedLive ? "opacity-100" : "opacity-0",
          )}
        />
      ) : (
        <div className="absolute inset-0 z-0 bg-zinc-900" aria-hidden />
      )}

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

      {(showBootstrapBanner || showDarkWarning) && !isReplay ? (
        <div className="pointer-events-auto absolute inset-x-2 top-2 z-20 sm:inset-x-4">
          {showBootstrapBanner ? (
            <p className="rounded-lg border border-amber-400/50 bg-amber-950/95 px-3 py-2 text-center text-[11px] text-amber-50">
              Demo model — run <code className="font-mono">npm run train:multi-room</code>
            </p>
          ) : (
            <p className="rounded-lg border border-rose-400/40 bg-rose-950/95 px-3 py-2 text-center text-[11px] text-rose-50">
              Camera is dark — close other apps using the webcam
            </p>
          )}
        </div>
      ) : null}

      {isReplay ? (
        <p className="pointer-events-none absolute inset-x-0 top-2 z-20 text-center text-[12px] font-medium text-amber-200/95">
          Demo replay — not live camera
        </p>
      ) : null}

      {onModeChanged ? (
        <div className="pointer-events-auto absolute right-2 top-2 z-20 sm:right-3 sm:top-3">
          <LiveModeControl liveMode={liveMode} onModeChanged={onModeChanged} />
        </div>
      ) : null}

      {/* Bottom dock — only this scrolls if needed */}
      <div className="pointer-events-none absolute inset-x-0 bottom-0 z-20 flex max-h-[min(48vh,420px)] flex-col justify-end">
        <button
          type="button"
          onClick={() => setDockOpen((o) => !o)}
          className="pointer-events-auto mx-auto mb-1 flex items-center gap-1 rounded-full border border-white/15 bg-zinc-950/80 px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-zinc-300 backdrop-blur-md"
        >
          {dockOpen ? (
            <>
              Hide controls <ChevronDown className="size-3" />
            </>
          ) : (
            <>
              Show controls <ChevronUp className="size-3" />
            </>
          )}
        </button>

        {dockOpen ? (
          <div className="pointer-events-auto overflow-y-auto overscroll-contain border-t border-white/10 bg-zinc-950/75 p-2 backdrop-blur-xl sm:p-3">
            <div className="grid gap-2 lg:grid-cols-2 lg:gap-3">
              <div className="min-w-0 space-y-2">
                <PrimaryStateOverlay
                  state={snapshot.primaryState}
                  confidence={liveConfidence}
                  sceneSummary={formatSceneTargets(snapshot)}
                  overlayShellClassName={cn(
                    roomosUi.liveOverlayGlassTranslucent,
                    "bg-zinc-950/50",
                  )}
                  className="!px-3 !py-2.5 sm:!px-4 [&_#roomos-live-trust]:hidden [&_h3]:!text-2xl [&_h3]:sm:!text-3xl"
                />
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
              <div className="flex min-w-0 flex-col gap-2">
                <LiveQuickCorrection
                  snapshot={snapshot}
                  compact
                  disabled={isReplay}
                  disabledReason="Switch to Live camera to teach the room."
                />
                {!isReplay ? (
                  <Link
                    href="/review"
                    className={cn(
                      roomosUi.liveOverlayGlassTranslucent,
                      "flex items-center justify-between gap-2 bg-zinc-950/50 px-3 py-2 text-[11px] font-semibold text-zinc-300",
                    )}
                  >
                    Review past switches
                    <ChevronRight className="size-3.5 opacity-70" aria-hidden />
                  </Link>
                ) : null}
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </section>
  )
}

function formatSceneTargets(snapshot: LiveInferenceSnapshot): string {
  const s = snapshot.appliedScene
  return `Lights ${s.brightness}% · ${s.fanOn ? "Fan on" : "Off"} · ${s.temperatureF}°F`
}
