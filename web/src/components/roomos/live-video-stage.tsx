"use client"

import { useState } from "react"
import { motion, useReducedMotion } from "framer-motion"
import { Camera, CheckCircle2, Fan, Flag, Lightbulb, Thermometer, X } from "lucide-react"
import { toast } from "sonner"

import { PrimaryStateOverlay } from "@/components/roomos/primary-state-overlay"
import { SecondaryStateConfidence } from "@/components/roomos/secondary-state-confidence"
import { useLiveRoomCamera } from "@/hooks/use-live-room-camera"
import { formatCameraDeviceLabel } from "@/lib/roomos/format-camera-device-label"
import { cn } from "@/lib/utils"
import { roomosUi } from "@/lib/roomos/roomos-ui"
import { ROOM_STATE_ACCENT, ROOM_STATE_LABEL } from "@/lib/roomos/state-meta"
import { submitLiveFeedback } from "@/lib/roomos/api-client"
import type { LiveInferenceStatus } from "@/hooks/use-live-inference"
import { ROOM_STATE_ORDER, type LiveInferenceSnapshot, type RoomStateId } from "@/types/roomos"

/**
 * Full-bleed live stage: local webcam fills the view; HUD uses translucent glass.
 */
export function LiveVideoStage({
  snapshot,
  dataSource = "ml",
  engineStatus = "running",
  connectionStatus = "live",
  statusMessage,
}: {
  snapshot: LiveInferenceSnapshot
  dataSource?: "ml" | null
  engineStatus?: string
  connectionStatus?: LiveInferenceStatus
  statusMessage?: string | null
}) {
  const reduceMotion = useReducedMotion()
  const primaryState = snapshot.primaryState
  const liveDistribution = snapshot.modelDistribution ?? snapshot.distribution
  const liveConfidence =
    liveDistribution[primaryState] ?? snapshot.primaryConfidence
  const accent = ROOM_STATE_ACCENT[primaryState]
  const [cameraDeviceId, setCameraDeviceId] = useState<string | null>(null)
  const camera = useLiveRoomCamera(cameraDeviceId)
  const feedLive = camera.status === "live"

  return (
    <section
      aria-labelledby="roomos-live-title"
      className="relative flex w-full min-h-[max(calc(100dvh-3.25rem),22rem)] flex-1 flex-col overflow-hidden sm:min-h-[max(calc(100dvh-3.5rem),22rem)]"
    >
      <h2 id="roomos-live-title" className="sr-only">
        Live room view and inferred activity
      </h2>

      {/* Fallback atmosphere when there is no live video yet */}
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
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_85%_70%_at_50%_38%,rgba(255,255,255,0.055)_0%,transparent_52%)]" />
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-zinc-800/25 via-transparent to-transparent" />
        <motion.div
          className="absolute inset-0 opacity-[0.055]"
          animate={
            reduceMotion ? false : { backgroundPosition: ["0% 0%", "100% 100%"] }
          }
          transition={
            reduceMotion
              ? undefined
              : { duration: 56, repeat: Number.POSITIVE_INFINITY, ease: "linear" }
          }
          style={{
            backgroundImage:
              "radial-gradient(circle at 20% 20%, rgba(255,255,255,0.9) 1px, transparent 1.5px)",
            backgroundSize: "38px 38px",
          }}
        />
        <div className="absolute inset-0 bg-gradient-to-t from-zinc-950/94 via-zinc-950/38 to-zinc-900/42" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_0%,rgba(0,0,0,0.38)_100%)]" />
      </div>

      <video
        ref={camera.videoRef}
        className={cn(
          "absolute inset-0 z-[1] h-full w-full object-cover transition-opacity duration-500",
          feedLive ? "opacity-100" : "opacity-0",
        )}
        muted
        playsInline
      />

      {feedLive ? (
        <div
          className="pointer-events-none absolute inset-0 z-[2] bg-[radial-gradient(ellipse_90%_85%_at_50%_50%,transparent_0%,rgba(0,0,0,0.22)_100%)]"
          aria-hidden
        />
      ) : null}

      {/* Camera controls: bottom strip over full-bleed video */}
      <div className="pointer-events-none absolute inset-x-0 bottom-0 z-30 flex justify-center p-3 sm:p-4">
        <div className="pointer-events-auto flex w-full max-w-[min(100%,40rem)] flex-wrap items-center gap-2">
          <label className="sr-only" htmlFor="roomos-live-camera-device">
            Camera device
          </label>
          <select
            id="roomos-live-camera-device"
            className={cn(
              roomosUi.liveStatusPillTranslucent,
              "max-w-full cursor-pointer rounded-full px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-stone-200 focus:outline-none focus:ring-2 focus:ring-teal-400/35",
            )}
            value={cameraDeviceId ?? ""}
            onChange={(e) => {
              const v = e.target.value
              setCameraDeviceId(v === "" ? null : v)
            }}
            disabled={
              camera.status === "requesting" ||
              (camera.videoInputs.length === 0 &&
                camera.status !== "denied" &&
                camera.status !== "error")
            }
          >
            <option value="">Auto</option>
            {camera.videoInputs.map((d) => (
              <option key={d.deviceId} value={d.deviceId}>
                {formatCameraDeviceLabel(d.label)}
              </option>
            ))}
          </select>
          {camera.status === "requesting" ? (
            <span
              className={cn(
                roomosUi.liveStatusPillTranslucent,
                "inline-flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-stone-300",
              )}
            >
              <Camera className="size-3 shrink-0" aria-hidden />
              Starting…
            </span>
          ) : null}
          {camera.status === "denied" || camera.status === "error" ? (
            <button
              type="button"
              onClick={() => camera.retry()}
              className={cn(
                roomosUi.liveStatusPillTranslucent,
                "border-teal-400/30 bg-teal-950/58 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-teal-100 hover:bg-teal-900/62 focus:outline-none focus:ring-2 focus:ring-teal-400/35",
              )}
            >
              Retry camera
            </button>
          ) : null}
        </div>
      </div>

      {camera.status === "unsupported" && camera.message ? (
        <p
          className="absolute bottom-24 left-4 right-4 z-30 mx-auto max-w-md rounded-xl border border-amber-400/30 bg-amber-950/72 px-3 py-2 text-[11px] leading-snug text-amber-50 shadow-lg backdrop-blur-md sm:left-6 sm:right-6"
          role="status"
        >
          {camera.message}
        </p>
      ) : null}
      {camera.message && camera.status !== "unsupported" ? (
        <p
          className="absolute bottom-24 left-4 right-4 z-30 mx-auto max-w-md rounded-xl border border-rose-400/28 bg-rose-950/72 px-3 py-2 text-[11px] leading-snug text-rose-100 shadow-lg backdrop-blur-md sm:left-6 sm:right-6"
          role="status"
        >
          {camera.message}
        </p>
      ) : null}

      {/* Overlay UI: translucent panels so the feed shows through */}
      <div className="pointer-events-none relative z-10 mx-auto flex min-h-0 w-full max-w-[min(100%,88rem)] flex-1 flex-col gap-6 p-4 sm:gap-7 sm:p-6 lg:p-8">
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <div
            role="status"
            className={cn(
              roomosUi.liveStatusPillTranslucent,
              "inline-flex items-center gap-2 px-3 py-1.5",
            )}
          >
            <span className="relative flex size-2" aria-hidden>
              {!reduceMotion ? (
                <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400/55 opacity-50 motion-reduce:animate-none" />
              ) : null}
              <span className="relative inline-flex size-2 rounded-full bg-emerald-400/95" />
            </span>
            <Camera className="size-3.5 text-zinc-300" aria-hidden />
            <span className="text-zinc-100">Live camera</span>
          </div>
          <div
            className={cn(
              roomosUi.liveStatusPillTranslucent,
              "inline-flex items-center gap-2 px-3 py-1.5 text-zinc-300",
            )}
          >
            <span className="font-mono text-[10.5px] font-semibold uppercase tracking-[0.18em] text-zinc-500">
              Room
            </span>
            <span className="text-zinc-200">Living room</span>
          </div>
          {dataSource === "ml" ? (
            <div
              className={cn(
                roomosUi.liveStatusPillTranslucent,
                "inline-flex items-center gap-2 border-teal-400/25 bg-teal-950/45 px-3 py-1.5 text-teal-100",
              )}
            >
              <span className="font-mono text-[10.5px] font-semibold uppercase tracking-[0.16em]">
                Model
              </span>
              <span className="text-[11px]">
                {connectionStatus === "live" ? "Live" : "Poll"}{" "}
                {typeof snapshot.sequence === "number" ? `#${snapshot.sequence}` : ""}
              </span>
            </div>
          ) : null}
          {snapshot.capturedAt ? (
            <div
              className={cn(
                roomosUi.liveStatusPillTranslucent,
                "inline-flex items-center gap-2 px-3 py-1.5 text-zinc-400",
              )}
            >
              <span className="text-[10px] font-medium tabular-nums">
                {formatUpdatedAgo(snapshot.capturedAt)}
              </span>
            </div>
          ) : null}
          {snapshot.personalization?.applied ? (
            <div
              className={cn(
                roomosUi.liveStatusPillTranslucent,
                "inline-flex items-center gap-2 border-violet-400/25 bg-violet-950/40 px-3 py-1.5 text-violet-100",
              )}
            >
              <span className="text-[10px] font-semibold uppercase tracking-[0.14em]">
                Memory {snapshot.personalization.matches ?? 0} match
                {(snapshot.personalization.matches ?? 0) === 1 ? "" : "es"}
              </span>
            </div>
          ) : null}
        </div>

        <div className="mt-auto flex min-h-0 w-full min-w-0 flex-col gap-5 pb-1 lg:flex-row lg:items-end lg:justify-between lg:gap-10">
          <div className="min-w-0 flex-1 lg:min-w-[min(100%,28rem)]">
            <PrimaryStateOverlay
              state={snapshot.primaryState}
              confidence={liveConfidence}
              sceneSummary={formatSceneSummary(snapshot)}
              overlayShellClassName={roomosUi.liveOverlayGlassTranslucent}
            />
          </div>
          <div className="flex w-full min-w-0 shrink-0 flex-col gap-3 lg:max-w-[21rem] xl:max-w-[22rem]">
            <SecondaryStateConfidence
              variant="overlay"
              distribution={liveDistribution}
              primary={snapshot.primaryState}
              overlayShellClassName={roomosUi.liveOverlayGlassTranslucent}
              finePercent
            />
            <SceneTargetCard snapshot={snapshot} />
            <FeedbackCorrectionCard snapshot={snapshot} />
          </div>
        </div>
      </div>

      <span className="sr-only">
        Live camera preview fills this page when permitted. Video stays in your browser unless you
        enable recording elsewhere.
      </span>
    </section>
  )
}

