"use client"

import { motion, useReducedMotion } from "framer-motion"

import { LiveDemoStatusBar } from "@/components/roomos/live-demo-status-bar"
import { LiveModeControl } from "@/components/roomos/live-mode-control"
import { LiveQuickCorrection } from "@/components/roomos/live-quick-correction"
import { PersonalizationHint } from "@/components/roomos/personalization-hint"
import { PrimaryStateOverlay } from "@/components/roomos/primary-state-overlay"
import { SecondaryStateConfidence } from "@/components/roomos/secondary-state-confidence"
import { useInferenceCameraPreview } from "@/hooks/use-inference-camera-preview"
import type { LiveEngineHookStatus } from "@/hooks/use-live-engine"
import type { LiveInferenceStatus } from "@/hooks/use-live-inference"
import type { LiveMode, ModelKind } from "@/lib/roomos/api-client"
import { cn } from "@/lib/utils"
import { roomosUi } from "@/lib/roomos/roomos-ui"
import { ROOM_STATE_ACCENT } from "@/lib/roomos/state-meta"
import type { LiveInferenceSnapshot } from "@/types/roomos"

/**
 * Full-bleed live stage for judge demos: one status bar, hero state, scene + correction.
 */
export function LiveVideoStage({
  snapshot,
  engineStatus = "running",
  inferenceSource = null,
  connectionStatus = "live",
  liveMode = "live",
  demoMode = false,
  previewDark = false,
  previewMeanLuma = null,
  modelKind = "unknown",
  onModeChanged,
}: {
  snapshot: LiveInferenceSnapshot
  engineStatus?: LiveEngineHookStatus
  inferenceSource?: string | null
  connectionStatus?: LiveInferenceStatus
  liveMode?: LiveMode
  demoMode?: boolean
  /** True when the backend preview frames are effectively black. */
  previewDark?: boolean
  /** 0..255 average brightness of the latest preview frame. */
  previewMeanLuma?: number | null
  modelKind?: ModelKind
  onModeChanged?: () => void
}) {
  const isReplay = demoMode || liveMode === "replay" || snapshot.dataSource === "demo-replay"
  const reduceMotion = useReducedMotion()
  const primaryState = snapshot.primaryState
  const liveDistribution = snapshot.modelDistribution ?? snapshot.distribution
  const liveConfidence =
    liveDistribution[primaryState] ?? snapshot.primaryConfidence
  const accent = ROOM_STATE_ACCENT[primaryState]
  const previewEnabled = engineStatus === "running"
  const preview = useInferenceCameraPreview(previewEnabled, snapshot.sequence)
  const feedLive = preview.status === "live"
  const showDarkWarning = !isReplay && previewDark && feedLive
  const showBootstrapBanner = !isReplay && modelKind === "bootstrap"
  // Honest low-confidence signal: when the raw model spreads probability
  // roughly evenly across classes, surface an abstain hint so judges know
  // the room state isn't being claimed with false certainty.
  const topProb = Math.max(...Object.values(liveDistribution))
  const lowConfidence = !isReplay && topProb < 0.45

  return (
    <section
      aria-labelledby="roomos-live-title"
      className="relative flex min-h-[max(calc(100dvh-3.25rem),24rem)] w-full flex-1 flex-col overflow-hidden 2xl:min-h-[calc(100dvh-3rem)]"
    >
      <h2 id="roomos-live-title" className="sr-only">
        Live room view and inferred activity
      </h2>

      {/* Atmosphere when video not ready */}
      <div
        className={cn(
          "absolute inset-0 z-0 overflow-hidden transition-opacity duration-500",
          feedLive ? "pointer-events-none opacity-0" : "opacity-100",
        )}
        aria-hidden
      >
        <motion.div
          key={primaryState}
          className={cn("absolute inset-0 bg-gradient-to-br", accent.heroMesh)}
          initial={reduceMotion ? false : { opacity: 0.88 }}
          animate={{ opacity: 1 }}
          transition={reduceMotion ? { duration: 0.12 } : { duration: 0.9, ease: "easeOut" }}
        />
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-zinc-950/94 via-zinc-950/38 to-zinc-900/42" />
      </div>

      {preview.objectUrl ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={preview.objectUrl}
          alt=""
          className={cn(
            "absolute inset-0 z-[1] h-full w-full object-cover transition-opacity duration-500",
            feedLive ? "opacity-100" : "opacity-0",
          )}
        />
      ) : null}

      {feedLive ? (
        <div
          className="pointer-events-none absolute inset-0 z-[2] bg-[radial-gradient(ellipse_90%_85%_at_50%_50%,transparent_0%,rgba(0,0,0,0.28)_100%)]"
          aria-hidden
        />
      ) : null}

      {!feedLive && preview.message ? (
        <p
          className="absolute left-1/2 top-[42%] z-20 max-w-md -translate-x-1/2 rounded-2xl border border-white/10 bg-zinc-950/75 px-4 py-3 text-center text-sm text-zinc-200 shadow-xl backdrop-blur-md"
          role="status"
        >
          {preview.status === "waiting"
            ? "Connecting to inference camera…"
            : preview.message}
          <span className="mt-1 block text-[11px] text-zinc-500">
            {isReplay
              ? "Demo replay uses scripted preview frames, not your webcam."
              : "Predictions use the same backend camera (not your browser webcam)."}
          </span>
        </p>
      ) : null}

      {isReplay ? (
        <div
          className="pointer-events-none absolute inset-x-0 top-0 z-30 flex justify-center px-4 pt-4"
          role="status"
          aria-live="polite"
        >
          <p className="max-w-2xl rounded-xl border border-amber-400/35 bg-amber-950/85 px-4 py-2.5 text-center text-sm font-medium text-amber-50 shadow-lg backdrop-blur-md">
            <span className="font-semibold uppercase tracking-wide text-amber-200/90">
              Demo replay active
            </span>
            {" — "}
            Prerecorded room states for presentation. Not live camera inference.
          </p>
        </div>
      ) : null}

      {showBootstrapBanner || showDarkWarning || lowConfidence ? (
        <div
          className="pointer-events-none absolute inset-x-0 top-0 z-30 flex flex-col items-center gap-2 px-4 pt-4"
          role="status"
          aria-live="polite"
        >
          {showBootstrapBanner ? (
            <p className="pointer-events-auto max-w-2xl rounded-xl border border-amber-400/35 bg-amber-950/85 px-4 py-2.5 text-center text-sm font-medium text-amber-50 shadow-lg backdrop-blur-md">
              <span className="font-semibold uppercase tracking-wide text-amber-200/90">
                Pipeline demo model
              </span>
              {" — "}
              Predictions come from synthetic stills, not your room. Run{" "}
              <code className="rounded bg-black/40 px-1.5 py-0.5 font-mono text-[12px] text-amber-100">
                npm run train:images
              </code>{" "}
              with photos of your space for accurate live inference.
            </p>
          ) : null}
          {showDarkWarning ? (
            <p className="pointer-events-auto max-w-2xl rounded-xl border border-rose-400/40 bg-rose-950/85 px-4 py-2.5 text-center text-sm font-medium text-rose-50 shadow-lg backdrop-blur-md">
              <span className="font-semibold uppercase tracking-wide text-rose-200/90">
                Camera is dark
              </span>
              {" — "}
              The backend is receiving near-black frames
              {typeof previewMeanLuma === "number"
                ? ` (mean luma ${previewMeanLuma.toFixed(1)}/255)`
                : ""}
              . Close Teams/Zoom/OBS, then try{" "}
              <code className="rounded bg-black/40 px-1.5 py-0.5 font-mono text-[12px] text-rose-100">
                npm run probe:cameras
              </code>{" "}
              and set <code className="rounded bg-black/40 px-1 py-0.5 font-mono text-[12px]">video.source</code> /{" "}
              <code className="rounded bg-black/40 px-1 py-0.5 font-mono text-[12px]">video.backend</code> in the
              inference config.
            </p>
          ) : null}
          {lowConfidence && !showDarkWarning ? (
            <p className="pointer-events-auto max-w-2xl rounded-xl border border-sky-400/30 bg-sky-950/80 px-4 py-2 text-center text-xs font-medium text-sky-100 shadow-lg backdrop-blur-md">
              Model is uncertain — top probability only {(topProb * 100).toFixed(0)}%.
              Teach the room with the correction below or train on real frames.
            </p>
          ) : null}
        </div>
      ) : null}

      <div className="relative z-10 mx-auto flex min-h-0 w-full max-w-[min(100%,96rem)] flex-1 flex-col gap-5 p-4 sm:gap-6 sm:p-6 lg:gap-8 lg:p-8 2xl:max-w-[110rem] 2xl:p-10">
        <div className="pointer-events-auto flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <LiveDemoStatusBar
            engineStatus={engineStatus}
            inferenceSource={inferenceSource}
            connectionStatus={connectionStatus}
            snapshot={snapshot}
            previewStatus={preview.status}
            liveMode={liveMode}
            demoMode={demoMode}
          />
          {onModeChanged ? (
            <LiveModeControl liveMode={liveMode} onModeChanged={onModeChanged} />
          ) : null}
        </div>

        <div className="mt-auto flex min-h-0 w-full min-w-0 flex-col gap-6 pb-2 xl:flex-row xl:items-end xl:justify-between xl:gap-12 2xl:gap-16">
          <div className="min-w-0 flex-1 xl:max-w-[52%] 2xl:max-w-[55%]">
            <PrimaryStateOverlay
              state={snapshot.primaryState}
              confidence={liveConfidence}
              sceneSummary={formatSceneTargets(snapshot)}
              overlayShellClassName={roomosUi.liveOverlayGlassTranslucent}
            />
          </div>

          <div className="pointer-events-none flex w-full min-w-0 shrink-0 flex-col gap-3 xl:max-w-[26rem] 2xl:max-w-[28rem]">
            <PersonalizationHint snapshot={snapshot} />
            <SecondaryStateConfidence
              variant="overlay"
              distribution={liveDistribution}
              primary={snapshot.primaryState}
              overlayShellClassName={roomosUi.liveOverlayGlassTranslucent}
              finePercent
              subtitle={
                snapshot.personalization?.applied
                  ? "After room memory blend"
                  : "Raw burst likelihoods"
              }
            />
            <SceneAndAutomationCard snapshot={snapshot} />
            <LiveQuickCorrection snapshot={snapshot} disabled={isReplay} disabledReason="Switch to Live camera to teach the room." />
          </div>
        </div>
      </div>
    </section>
  )
}

