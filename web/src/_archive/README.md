# Archived / removed (hackathon handoff)

These paths were **removed** because nothing in the demo app imported them:

| Removed | Was |
|---------|-----|
| `lib/mock/roomos-mock.ts` | Fake live snapshots — **never used on `/live`** |
| `components/room/stack-demo.tsx` | shadcn calibration demo |
| `components/room/room-trend-chart.tsx` | Placeholder chart for StackDemo |
| `stores/room-store.ts` | Zustand store for StackDemo only |
| `hooks/use-live-room-camera.ts` | Browser `getUserMedia` — replaced by backend `preview.jpg` |
| `components/roomos/confidence-history-chart.tsx` | Unused chart |
| `components/roomos/rationale-list.tsx` | Unused; rationale inline in `live-video-stage` |
| `components/roomos/applied-scene-strip.tsx` | Unused; scene targets inline in live HUD |

**Canonical UI:** `web/src/app/(dashboard)/live` and `preferences` only.
