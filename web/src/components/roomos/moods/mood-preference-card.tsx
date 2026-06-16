"use client"

import { useState } from "react"
import { Camera, Images, Trash2 } from "lucide-react"

import { MoodLifecycleChip } from "@/components/roomos/moods/mood-lifecycle-chip"
import { StatePreferenceCard } from "@/components/roomos/preferences/state-preference-card"
import { PrivacyConsentModal } from "@/components/roomos/moods/privacy-consent-modal"
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
  const lifecycle = mood.lifecycle
  const burstCount = mood.ml?.burstCount ?? 0
  const collapseDevices = connectedDevices.length > 3
  const canTeach =
    mood.inferenceEligible !== true &&
    status !== "training" &&
    lifecycle !== "inference_hidden"

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
      <div className="flex flex-wrap items-start justify-between gap-2">
        <MoodLifecycleChip mood={mood} />
        <div className="flex flex-wrap items-center gap-1.5 px-1">
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
          {canTeach && (
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
      <StatePreferenceCard
        stateId={mood.id}
        connectedDevices={connectedDevices}
        collapseDevices={collapseDevices}
      />

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
            Also delete on device training frames for this mood
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