function FeedbackCorrectionCard({ snapshot }: { snapshot: LiveInferenceSnapshot }) {
  const [open, setOpen] = useState(false)
  const [correctedLabel, setCorrectedLabel] = useState<RoomStateId>(() =>
    firstDifferentState(snapshot.primaryState),
  )
  const [notes, setNotes] = useState("")
  const [saving, setSaving] = useState(false)

  async function submit() {
    if (correctedLabel === snapshot.primaryState) return
    setSaving(true)
    try {
      const result = await submitLiveFeedback({ correctedLabel, notes })
      toast.success("Correction saved", {
        description: `${result.screenshotCount} burst frames added to room memory.`,
      })
      setOpen(false)
      setNotes("")
    } catch (err) {
      toast.error("Could not save correction", {
        description: err instanceof Error ? err.message : "The backend rejected the report.",
      })
    } finally {
      setSaving(false)
    }
  }

  if (!open) {
    return (
      <aside className={cn(roomosUi.liveOverlayGlassTranslucent, "pointer-events-auto p-3")}>
        <button
          type="button"
          onClick={() => {
            setCorrectedLabel(firstDifferentState(snapshot.primaryState))
            setOpen(true)
          }}
          className="flex w-full items-center justify-center gap-2 rounded-lg border border-white/[0.08] bg-white/[0.06] px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-zinc-200 transition hover:bg-white/[0.1] focus:outline-none focus:ring-2 focus:ring-teal-400/35"
        >
          <Flag className="size-3.5" aria-hidden />
          Report wrong state
        </button>
      </aside>
    )
  }

  return (
    <aside className={cn(roomosUi.liveOverlayGlassTranslucent, "pointer-events-auto p-4")}>
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-[0.68rem] font-semibold uppercase tracking-[0.18em] text-zinc-400">
          Correct state
        </h3>
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="flex size-7 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.05] text-zinc-300 hover:bg-white/[0.1] focus:outline-none focus:ring-2 focus:ring-teal-400/35"
          aria-label="Close correction form"
        >
          <X className="size-3.5" aria-hidden />
        </button>
      </div>
      <div className="mt-3 grid gap-3">
        <label className="grid gap-1.5">
          <span className="text-[0.65rem] font-semibold uppercase tracking-[0.16em] text-zinc-500">
            It was
          </span>
          <select
            value={correctedLabel}
            onChange={(e) => setCorrectedLabel(e.target.value as RoomStateId)}
            className="h-9 rounded-lg border border-white/[0.08] bg-zinc-950/60 px-3 text-sm text-zinc-100 outline-none focus:ring-2 focus:ring-teal-400/35"
          >
            {ROOM_STATE_ORDER.map((state) => (
              <option key={state} value={state}>
                {ROOM_STATE_LABEL[state]}
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-1.5">
          <span className="text-[0.65rem] font-semibold uppercase tracking-[0.16em] text-zinc-500">
            Note
          </span>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            maxLength={1000}
            rows={2}
            className="min-h-16 resize-none rounded-lg border border-white/[0.08] bg-zinc-950/60 px-3 py-2 text-sm leading-relaxed text-zinc-100 outline-none placeholder:text-zinc-600 focus:ring-2 focus:ring-teal-400/35"
            placeholder="Optional"
          />
        </label>
        <button
          type="button"
          onClick={submit}
          disabled={saving || correctedLabel === snapshot.primaryState}
          className="flex h-9 items-center justify-center gap-2 rounded-lg border border-teal-300/20 bg-teal-500/16 px-3 text-[11px] font-semibold uppercase tracking-[0.16em] text-teal-100 transition hover:bg-teal-500/24 focus:outline-none focus:ring-2 focus:ring-teal-400/35 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <CheckCircle2 className="size-3.5" aria-hidden />
          {saving ? "Saving" : "Save correction"}
        </button>
      </div>
    </aside>
  )
}

function firstDifferentState(primary: RoomStateId): RoomStateId {
  return ROOM_STATE_ORDER.find((state) => state !== primary) ?? "relaxing"
}

function SceneTargetCard({ snapshot }: { snapshot: LiveInferenceSnapshot }) {
  const target = snapshot.appliedScene
  const targetRows = [
    {
      label: "Light",
      value: `${target.brightness}%`,
      Icon: Lightbulb,
      accent: "text-amber-200",
    },
    {
      label: "Air",
      value: target.fanOn ? "On" : "Still",
      Icon: Fan,
      accent: "text-sky-200",
    },
    {
      label: "Target",
      value: `${target.temperatureF}°F`,
      Icon: Thermometer,
      accent: "text-teal-200",
    },
  ] as const

  return (
    <aside
      className={cn(roomosUi.liveOverlayGlassTranslucent, "p-4 sm:p-5")}
      aria-labelledby="roomos-scene-targets"
    >
      <div className="flex items-center justify-between gap-3">
        <h3
          id="roomos-scene-targets"
          className="text-[0.68rem] font-semibold uppercase tracking-[0.18em] text-zinc-400"
        >
          Applied scene
        </h3>
        <span
          className="size-4 rounded-full border border-white/20 shadow-[inset_0_1px_0_rgba(255,255,255,0.2)]"
          style={{ backgroundColor: target.lightColorHex }}
          aria-label={`Current light color ${target.lightColorHex}`}
        />
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2">
        {targetRows.map(({ label, value, Icon, accent }) => (
          <div key={label} className="rounded-xl border border-white/[0.08] bg-white/[0.08] p-2.5">
            <Icon className={cn("size-3.5", accent)} aria-hidden />
            <p className="mt-2 font-mono text-[13px] font-semibold tabular-nums text-zinc-100">
              {value}
            </p>
            <p className="mt-0.5 text-[10px] uppercase tracking-[0.13em] text-zinc-600">{label}</p>
          </div>
        ))}
      </div>
      <div className="mt-4 border-t border-white/[0.08] pt-3">
        <p className="text-[0.65rem] font-semibold uppercase tracking-[0.18em] text-zinc-500">
          Why
        </p>
        <ul className="mt-2 space-y-1.5">
          {snapshot.rationale.slice(0, 3).map((reason) => (
            <li key={reason} className="flex gap-2 text-[12px] leading-relaxed text-zinc-300">
              <span className="mt-2 size-1 shrink-0 rounded-full bg-teal-300/70" aria-hidden />
              <span>{reason}</span>
            </li>
          ))}
        </ul>
      </div>
    </aside>
  )
}

function formatUpdatedAgo(iso: string): string {
  const t = Date.parse(iso)
  if (Number.isNaN(t)) return "Updated"
  const sec = Math.max(0, Math.round((Date.now() - t) / 1000))
  if (sec < 2) return "Updated just now"
  if (sec < 60) return `Updated ${sec}s ago`
  return `Updated ${Math.round(sec / 60)}m ago`
}

function formatSceneSummary(snapshot: LiveInferenceSnapshot): string {
  const s = snapshot.appliedScene
  const fan = s.fanOn ? "Fan on" : "Fan off"
  const base = `Lights ${s.brightness}%, ${fan}, ${s.temperatureF}°F target`
  const topRationale = snapshot.rationale[0]
  if (!topRationale) return base
  return `${base}. ${topRationale}`
}
