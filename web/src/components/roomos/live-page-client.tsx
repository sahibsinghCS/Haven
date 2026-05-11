"use client"

import { useEffect } from "react"
import { useQuery } from "@tanstack/react-query"

import { LiveStageSkeleton } from "@/components/roomos/roomos-loading-states"
import { LiveVideoStage } from "@/components/roomos/live-video-stage"
import { fetchMockLiveSnapshot } from "@/lib/mock/roomos-mock"
import { roomosUi } from "@/lib/roomos/roomos-ui"
import { useRoomOsAmbientStore } from "@/stores/roomos-store"
import { cn } from "@/lib/utils"

export function LivePageClient() {
  const setPrimaryState = useRoomOsAmbientStore((s) => s.setPrimaryState)

  const live = useQuery({
    queryKey: ["roomos", "live"],
    queryFn: fetchMockLiveSnapshot,
    refetchInterval: 12_000,
  })

  useEffect(() => {
    if (!live.data) return
    setPrimaryState(live.data.primaryState)
  }, [live.data, setPrimaryState])

  useEffect(() => {
    return () => setPrimaryState(null)
  }, [setPrimaryState])

  if (live.isPending) {
    return <LiveStageSkeleton />
  }

  if (live.isError) {
    return (
      <div className="flex min-h-[40svh] flex-1 items-center justify-center px-4 py-12">
        <div
          className={cn(
            roomosUi.liveOverlayGlass,
            "text-rose-100 border-rose-500/20 max-w-md p-6 text-sm",
          )}
        >
          <p className="text-zinc-100 font-medium">Live view unavailable</p>
          <p className="text-rose-200/80 mt-2 text-xs leading-relaxed">
            We could not load the latest snapshot. Try again shortly.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <LiveVideoStage snapshot={live.data} />
    </div>
  )
}
