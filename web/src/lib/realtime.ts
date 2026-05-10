import ReconnectingWebSocket from "reconnecting-websocket"

export type RoomSocketHandlers = {
  onOpen?: () => void
  /** Fired when the socket closes (normalized shape; avoids DOM vs RWS `CloseEvent` mismatch). */
  onClose?: (event: { code: number; reason: string; wasClean: boolean }) => void
  onMessage?: (data: unknown) => void
  onError?: (event: unknown) => void
}

/**
 * Browser WebSocket client with automatic reconnect (via `reconnecting-websocket`).
 * Point `url` at your FastAPI (or other) WS endpoint, e.g. from `NEXT_PUBLIC_WS_URL`.
 */
export function createRoomSocket(
  url: string,
  handlers: RoomSocketHandlers = {},
): ReconnectingWebSocket {
  const socket = new ReconnectingWebSocket(url, [], {
    maxReconnectionDelay: 10_000,
    minReconnectionDelay: 1_000,
    connectionTimeout: 4_000,
  })

  socket.addEventListener("open", () => handlers.onOpen?.())
  socket.addEventListener("close", (e) =>
    handlers.onClose?.({
      code: e.code,
      reason: e.reason,
      wasClean: e.wasClean,
    }),
  )
  socket.addEventListener("error", (e) => handlers.onError?.(e))
  socket.addEventListener("message", (event) => {
    try {
      const parsed = JSON.parse(String(event.data)) as unknown
      handlers.onMessage?.(parsed)
    } catch {
      handlers.onMessage?.(event.data)
    }
  })

  return socket
}
