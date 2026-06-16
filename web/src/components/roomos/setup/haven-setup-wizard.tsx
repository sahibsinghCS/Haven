"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { useQuery } from "@tanstack/react-query"
import { ArrowRight, Radio } from "lucide-react"

import { LiveCamerasSection } from "@/components/roomos/live-cameras-section"
import { fetchRoomsStatus } from "@/lib/roomos/api-client"
import { RoomsSettingsSection } from "@/components/roomos/rooms-settings-section"
import { SetupStepper } from "@/components/roomos/setup/setup-stepper"
import { Button } from "@/components/ui/button"
import { loadDeviceSettingsWithFallback } from "@/lib/roomos/device-settings-persistence"
import {
  loadSetupStep,
  markSetupComplete,
  saveSetupStep,
  type SetupWizardStep,
} from "@/lib/roomos/setup-session"
import { roomosUi } from "@/lib/roomos/roomos-ui"
import { useLiveSessionStore } from "@/stores/live-session-store"
import { cn } from "@/lib/utils"

function inferInitialStep(
  roomsCount: number,
  cameraSetupRequired: boolean,
  saved: SetupWizardStep | null,
): SetupWizardStep {
  if (saved) return saved
  if (roomsCount === 0) return "room"
  if (cameraSetupRequired) return "room"
  return "devices"
}

export function HavenSetupWizard({
  variant = "live",
  onGoLive,
  onDismiss,
  className,
}: {
  variant?: "live" | "connections"
  /** Live variant: enable camera and continue boot */
  onGoLive?: () => void
  onDismiss?: () => void
  className?: string
}) {
  const storeRooms = useLiveSessionStore((s) => s.rooms)
  const roomsQuery = useQuery({
    queryKey: ["roomos", "rooms"],
    queryFn: ({ signal }) => fetchRoomsStatus(signal),
    staleTime: 5_000,
  })
  const rooms = roomsQuery.data?.rooms ?? storeRooms
  const [step, setStep] = useState<SetupWizardStep>(() =>
    inferInitialStep(rooms.length, false, loadSetupStep()),
  )
  const devicesDoc = useMemo(() => loadDeviceSettingsWithFallback(), [])

  useEffect(() => {
    saveSetupStep(step)
  }, [step])

  const goTo = useCallback((next: SetupWizardStep) => setStep(next), [])

  const canAdvanceFromRoom = rooms.some((room) => room.enabled)

  const handleFinishLive = useCallback(() => {
    markSetupComplete()
    onGoLive?.()
    onDismiss?.()
  }, [onGoLive, onDismiss])

  const shellClass =
    variant === "live"
      ? cn(roomosUi.liveOverlayGlass, "border-teal-500/25 shadow-2xl")
      : cn(roomosUi.prefsCallout, "border-stone-200/90 shadow-[var(--haven-shadow-card)]")

  return (
    <div
      className={cn(shellClass, "flex w-full max-w-2xl flex-col gap-5 px-5 py-6 sm:px-7 sm:py-8", className)}
      role="region"
      aria-labelledby="haven-setup-title"
    >
      <div>
        <p
          className={cn(
            "text-[11px] font-semibold uppercase tracking-[0.22em]",
            variant === "live" ? "text-zinc-500" : "text-stone-500",
          )}
        >
          Guided setup
        </p>
        <h2
          id="haven-setup-title"
          className={cn(
            "mt-1 font-serif text-xl font-medium tracking-[-0.02em] sm:text-2xl",
            variant === "live" ? "text-zinc-50" : "text-stone-900",
          )}
        >
          Get Haven ready for live inference
        </h2>
        <p
          className={cn(
            "mt-2 text-sm leading-relaxed",
            variant === "live" ? "text-zinc-400" : "text-stone-600",
          )}
        >
          Connect cameras, assign devices, then go live when everything looks right.
        </p>
      </div>

      <SetupStepper current={step} variant={variant === "live" ? "dark" : "light"} />

      {step === "room" ? (
        <div className="space-y-4">
          <LiveCamerasSection variant={variant === "live" ? "dark" : "light"} />
          <div className="flex flex-wrap justify-end gap-2">
            <Button
              type="button"
              className={cn("gap-2", roomosUi.havenPrimaryBtn, "text-white")}
              disabled={!canAdvanceFromRoom}
              onClick={() => goTo("devices")}
            >
              Continue
              <ArrowRight className="size-4" />
            </Button>
          </div>
          {!canAdvanceFromRoom ? (
            <p className={cn("text-[11px]", variant === "live" ? "text-zinc-500" : "text-stone-500")}>
              Connect at least one camera to continue.
            </p>
          ) : null}
        </div>
      ) : null}

      {step === "devices" ? (
        <div className="space-y-4">
          <div
            className={cn(
              "rounded-xl border px-4 py-3 text-[13px] leading-relaxed",
              variant === "live"
                ? "border-white/10 bg-black/25 text-zinc-300"
                : "border-stone-200/80 bg-white/70 text-stone-700",
            )}
          >
            Assign each device to the room where it lives. Only the{" "}
            <span className="font-medium">active room</span> follows live mood scenes.
          </div>
          <RoomsSettingsSection devicesDoc={devicesDoc} variant={variant === "live" ? "dark" : "light"} />
          <p className={cn("text-[12px]", variant === "live" ? "text-zinc-500" : "text-stone-500")}>
            Need to add or test hardware?{" "}
            <Link href="/connections" className="font-medium text-teal-400 underline-offset-2 hover:underline">
              Open Connections
            </Link>
          </p>
          <div className="flex justify-between gap-2">
            <Button type="button" variant="ghost" onClick={() => goTo("room")}>
              Back
            </Button>
            <Button
              type="button"
              className={cn("gap-2", roomosUi.havenPrimaryBtn, "text-white")}
              onClick={() => (variant === "live" ? goTo("live") : handleFinishLive())}
            >
              {variant === "live" ? "Continue" : "Done"}
              <ArrowRight className="size-4" />
            </Button>
          </div>
        </div>
      ) : null}

      {step === "live" && variant === "live" ? (
        <div className="space-y-4 text-center">
          <Radio className="mx-auto size-8 text-teal-300" aria-hidden />
          <p className="text-sm leading-relaxed text-zinc-300">
 Start the inference camera. the first burst may take 15 to 30 seconds while OpenCLIP
            loads.
          </p>
          <div className="flex flex-col gap-2 sm:flex-row sm:justify-center">
            <Button type="button" variant="ghost" className="text-zinc-400" onClick={() => goTo("devices")}>
              Back
            </Button>
            <Button
              type="button"
              className={cn("gap-2", roomosUi.havenPrimaryBtn, "text-white")}
              onClick={handleFinishLive}
            >
              Start live camera
              <ArrowRight className="size-4" />
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  )
}
