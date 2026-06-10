"use client"

import { create } from "zustand"

import type { LiveEngineHookStatus } from "@/hooks/use-live-engine"
import type { LiveInferenceStatus } from "@/hooks/use-live-inference"
import type { BootPhase, CompatReport, LiveMode, ModelKind } from "@/lib/roomos/api-client"
import type { LiveFeedbackEvent } from "@/types/feedback-event"
import type { LivePreferencesEvent } from "@/types/preferences-event"
import type { LiveInferenceSnapshot } from "@/types/roomos"

type LiveSessionStore = {
  /** User wants the inference camera on (power toggle). */
  cameraEnabled: boolean
  /** Engine was started this session — keep inference WS alive across /live navigation. */
  engineWasRunning: boolean
  /** MJPEG preview has delivered at least one frame this session. */
  previewStreamLive: boolean
  setCameraEnabled: (enabled: boolean) => void
  setEngineWasRunning: (running: boolean) => void
  setPreviewStreamLive: (live: boolean) => void
  /** Clear inference + engine UI state after the user powers the camera off. */
  resetForCameraOff: () => void

  snapshot: LiveInferenceSnapshot | null
  liveStatus: LiveInferenceStatus
  liveMessage: string | null
  lastFeedbackEvent: LiveFeedbackEvent | null
  lastPreferencesEvent: LivePreferencesEvent | null
  setLiveInference: (patch: {
    snapshot?: LiveInferenceSnapshot | null
    liveStatus?: LiveInferenceStatus
    liveMessage?: string | null
    lastFeedbackEvent?: LiveFeedbackEvent | null
    lastPreferencesEvent?: LivePreferencesEvent | null
  }) => void
  dismissFeedbackEvent: () => void
  dismissPreferencesEvent: () => void

  engineStatus: LiveEngineHookStatus
  engineMessage: string | null
  inferenceSource: string | null
  previewAvailable: boolean
  previewMeanLuma: number | null
  previewDark: boolean
  previewFit: "cover" | "contain"
  bootPhase: BootPhase
  modelKind: ModelKind
  compatReport: CompatReport | null
  liveMode: LiveMode
  setEngineSession: (patch: Partial<Omit<LiveSessionStore, "setLiveInference" | "setEngineSession" | "dismissFeedbackEvent" | "dismissPreferencesEvent" | "setCameraEnabled" | "setEngineWasRunning" | "setPreviewStreamLive" | "resetForCameraOff">>) => void
}

export const useLiveSessionStore = create<LiveSessionStore>((set) => ({
  cameraEnabled: false,
  engineWasRunning: false,
  previewStreamLive: false,
  setCameraEnabled: (cameraEnabled) => set({ cameraEnabled }),
  setEngineWasRunning: (engineWasRunning) => set({ engineWasRunning }),
  setPreviewStreamLive: (previewStreamLive) => set({ previewStreamLive }),
  resetForCameraOff: () =>
    set({
      snapshot: null,
      liveStatus: "connecting",
      liveMessage: null,
      engineStatus: "idle",
      engineMessage: null,
      previewStreamLive: false,
      previewAvailable: false,
      previewMeanLuma: null,
      previewDark: false,
      bootPhase: "off",
      liveMode: "off",
      inferenceSource: null,
    }),

  snapshot: null,
  liveStatus: "connecting",
  liveMessage: null,
  lastFeedbackEvent: null,
  lastPreferencesEvent: null,
  setLiveInference: (patch) => set((s) => ({ ...s, ...patch })),
  dismissFeedbackEvent: () => set({ lastFeedbackEvent: null }),
  dismissPreferencesEvent: () => set({ lastPreferencesEvent: null }),

  engineStatus: "idle",
  engineMessage: null,
  inferenceSource: null,
  previewAvailable: false,
  previewMeanLuma: null,
  previewDark: false,
  previewFit: "cover",
  bootPhase: "off",
  modelKind: "unknown",
  compatReport: null,
  liveMode: "off",
  setEngineSession: (patch) => set((s) => ({ ...s, ...patch })),
}))
