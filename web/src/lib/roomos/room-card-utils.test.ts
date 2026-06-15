/**
 * run: npx tsx src/lib/roomos/room-card-utils.test.ts
 */
import assert from "node:assert/strict"

import {
  galleryLayoutDensity,
  optimisticActiveRoomPatch,
  roomScanRole,
  roomSourceHealth,
} from "./room-card-utils"
import type { RoomStatus, RoomsStatusResponse } from "@/types/roomos"

const baseRoom = (id: string, overrides: Partial<RoomStatus> = {}): RoomStatus => ({
  id,
  name: id,
  enabled: true,
  camera: { source: 0, backend: "dshow" },
  deviceIds: [],
  isActive: false,
  inferenceActive: false,
  previewAvailable: true,
  previewMeanLuma: 40,
  lastMood: null,
  ...overrides,
})

assert.equal(galleryLayoutDensity(1), "pair")
assert.equal(galleryLayoutDensity(2), "pair")
assert.equal(galleryLayoutDensity(3), "grid")
assert.equal(galleryLayoutDensity(4), "compact")
assert.equal(galleryLayoutDensity(6), "compact")

assert.equal(roomSourceHealth(baseRoom("a", { enabled: false })), "off")
assert.equal(
  roomSourceHealth(baseRoom("a", { previewAvailable: false })),
  "waiting",
)
assert.equal(
  roomSourceHealth(baseRoom("a", { previewMeanLuma: 5 })),
  "dark",
)
assert.equal(roomSourceHealth(baseRoom("a")), "live")

assert.equal(
  roomScanRole(baseRoom("a", { inferenceActive: true }), "active"),
  "inferring",
)
assert.equal(
  roomScanRole(baseRoom("a", { isActive: true }), "grace"),
  "active_hold",
)
assert.equal(
  roomScanRole(baseRoom("a"), "grace"),
  "grace_scan",
)
assert.equal(roomScanRole(baseRoom("a"), "away"), "standby")

const status: RoomsStatusResponse = {
  orchestratorMode: "active",
  activeRoomId: "a",
  graceDurationSec: 60,
  graceStartedAt: null,
  graceRemainingSec: null,
  lastPrimaryState: null,
  rooms: [
    baseRoom("a", { isActive: true, inferenceActive: true }),
    baseRoom("b"),
  ],
}
const patched = optimisticActiveRoomPatch(status, "b")
assert.equal(patched.activeRoomId, "b")
assert.equal(patched.rooms.find((r) => r.id === "b")?.isActive, true)
assert.equal(patched.rooms.find((r) => r.id === "b")?.inferenceActive, true)
assert.equal(patched.rooms.find((r) => r.id === "a")?.isActive, false)

console.log("room-card-utils.test.ts: ok")
