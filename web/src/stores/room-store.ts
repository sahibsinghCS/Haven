import { create } from "zustand"

export type RoomUiPhase = "idle" | "connecting" | "live" | "error"

export type RoomSnapshot = {
  phase: RoomUiPhase
  lastEventAt: number | null
  lastMessage: string | null
}

type RoomStore = RoomSnapshot & {
  setPhase: (phase: RoomUiPhase) => void
  touchEvent: (message: string) => void
  reset: () => void
}

const initial: RoomSnapshot = {
  phase: "idle",
  lastEventAt: null,
  lastMessage: null,
}

export const useRoomStore = create<RoomStore>((set) => ({
  ...initial,
  setPhase: (phase) => set({ phase }),
  touchEvent: (message) =>
    set({ lastEventAt: Date.now(), lastMessage: message, phase: "live" }),
  reset: () => set(initial),
}))
