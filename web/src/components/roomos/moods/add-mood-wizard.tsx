"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { Plus } from "lucide-react"

import { PrivacyConsentModal } from "@/components/roomos/moods/privacy-consent-modal"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Slider } from "@/components/ui/slider"
import { useMoodMutations, useMoods } from "@/hooks/use-moods"
import { buildLiveCollectUrl } from "@/lib/roomos/mood-collect-start"
import { markLiveStartIntent } from "@/lib/roomos/live-session-start"
import { roomosUi } from "@/lib/roomos/roomos-ui"
import { useLiveSessionStore } from "@/stores/live-session-store"
import { useMoodSessionStore } from "@/stores/mood-session-store"
import type { MoodDefinition } from "@/types/roomos"
import { cn } from "@/lib/utils"

type Step = "choose" | "teach"

export function AddMoodWizard({
  onMoodCreated,
}: {
  onMoodCreated?: (mood: MoodDefinition) => void
}) {
  const router = useRouter()
  const { data: moodsData } = useMoods()
  const { create, consent } = useMoodMutations()
  const setPendingCollect = useMoodSessionStore((s) => s.setPendingCollect)

  const [open, setOpen] = useState(false)
  const [step, setStep] = useState<Step>("choose")
  const [customName, setCustomName] = useState("")
  const [createdMood, setCreatedMood] = useState<MoodDefinition | null>(null)
  const [durationMin, setDurationMin] = useState(5)
  const [consentOpen, setConsentOpen] = useState(false)
  const [pendingTeach, setPendingTeach] = useState(false)
  const [trainAllRooms, setTrainAllRooms] = useState(false)
  const rooms = useLiveSessionStore((s) => s.rooms)

  const restorable = moodsData?.restorableBuiltins ?? []
  const consentAccepted = moodsData?.consent?.accepted ?? false

  useEffect(() => {
    if (!open) {
      setStep("choose")
      setCustomName("")
      setCreatedMood(null)
      setDurationMin(5)
      setPendingTeach(false)
    }
  }, [open])

  const durationSec = durationMin * 60

  async function handleCreateBuiltin(builtinKey: string) {
    const mood = await create.mutateAsync({ builtinKey })
    setCreatedMood(mood)
    onMoodCreated?.(mood)
    setStep("teach")
  }

  async function handleCreateCustom() {
    const mood = await create.mutateAsync({ name: customName.trim() })
    setCreatedMood(mood)
    onMoodCreated?.(mood)
    setStep("teach")
  }

  function beginTeachOnLive() {
    if (!createdMood) return
    if (!consentAccepted) {
      setPendingTeach(true)
      setConsentOpen(true)
      return
    }
    void navigateToLiveCollect(createdMood.id)
  }

  async function navigateToLiveCollect(moodId: string) {
    const roomIds =
      trainAllRooms && rooms.length > 0
        ? rooms.filter((r) => r.enabled).map((r) => r.id)
        : []
    setPendingCollect(moodId, durationSec, roomIds)
    markLiveStartIntent()
    setOpen(false)
    router.push(buildLiveCollectUrl(moodId, durationSec))
  }

  async function handleConsentAccept() {
    await consent.mutateAsync(true)
    setConsentOpen(false)
    if (pendingTeach && createdMood) {
      setPendingTeach(false)
      await navigateToLiveCollect(createdMood.id)
    }
  }

  return (
    <>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogTrigger asChild>
          <button
            type="button"
            className={cn(
              "group flex min-h-[12rem] flex-col items-center justify-center gap-3 rounded-[1.35rem]",
              "border border-dashed border-[color:var(--haven-line-strong)] bg-white/40",
              "transition-colors hover:border-teal-500/35 hover:bg-teal-50/30",
              roomosUi.focusRingLight,
            )}
          >
            <span className="flex size-11 items-center justify-center rounded-full bg-stone-900/[0.06] text-[color:var(--haven-ink)] transition group-hover:bg-teal-600/10 group-hover:text-teal-800">
              <Plus className="size-5" aria-hidden />
            </span>
            <span className="haven-display text-[1.05rem] font-semibold text-[color:var(--haven-ink)]">
              Add mood
            </span>
            <span className="max-w-[12rem] text-center text-[12px] leading-relaxed text-[color:var(--haven-muted)]">
              Custom name or restore a preloaded mood
            </span>
          </button>
        </DialogTrigger>
        <DialogContent className="max-w-lg gap-0 p-0 sm:max-w-xl">
          {step === "choose" ? (
            <>
              <div className="border-b border-[color:var(--haven-line)] px-6 py-5">
                <DialogHeader className="text-left">
                  <DialogTitle className="haven-display text-xl font-semibold">
                    Add a mood
                  </DialogTitle>
                  <DialogDescription className="text-[13px]">
                    Choose a custom name or bring back one of the four preloaded moods.
                  </DialogDescription>
                </DialogHeader>
              </div>
              <div className="space-y-5 px-6 py-5">
                <div className="space-y-2">
                  <Label htmlFor="custom-mood-name">Custom mood name</Label>
                  <Input
                    id="custom-mood-name"
                    placeholder="e.g. Reading, Yoga, Focus"
                    value={customName}
                    onChange={(e) => setCustomName(e.target.value)}
                    maxLength={40}
                  />
                  <Button
                    type="button"
                    className={cn("w-full", roomosUi.havenPrimaryBtn, "text-white")}
                    disabled={customName.trim().length < 2 || create.isPending}
                    onClick={() => void handleCreateCustom()}
                  >
                    Create custom mood
                  </Button>
                </div>
                {restorable.length > 0 ? (
                  <div className="space-y-2 border-t border-[color:var(--haven-line)] pt-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[color:var(--haven-muted)]">
                      Restore preloaded
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {restorable.map((b) => (
                        <Button
                          key={b.builtinKey}
                          type="button"
                          variant="outline"
                          size="sm"
                          className="rounded-full"
                          disabled={create.isPending}
                          onClick={() => void handleCreateBuiltin(b.builtinKey)}
                        >
                          {b.displayName}
                        </Button>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            </>
          ) : (
            <>
              <div className="border-b border-[color:var(--haven-line)] px-6 py-5">
                <DialogHeader className="text-left">
                  <DialogTitle className="haven-display text-xl font-semibold">
 Teach the camera. {createdMood?.displayName}
                  </DialogTitle>
                  <DialogDescription className="text-[13px] leading-relaxed">
                    Act out this mood in front of the camera. Frames stay on this device and
                    train a personal classifier for you only.
                  </DialogDescription>
                </DialogHeader>
              </div>
              <div className="space-y-5 px-6 py-5">
                <div className="space-y-3">
                  <div className="flex items-center justify-between text-[13px]">
                    <Label>Collection duration</Label>
                    <span className="font-mono tabular-nums text-[color:var(--haven-muted)]">
                      {durationMin} min
                    </span>
                  </div>
                  <Slider
                    min={1}
                    max={30}
                    step={1}
                    value={[durationMin]}
                    onValueChange={([v]) => setDurationMin(v ?? 5)}
                  />
                </div>
                {rooms.length > 1 ? (
                  <label className="flex cursor-pointer items-start gap-2 rounded-xl border border-[color:var(--haven-line)] bg-stone-50/80 px-3 py-2.5 text-[12.5px] leading-relaxed text-[color:var(--haven-muted)]">
                    <input
                      type="checkbox"
                      checked={trainAllRooms}
                      className="mt-0.5 size-3.5"
                      onChange={(e) => setTrainAllRooms(e.target.checked)}
                    />
                    <span>
                      Collect in all enabled rooms (otherwise only the active room on Live).
                    </span>
                  </label>
                ) : (
                  <p className="rounded-xl border border-[color:var(--haven-line)] bg-stone-50/80 px-3 py-2.5 text-[12.5px] leading-relaxed text-[color:var(--haven-muted)]">
                    Capture runs until you hit at least 12 bursts (20 recommended), or the timer
                    ends. Only your on device frames train this mood, not the built in multi room
                    photos.
                  </p>
                )}
              </div>
              <DialogFooter className="border-t border-[color:var(--haven-line)] px-6 py-4">
                <Button type="button" variant="outline" onClick={() => setOpen(false)}>
                  Set preferences later
                </Button>
                <Button
                  type="button"
                  className={cn(roomosUi.havenPrimaryBtn, "text-white")}
                  onClick={beginTeachOnLive}
                >
                  Start training on Live
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>

      <PrivacyConsentModal
        open={consentOpen}
        datasetFolder={moodsData?.datasetFolder}
        busy={consent.isPending}
        onAccept={() => void handleConsentAccept()}
        onDecline={() => {
          setConsentOpen(false)
          setPendingTeach(false)
        }}
      />
    </>
  )
}
