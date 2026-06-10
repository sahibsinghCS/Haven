"use client"

import { useState } from "react"
import { Camera, Images, Trash2 } from "lucide-react"

import { StatePreferenceCard } from "@/components/roomos/preferences/state-preference-card"
import { PrivacyConsentModal } from "@/components/roomos/moods/privacy-consent-modal"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { useMoodMutations, useMoods } from "@/hooks/use-moods"
import { buildLiveCollectUrl } from "@/lib/roomos/mood-collect-start"
import { markLiveStartIntent } from "@/lib/roomos/live-session-start"
import { useMoodSessionStore } from "@/stores/mood-session-store"
import type { ConnectedDeviceRef, MoodDefinition } from "@/types/roomos"
import { cn } from "@/lib/utils"
import { useRouter } from "next/navigation"

const ML_BADGE: Record<string, string> = {
  untrained: "bg-amber-500/10 text-amber-800 ring-amber-500/25",
  collecting: "bg-sky-500/10 text-sky-800 ring-sky-500/25",
  training: "bg-violet-500/10 text-violet-800 ring-violet-500/25",
  ready: "bg-emerald-500/10 text-emerald-800 ring-emerald-500/25",
  error: "bg-rose-500/10 text-rose-800 ring-rose-500/25",
}

function mlLabel(status: string): string {
  switch (status) {
    case "collecting":
      return "Collecting"
    case "training":
      return "Training"
    case "ready":
      return "ML ready"
    case "error":
      return "ML error"
    default:
      return "Needs training"
  }
}

export function MoodPreferenceCard({
  mood,
  connectedDevices,
  canDelete,
}: {
  mood: MoodDefinition
  connectedDevices: ConnectedDeviceRef[]
  canDelete: boolean
}) {
  const router = useRouter()
  const { data: moodsData } = useMoods()
  const { remove, consent } = useMoodMutations()
  const openBurstReview = useMoodSessionStore((s) => s.openBurstReview)
  const setPendingCollect = useMoodSessionStore((s) => s.setPendingCollect)

  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleteData, setDeleteData] = useState(false)
  const [consentOpen, setConsentOpen] = useState(false)

  const status = mood.ml?.status ?? "untrained"
  const burstCount = mood.ml?.burstCount ?? 0
  const frameCount = mood.ml?.frameCount ?? 0

  function goTeachOnLive() {
    if (!moodsData?.consent?.accepted) {
      setConsentOpen(true)
      return
    }
    setPendingCollect(mood.id, 300)
    markLiveStartIntent()
    router.push(buildLiveCollectUrl(mood.id, 300))
  }

  async function handleConsentAccept() {
    await consent.mutateAsync(true)
    setConsentOpen(false)
    setPendingCollect(mood.id, 300)
    markLiveStartIntent()
    router.push(buildLiveCollectUrl(mood.id, 300))
  }

  return (
    <div className="relative flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2 px-1">
        <Badge
          variant="outline"
          className={cn("rounded-full text-[10px] font-semibold uppercase tracking-wider ring-1", ML_BADGE[status] ?? ML_BADGE.untrained)}
        >
          {mlLabel(status)}
        </Badge>
        <div className="flex flex-wrap items-center gap-1.5">
          {(burstCount > 0 || status !== "untrained") && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-8 gap-1.5 rounded-full text-[12px]"
              onClick={() => openBurstReview(mood.id)}
            >
              <Images className="size-3.5" aria-hidden />
              Review ({burstCount})
            </Button>
          )}
          {status !== "ready" && status !== "training" && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-8 gap-1.5 rounded-full text-[12px]"
              onClick={goTeachOnLive}
            >
              <Camera className="size-3.5" aria-hidden />
              Teach camera
            </Button>
          )}
          {canDelete ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-8 gap-1.5 rounded-full text-[12px] text-rose-700 hover:bg-rose-50 hover:text-rose-800"
              onClick={() => setDeleteOpen(true)}
            >
              <Trash2 className="size-3.5" aria-hidden />
              Delete
            </Button>
          ) : null}
        </div>
      </div>
      {frameCount > 0 ? (
        <p className="px-1 text-[11px] text-[color:var(--haven-faint)]">
          {frameCount} frames · {burstCount} bursts on this device
        </p>
      ) : null}
      <StatePreferenceCard stateId={mood.id} connectedDevices={connectedDevices} />

      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Delete “{mood.displayName}”?</DialogTitle>
            <DialogDescription>
              This removes the mood from preferences and live predictions. You can restore
              preloaded moods later from Add mood.
            </DialogDescription>
          </DialogHeader>
          <label className="flex items-start gap-2 text-[13px] text-[color:var(--haven-muted)]">
            <input
              type="checkbox"
              className="mt-1"
              checked={deleteData}
              onChange={(e) => setDeleteData(e.target.checked)}
            />
            Also delete on-device training frames for this mood
          </label>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setDeleteOpen(false)}>
              Cancel
            </Button>
            <Button
              type="button"
              variant="destructive"
              disabled={remove.isPending}
              onClick={() => {
                void remove.mutateAsync({ moodId: mood.id, deleteData }).then(() => {
                  setDeleteOpen(false)
                })
              }}
            >
              Delete mood
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <PrivacyConsentModal
        open={consentOpen}
        datasetFolder={moodsData?.datasetFolder}
        busy={consent.isPending}
        onAccept={() => void handleConsentAccept()}
        onDecline={() => setConsentOpen(false)}
      />
    </div>
  )
}