function SceneAndAutomationCard({ snapshot }: { snapshot: LiveInferenceSnapshot }) {
  const target = snapshot.appliedScene
  const mode = snapshot.automationMode ?? "off"
  const last = snapshot.lastAutomation
  const topReasons = snapshot.rationale.filter(Boolean).slice(0, 2)

  return (
    <aside
      className={cn(roomosUi.liveOverlayGlassTranslucent, "p-4 sm:p-5")}
      aria-labelledby="roomos-scene-effect"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3
            id="roomos-scene-effect"
            className="text-[0.68rem] font-semibold uppercase tracking-[0.18em] text-zinc-400"
          >
            Room response
          </h3>
          <p className="mt-1 text-[11px] text-zinc-500">From your active preference preset</p>
        </div>
        <span
          className="size-5 shrink-0 rounded-full border border-white/20 shadow-inner"
          style={{ backgroundColor: target.lightColorHex }}
          aria-label={`Target light color ${target.lightColorHex}`}
        />
      </div>

      <dl className="mt-3 grid grid-cols-3 gap-2 text-center">
        <div className="rounded-xl border border-white/[0.08] bg-white/[0.06] px-2 py-2.5">
          <dt className="text-[10px] uppercase tracking-[0.12em] text-zinc-500">Lights</dt>
          <dd className="mt-1 font-mono text-lg font-semibold tabular-nums text-zinc-50">
            {target.brightness}%
          </dd>
        </div>
        <div className="rounded-xl border border-white/[0.08] bg-white/[0.06] px-2 py-2.5">
          <dt className="text-[10px] uppercase tracking-[0.12em] text-zinc-500">Fan</dt>
          <dd className="mt-1 font-mono text-lg font-semibold text-zinc-50">
            {target.fanOn ? "On" : "Off"}
          </dd>
        </div>
        <div className="rounded-xl border border-white/[0.08] bg-white/[0.06] px-2 py-2.5">
          <dt className="text-[10px] uppercase tracking-[0.12em] text-zinc-500">Temp</dt>
          <dd className="mt-1 font-mono text-lg font-semibold tabular-nums text-zinc-50">
            {target.temperatureF}°
          </dd>
        </div>
      </dl>

      {topReasons.length > 0 ? (
        <div className="mt-4 border-t border-white/[0.08] pt-3">
          <p className="text-[0.65rem] font-semibold uppercase tracking-[0.16em] text-zinc-500">
            Why this state
          </p>
          <ul className="mt-2 space-y-1">
            {topReasons.map((reason) => (
              <li key={reason} className="text-[12px] leading-snug text-zinc-300">
                {reason}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="mt-4 rounded-xl border border-white/[0.06] bg-black/20 px-3 py-2.5">
        <p className="text-[0.65rem] font-semibold uppercase tracking-[0.14em] text-zinc-500">
          Smart home
        </p>
        <p className="mt-1 text-[12px] leading-relaxed text-zinc-300">
          {mode === "live"
            ? last?.summary ?? "Live rule fired — device integration active."
            : mode === "dry_run"
              ? "Simulated only — no devices contacted (dry-run in config)."
              : "Not configured for this session."}
        </p>
      </div>
    </aside>
  )
}

function formatSceneTargets(snapshot: LiveInferenceSnapshot): string {
  const s = snapshot.appliedScene
  const fan = s.fanOn ? "Fan on" : "Fan off"
  return `Lights ${s.brightness}% · ${fan} · ${s.temperatureF}°F target`
}
