# Deterministic demo replay

When the camera, OpenCLIP download, or model bundle might fail during judging, use **demo replay**: a scripted walkthrough of room states on the **same `/live` UI** as real inference.

## Honesty rules (built in)

| Signal | Meaning |
|--------|---------|
| Amber banner on `/live` | **Demo replay active** — not live inference |
| Status chip **Demo replay ON** | Prerecorded sequence |
| `dataSource: "demo-replay"` in API snapshots | Not `roomos-ml` |
| Preview frames | Synthetic JPEGs labeled **DEMO REPLAY — not live camera** |
| Teach the room | Disabled in replay (switch to **Live camera** first) |

## Activate

### Option A — one command (recommended for flaky venues)

```bash
npm run demo:replay
```

Sets `ROOMOS_DEMO_MODE=replay`, skips model preflight, autostarts the fixture on API boot.

### Option B — backend `.env`

```env
ROOMOS_DEMO_MODE=replay
ROOMOS_DEMO_FIXTURE=configs/demo_replay.json
```

Then `npm run demo` or `npm run dev`.

### Option C — toggle on `/live` (API already running)

Use **Live camera** / **Demo replay** buttons (calls `POST /api/live/mode`).

Or:

```bash
curl -X POST http://127.0.0.1:8000/api/live/mode -H "Content-Type: application/json" -d "{\"mode\":\"replay\"}"
curl -X POST http://127.0.0.1:8000/api/live/mode -H "Content-Type: application/json" -d "{\"mode\":\"live\"}"
```

## Fixture

Default: [`backend/configs/demo_replay.json`](../backend/configs/demo_replay.json)

Sequence (loops): **work → gaming → relaxing → sleep → away** (~6s each).

Edit `steps[].rationale`, `distribution`, and `applied_scene` for your narrative.

Optional: add steps with `scripts/capture_demo_fixture.py` after saving a snapshot JSON from live mode.

## Architecture

```text
demo_replay.json
       ↓
DemoReplayEngine (background thread)
       ↓
SnapshotHub + PreviewHub  ← same as live ML engine
       ↓
GET /snapshot, WS /ws, GET /preview.jpg
       ↓
Next.js /live (unchanged hooks)
```

Live camera mode still uses OpenCV + XGBoost + train/serve gate.

## Recommended use while judging

1. **Before judges arrive:** run `npm run demo:replay` once to verify the banner and state transitions.
2. **If live works:** switch to **Live camera** on `/live` and demo real inference.
3. **If camera/model fails mid-pitch:** switch to **Demo replay** without leaving the page — say aloud: *“This is our recorded walkthrough so the UI story stays clear; live mode uses the same screen with the real classifier.”*
4. **Do not** claim replay percentages came from today’s webcam session.

## API

| Endpoint | Purpose |
|----------|---------|
| `GET /api/live/status` | `live_mode`, `demo_mode`, `data_source` |
| `POST /api/live/mode` | `{"mode":"live"\|"replay"\|"off"}` |
| `POST /api/live/start/replay` | Start replay only |
| `POST /api/live/start/live` | Start live only |

See also: [`DEMO.md`](DEMO.md), [`HANDOFF.md`](HANDOFF.md).
