"use client"

import Link from "next/link"
import { Shield } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { roomosUi } from "@/lib/roomos/roomos-ui"
import { cn } from "@/lib/utils"

export function PrivacyConsentModal({
  open,
  datasetFolder,
  busy,
  onAccept,
  onDecline,
}: {
  open: boolean
  datasetFolder?: string
  busy?: boolean
  onAccept: () => void
  onDecline: () => void
}) {
  return (
    <Dialog open={open} onOpenChange={(v) => !v && onDecline()}>
      <DialogContent className="max-w-md gap-0 p-0 sm:max-w-lg">
        <div className="border-b border-[color:var(--haven-line)] px-6 py-5">
          <DialogHeader className="space-y-3 text-left">
            <div className="flex items-center gap-3">
              <span className="flex size-10 items-center justify-center rounded-2xl bg-teal-500/10 text-teal-700 ring-1 ring-teal-500/20">
                <Shield className="size-5" aria-hidden />
              </span>
              <DialogTitle className="haven-display text-xl font-semibold tracking-tight">
                On-device training data
              </DialogTitle>
            </div>
            <DialogDescription className="text-[13.5px] leading-relaxed text-[color:var(--haven-muted)]">
              Before Haven saves camera frames for a custom mood, here is how your data is
              handled.
            </DialogDescription>
          </DialogHeader>
        </div>
        <ul className="space-y-3 px-6 py-5 text-[13px] leading-relaxed text-[color:var(--haven-muted)]">
          <li className="flex gap-2">
            <span className="font-semibold text-[color:var(--haven-ink)]">1.</span>
 Frames are stored only on this computer. never uploaded to the cloud.
          </li>
          <li className="flex gap-2">
            <span className="font-semibold text-[color:var(--haven-ink)]">2.</span>
            Your captures are not used to train models for other users.
          </li>
          <li className="flex gap-2">
            <span className="font-semibold text-[color:var(--haven-ink)]">3.</span>
            You can review and delete bursts or frames anytime before training.
          </li>
        </ul>
        {datasetFolder ? (
          <p className="px-6 pb-2 font-mono text-[10px] leading-relaxed text-[color:var(--haven-faint)]">
            Dataset folder: {datasetFolder}
          </p>
        ) : null}
        <DialogFooter className="flex-col gap-2 border-t border-[color:var(--haven-line)] px-6 py-4 sm:flex-row sm:justify-end">
          <Button type="button" variant="outline" onClick={onDecline} disabled={busy}>
            Cancel
          </Button>
          <Button
            type="button"
            className={cn(roomosUi.havenPrimaryBtn, "text-white")}
            onClick={onAccept}
            disabled={busy}
          >
 I understand. continue
          </Button>
        </DialogFooter>
        <p className="px-6 pb-5 text-center text-[11px] text-[color:var(--haven-faint)]">
          Advanced: open{" "}
          <Link href="/connections" className="underline underline-offset-2">
            Connections
          </Link>{" "}
          for device settings.
        </p>
      </DialogContent>
    </Dialog>
  )
}
