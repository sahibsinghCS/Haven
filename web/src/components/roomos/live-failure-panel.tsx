"use client"

import { AlertTriangle, ServerCrash } from "lucide-react"

import { HavenCompatDetails } from "@/components/roomos/haven-compat-details"
import { HavenModeBadge } from "@/components/roomos/haven-mode-badge"
import { HavenOperatorActions } from "@/components/roomos/haven-operator-actions"
import { HavenSurfaceState } from "@/components/roomos/haven-surface-state"
import { LiveCameraPowerButton } from "@/components/roomos/live-camera-power"
import {
  FAILURE_COPY,
  classifyLiveFailure,
  type LiveFailureKind,
} from "@/lib/roomos/haven-system-state"
import type { CompatReport } from "@/lib/roomos/api-client"
import type { LiveInferenceStatus } from "@/hooks/use-live-inference"

const MODE_FOR_FAILURE: Record<
  LiveFailureKind,
  "api_offline" | "compat_error" | "model_missing" | "engine_error" | "camera_error"
> = {
  api_offline: "api_offline",
  compat_error: "compat_error",
  model_missing: "model_missing",
  engine_error: "engine_error",
  camera_error: "camera_error",
  no_data: "engine_error",
}

export function LiveFailurePanel({
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
  compatReport?: CompatReport | null
}) {
  const kind = classifyLiveFailure({
    engineStatus,
    liveStatus,
    engineMessage,
    liveMessage,
    compatReport,
  })
  const copy = FAILURE_COPY[kind]
  const hint = engineMessage ?? liveMessage
  const badgeMode = MODE_FOR_FAILURE[kind]

  return (
    <div className="relative flex min-h-[50svh] flex-1 items-center justify-center px-4 py-16">
      <div className="absolute left-3 top-3 z-30 sm:left-4 sm:top-4">
        <LiveCameraPowerButton />
      </div>
      <HavenSurfaceState
        variant="dark"
        tone={kind === "compat_error" ? "error" : kind === "api_offline" ? "warn" : "warn"}
        role="alert"
        icon={
          kind === "api_offline" ? (
            <ServerCrash className="size-6 text-amber-300/90" />
          ) : (
            <AlertTriangle className="size-6 text-rose-300/90" />
          )
        }
        eyebrow={
          <span className="inline-flex justify-center">
            <HavenModeBadge mode={badgeMode} size="md" />
          </span>
        }
        title={copy.title}
        description={
          <>
            {copy.description}
            {hint && hint !== copy.title ? (
              <span className="mt-2 block rounded-md border border-white/[0.08] bg-black/30 px-2 py-1.5 font-mono text-[11px] leading-snug text-zinc-400">
                {hint}
              </span>
            ) : null}
          </>
        }
        className="max-w-xl"
      >
        {kind === "compat_error" && compatReport?.mismatches?.length ? (
          <HavenCompatDetails mismatches={compatReport.mismatches} />
        ) : null}
        <div className="border-t border-white/[0.08] pt-4">
          <HavenOperatorActions actions={copy.actions} />
        </div>
        <p className="mt-4 font-mono text-[10px] uppercase tracking-wider text-zinc-600">
          api={liveStatus} · engine={engineStatus}
        </p>
      </HavenSurfaceState>
    </div>
  )
}
