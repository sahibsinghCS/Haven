"use client"

import { useMutation } from "@tanstack/react-query"
import { toast } from "sonner"

import {
  buildRoomsStatusFromStore,
  optimisticActiveRoomPatch,
} from "@/lib/roomos/room-card-utils"
import { setActiveRoom, setRoomEnabled } from "@/lib/roomos/api-client"
import { useLiveSessionStore } from "@/stores/live-session-store"

export function useRoomOrchestrationActions() {
  const setRoomsStatus = useLiveSessionStore((s) => s.setRoomsStatus)

  const activateRoom = useMutation({
    mutationFn: (roomId: string) => setActiveRoom(roomId),
    onMutate: (roomId) => {
      const state = useLiveSessionStore.getState()
      setRoomsStatus(
        optimisticActiveRoomPatch(buildRoomsStatusFromStore(state), roomId),
      )
    },
    onSuccess: (data) => setRoomsStatus(data),
    onError: (e: Error) => toast.error(e.message),
  })

  const toggleEnabled = useMutation({
    mutationFn: ({ roomId, enabled }: { roomId: string; enabled: boolean }) =>
      setRoomEnabled(roomId, enabled),
    onSuccess: (data) => setRoomsStatus(data),
    onError: (e: Error) => toast.error(e.message),
  })

  return { activateRoom, toggleEnabled }
}
