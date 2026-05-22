# RoomOS web UI (Next.js)

Canonical frontend for the hackathon demo. Started by `npm run demo` or `npm run dev` from the **repo root** (not from this folder alone).

## Routes

| Route | Purpose |
|-------|---------|
| `/` | Marketing landing (static) |
| `/live` | Live inference HUD — **real FastAPI snapshots + backend camera preview** |
| `/preferences` | Mood presets → saved via `PUT /api/preferences` |

## Environment

| Variable | Default |
|----------|---------|
| `NEXT_PUBLIC_ROOMOS_API_BASE` | `http://127.0.0.1:8000` |
| `NEXT_PUBLIC_ROOMOS_WS_BASE` | derived from API base (`ws` / `wss`) |

## Development

From repo root:

```bash
npm run dev        # web + API (no preflight)
npm run build      # production build (lint via npm run lint)
```

From this directory only (API must already run on :8000):

```bash
npm install
npm run dev
```

## Data flow (`/live`)

1. `useLiveEngineAutostart` — `POST /api/live/start` if needed  
2. `useLiveInference` — WebSocket `/api/live/ws` + 2s HTTP poll on `/api/live/snapshot`  
3. `useInferenceCameraPreview` — polls `/api/live/preview.jpg`  

No mock inference path. Removed unused code is documented in [`src/_archive/README.md`](src/_archive/README.md).

## Handoff

See [`../docs/HANDOFF.md`](../docs/HANDOFF.md) and [`../docs/DEMO.md`](../docs/DEMO.md).
