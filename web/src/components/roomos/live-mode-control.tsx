"use client"

import { useCallback, useState } from "react"
import { Clapperboard, Radio, Video } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { setLiveMode, type LiveMode } from "@/lib/roomos/api-client"
import { cn } from "@/lib/utils"

export function LiveModeControl({
  liveMode,
  onModeChanged,
  className,
}: {
  liveMode: LiveMode
  onModeChanged: () => void
  className?: string
}) {
  const [busy, setBusy] = useState(false)

  const switchMode = useCallback(
    async (mode: "live" | "replay") => {
      if (busy || liveMode === mode) return
      setBusy(true)
      try {
        const result = await setLiveMode(mode)
        if (result.status === "error") {
          toast.error(result.error ?? "Could not switch mode")
          return
        }
        toast.success(
          mode === "replay"
            ? "Demo replay on — prerecorded sequence (not live camera)"
            : "Live mode on — real camera + model",
        )
        onModeChanged()
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Mode switch failed")
      } finally {
        setBusy(false)
      }
    },
    [busy, liveMode, onModeChanged],
  )

  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-2 rounded-xl border border-white/10 bg-zinc-950/60 px-3 py-2 backdrop-blur-md",
        className,
      )}
      role="group"
      aria-label="Live or demo replay mode"
    >
      <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-500">
        Source
      </span>
      <Button
        type="button"
        size="sm"
        variant={liveMode === "live" ? "default" : "outline"}
        className={cn(
          "h-8 gap-1.5 text-xs",
          liveMode === "live" && "bg-teal-700 hover:bg-teal-600",
        )}
        disabled={busy}
        onClick={() => void switchMode("live")}
      >
        <Video className="size-3.5" aria-hidden />
        Live camera
      </Button>
      <Button
        type="button"
        size="sm"
        variant={liveMode === "replay" ? "default" : "outline"}
        className={cn(
          "h-8 gap-1.5 text-xs",
          liveMode === "replay" && "bg-amber-700 hover:bg-amber-600",
        )}
        disabled={busy}
        onClick={() => void switchMode("replay")}
      >
        <Clapperboard className="size-3.5" aria-hidden />
        Demo replay
      </Button>
      {liveMode === "replay" ? (
        <span className="inline-flex items-center gap-1 text-[10px] font-medium text-amber-200/90">
          <Radio className="size-3" aria-hidden />
          Not live inference
        </span>
      ) : null}
    </div>
  )
}
