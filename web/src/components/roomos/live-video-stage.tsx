"use client"

import { motion, useReducedMotion } from "framer-motion"
import { Camera, Shield } from "lucide-react"

import { PrimaryStateOverlay } from "@/components/roomos/primary-state-overlay"
import { SecondaryStateConfidence } from "@/components/roomos/secondary-state-confidence"
import { cn } from "@/lib/utils"
import { roomosUi } from "@/lib/roomos/roomos-ui"
import { ROOM_STATE_ACCENT } from "@/lib/roomos/state-meta"
import type { LiveInferenceSnapshot } from "@/types/roomos"

/**
 * Full-bleed live stage: simulated feed + floating overlays.
 * Replace gradient layers with `<video>` when `stream.streamUrl` is available.
 */
export function LiveVideoStage({ snapshot }: { snapshot: LiveInferenceSnapshot }) {
  const reduceMotion = useReducedMotion()
  const primaryState = snapshot.primaryState
  const accent = ROOM_STATE_ACCENT[primaryState]

  return (
    <section
      aria-labelledby="roomos-live-title"
      className="relative flex min-h-[calc(100dvh-3.25rem)] w-full flex-1 flex-col overflow-hidden sm:min-h-[calc(100dvh-3.5rem)]"
    >
      <h2 id="roomos-live-title" className="sr-only">
        Live room view and inferred activity
      </h2>

      {/* Simulated camera / feed plate */}
      <div className="absolute inset-0 overflow-hidden">
        <motion.div
          key={primaryState}
          className={cn("absolute inset-0 bg-gradient-to-br", accent.heroMesh)}
          initial={reduceMotion ? false : { opacity: 0.88 }}
          animate={{ opacity: 1 }}
          transition={reduceMotion ? { duration: 0.12 } : { duration: 0.9, ease: "easeOut" }}
          aria-hidden
        />
        {/* Atmospheric lift — reduces flat black void */}
        <div
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_85%_70%_at_50%_38%,rgba(255,255,255,0.055)_0%,transparent_52%)]"
          aria-hidden
        />
        <div
          className="pointer-events-none absolute inset-0 bg-gradient-to-b from-zinc-800/25 via-transparent to-transparent"
          aria-hidden
        />
        <motion.div
          className="absolute inset-0 opacity-[0.055]"
          aria-hidden
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
        <div
          className="absolute inset-0 bg-gradient-to-t from-zinc-950/94 via-zinc-950/38 to-zinc-900/42"
          aria-hidden
        />
        <div
          className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_0%,rgba(0,0,0,0.38)_100%)]"
          aria-hidden
        />
      </div>

      {/* Center lens — intentional placeholder, not an empty hole */}
      <div className="pointer-events-none absolute inset-0 flex items-center justify-center p-8">
        <div
          className="flex size-[5.5rem] items-center justify-center rounded-full border border-white/[0.09] bg-zinc-950/50 text-zinc-500 shadow-[0_0_0_1px_rgba(255,255,255,0.04),inset_0_1px_0_rgba(255,255,255,0.06),0_28px_70px_-28px_rgba(0,0,0,0.55)] backdrop-blur-[2px] ring-1 ring-white/[0.04] sm:size-24"
          aria-hidden
        >
          <Camera className="size-8 opacity-50 sm:size-9" aria-hidden />
        </div>
        <span className="sr-only">Camera preview placeholder — no recording shown</span>
      </div>

      {/* Overlay UI */}
      <div className="relative z-10 mx-auto flex min-h-0 w-full max-w-[min(100%,88rem)] flex-1 flex-col gap-6 p-4 sm:gap-7 sm:p-6 lg:p-8">
        <div className="flex shrink-0 flex-col gap-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div
              role="status"
              className={cn(
                roomosUi.liveStatusPill,
                "inline-flex items-center gap-2 px-3 py-1.5",
              )}
            >
              <span className="relative flex size-2" aria-hidden>
                {!reduceMotion ? (
                  <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400/50 opacity-35 motion-reduce:animate-none" />
                ) : null}
                <span className="relative inline-flex size-2 rounded-full bg-emerald-400/90" />
              </span>
              <Camera className="size-3.5 text-zinc-300" aria-hidden />
              <span className="text-zinc-100">Live camera</span>
            </div>
            <div
              className={cn(
                roomosUi.liveStatusPill,
                "inline-flex items-center gap-2 border-emerald-500/18 px-3 py-1.5 text-emerald-50/98",
              )}
            >
              <Shield className="size-3.5 text-emerald-400/95" aria-hidden />
              <span>On-device · Private</span>
            </div>
          </div>
          <p className="max-w-2xl text-pretty text-[0.8125rem] leading-relaxed text-zinc-400 sm:text-sm">
            Haven reads your space locally, names what you are probably doing, then nudges the
            room toward comfort — calmly, and only with signals you already have here.
          </p>
        </div>

        <div className="mt-auto flex min-h-0 w-full min-w-0 flex-col gap-5 pb-1 lg:flex-row lg:items-end lg:justify-between lg:gap-10">
          <div className="min-w-0 flex-1 lg:min-w-[min(100%,28rem)]">
            <PrimaryStateOverlay
              state={snapshot.primaryState}
              confidence={snapshot.primaryConfidence}
              sceneSummary={formatSceneSummary(snapshot)}
            />
          </div>
          <div className="w-full min-w-0 shrink-0 lg:max-w-sm xl:max-w-[19.5rem]">
            <SecondaryStateConfidence
              variant="overlay"
              distribution={snapshot.distribution}
              primary={snapshot.primaryState}
            />
          </div>
        </div>
      </div>
    </section>
  )
}

function formatSceneSummary(snapshot: LiveInferenceSnapshot): string {
  const s = snapshot.appliedScene
  const fan = s.fanOn ? "Fan on" : "Fan off"
  return `Lights ${s.brightness}% · ${fan} · ${s.temperatureF}°F target`
}
