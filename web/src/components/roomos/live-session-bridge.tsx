"use client"

import { useEffect } from "react"
import { usePathname } from "next/navigation"

import { useLiveEngineAutostart } from "@/hooks/use-live-engine"
import { useLiveInference } from "@/hooks/use-live-inference"
import { useLiveSessionStore } from "@/stores/live-session-store"

/**
 * Keeps inference engine + snapshot stream alive while navigating away from /live.
 * Mount once in the dashboard shell.
 */
export function LiveSessionBridge() {
  const pathname = usePathname()
  const isLive = pathname === "/live"
  const cameraEnabled = useLiveSessionStore((s) => s.cameraEnabled)
  const engineWasRunning = useLiveSessionStore((s) => s.engineWasRunning)
  const setEngineWasRunning = useLiveSessionStore((s) => s.setEngineWasRunning)
  const setLiveInference = useLiveSessionStore((s) => s.setLiveInference)
  const setEngineSession = useLiveSessionStore((s) => s.setEngineSession)

  const shouldRunEngine = cameraEnabled && (isLive || engineWasRunning)
  const shouldStreamInference = cameraEnabled && (isLive || engineWasRunning)

  const engine = useLiveEngineAutostart(shouldRunEngine)
  const live = useLiveInference(shouldStreamInference)

  useEffect(() => {
    if (engine.status === "running") {
      setEngineWasRunning(true)
    }
  }, [engine.status, setEngineWasRunning])

  useEffect(() => {
    setLiveInference({
      snapshot: live.snapshot,
      liveStatus: live.status,
      liveMessage: live.message,
      lastFeedbackEvent: live.lastFeedbackEvent,
      lastPreferencesEvent: live.lastPreferencesEvent,
    })
  }, [
    live.snapshot,
    live.status,
    live.message,
    live.lastFeedbackEvent,
    live.lastPreferencesEvent,
    setLiveInference,
  ])

  useEffect(() => {
    setEngineSession({
      engineStatus: engine.status,
      engineMessage: engine.message,
      inferenceSource: engine.inferenceSource,
      previewAvailable: engine.previewAvailable,
      previewMeanLuma: engine.previewMeanLuma,
      previewDark: engine.previewDark,
      previewFit: engine.previewFit,
      bootPhase: engine.bootPhase,
      modelKind: engine.modelKind,
      compatReport: engine.compatReport,
      liveMode: engine.liveMode,
    })
  }, [
    engine.status,
    engine.message,
    engine.inferenceSource,
    engine.previewAvailable,
    engine.previewMeanLuma,
    engine.previewDark,
    engine.previewFit,
    engine.bootPhase,
    engine.modelKind,
    engine.compatReport,
    engine.liveMode,
    setEngineSession,
  ])

  return null
}
