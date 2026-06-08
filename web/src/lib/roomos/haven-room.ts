const STORAGE_KEY = "haven.room.id.v1"

export function getHavenRoomId(): string {
  if (typeof window === "undefined") {
    return process.env.NEXT_PUBLIC_HAVEN_ROOM_ID?.trim() || "default"
  }
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)?.trim()
    if (stored) return stored
  } catch {
    /* ignore */
  }
  const fromEnv = process.env.NEXT_PUBLIC_HAVEN_ROOM_ID?.trim()
  return fromEnv || "default"
}

export function setHavenRoomId(roomId: string): void {
  if (typeof window === "undefined") return
  const value = roomId.trim() || "default"
  window.localStorage.setItem(STORAGE_KEY, value)
}

export function havenRequestHeaders(extra?: HeadersInit): HeadersInit {
  return {
    "Content-Type": "application/json",
    "X-Haven-Room-Id": getHavenRoomId(),
    ...extra,
  }
}
