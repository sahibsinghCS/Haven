import type {
  LiveInferenceSnapshot,
  OrchestratorMode,
  RoomStatus,
  RoomsStatusResponse,
} from "@/types/roomos"

/** Matches backend preview_dark threshold in `state.py`. */
export const PREVIEW_DARK_LUMA = 10

export type RoomSourceHealth = "off" | "waiting" | "dark" | "live"

export type RoomScanRole =
  | "inferring"
  | "active_hold"
  | "grace_scan"
  | "preview"
  | "standby"
  | "off"

export type GalleryLayoutDensity = "pair" | "grid" | "compact"

export function galleryLayoutDensity(roomCount: number): GalleryLayoutDensity {
  if (roomCount >= 4) return "compact"
  if (roomCount >= 3) return "grid"
  return "pair"
}

export function roomSourceHealth(room: RoomStatus): RoomSourceHealth {
  if (!room.enabled) return "off"
  if (!room.previewAvailable) return "waiting"
  if (
    room.previewMeanLuma != null &&
    room.previewMeanLuma < PREVIEW_DARK_LUMA
  ) {
    return "dark"
  }
  return "live"
}

export function roomScanRole(
  room: RoomStatus,
  orchestratorMode: OrchestratorMode,
): RoomScanRole {
  if (!room.enabled) return "off"
  if (room.inferenceActive) return "inferring"
  if (orchestratorMode === "away") return "standby"
  if (orchestratorMode === "grace") {
    if (room.isActive) return "active_hold"
    return "grace_scan"
  }
  if (room.isActive) return "inferring"
  return "preview"
}

export function roomDisplayMood(
  room: RoomStatus,
  snapshot: LiveInferenceSnapshot | null,
): string | null {
  if (room.inferenceActive && snapshot && snapshot.roomId === room.id) {
    return snapshot.primaryState
  }
  return room.lastMood
}

export function roomRoleLabel(role: RoomScanRole): string {
  switch (role) {
    case "inferring":
      return "Full inference"
    case "active_hold":
      return "Grace hold"
    case "grace_scan":
      return "Grace scan"
    case "preview":
      return "Preview scan"
    case "standby":
      return "Standby"
    case "off":
      return "Off"
  }
}

export function roomHealthLabel(health: RoomSourceHealth): string {
  switch (health) {
    case "live":
      return "Source live"
    case "dark":
      return "Very dark"
    case "waiting":
      return "Connecting"
    case "off":
      return "Disabled"
  }
}

export function optimisticActiveRoomPatch(
  status: RoomsStatusResponse,
  roomId: string,
): RoomsStatusResponse {
  return {
    ...status,
    activeRoomId: roomId,
    orchestratorMode:
      status.orchestratorMode === "away" ? "active" : status.orchestratorMode,
    rooms: status.rooms.map((room) => ({
      ...room,
      isActive: room.id === roomId,
      inferenceActive: room.id === roomId && room.enabled,
    })),
  }
}

export function buildRoomsStatusFromStore(patch: {
  orchestratorMode: OrchestratorMode
  activeRoomId: string | null
  graceRemainingSec: number | null
  rooms: RoomStatus[]
}): RoomsStatusResponse {
  return {
    orchestratorMode: patch.orchestratorMode,
    activeRoomId: patch.activeRoomId,
    graceDurationSec: 60,
    graceStartedAt: null,
    graceRemainingSec: patch.graceRemainingSec,
    lastPrimaryState: null,
    rooms: patch.rooms,
  }
}
