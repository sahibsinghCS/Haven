# Hackathon scope (internal)

**Handoff index:** [`HANDOFF.md`](HANDOFF.md) — start there for judges/teammates.

Canonical apps: **`backend/`** + **`web/`**. **`frontend/`** is archived (see [`../frontend/ARCHIVE.md`](../frontend/ARCHIVE.md)).

---

## Minimum demo path

| Step | Route | Backend |
|------|--------|---------|
| Prep | `npm run setup:model` once | Synthetic model in `data/models/latest/` |
| 1 | `/live` | OpenCV → bursts → XGBoost → WS/poll + `preview.jpg` |
| 2 | `/live` | `POST /api/live/feedback` |
| 3 | `/preferences` | `PUT /api/preferences` |

**Do not demo:** `frontend/`, StackDemo (removed), mock snapshots (removed), full video-labeling pipeline in 90s.

---

## Feature tiers

**Must-have:** `npm run demo`, unified camera preview, honest empty states, preferences API, correction storage.

**Nice-to-have:** `train:images` on real stills, DroidCam/RTSP in `default.yaml`, `eval:report`, local webhook demo.

**Cut / removed:** browser webcam inference hook, `roomos-mock.ts`, stack calibration UI, silent mock on `/live`.

---

## Live stack truth

- **Features in production path:** CLIP + motion (`configs/inference.yaml`; pose/posture off).
- **Preview:** JPEG from inference loop, not WebRTC (`streamUrl` stays null).
- **Bootstrap model:** pipeline demo until personal `train:images`.
- **Marketing:** landing no longer claims optional cloud for this build.

---

## 90s judge script

See [`HANDOFF.md`](HANDOFF.md) and [`DEMO.md`](DEMO.md) § Judge demo path.

---

## API surface

```
GET  /api/health
GET  /api/live/status
GET  /api/live/preview.jpg
GET  /api/live/snapshot
WS   /api/live/ws
POST /api/live/start|stop
POST /api/live/feedback
GET|PUT /api/preferences
```

Camera: `backend/configs/default.yaml` → `video.source` (default `0`).

---

## Risks (demo)

| Rank | Risk | Mitigation |
|------|------|------------|
| P0 | No model | `npm run setup:model` |
| P0 | Black preview | Set `video.source: 0`; test before judging |
| P1 | Slow first CLIP download | Pre-run setup on demo laptop |
| P2 | Engine 503 race | Autostart + poll; skeleton until snapshot |
