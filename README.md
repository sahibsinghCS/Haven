# HAVEN / RoomOS

A local-first room intelligence stack: a Python pipeline that samples the
camera in **short multi-frame bursts**, classifies each burst with XGBoost on
fused OpenCLIP + pose + motion features, smooths predictions over time, and
serves results to a Next.js UI over FastAPI + WebSockets.

* **`backend/`** — RoomOS Python project (OpenCLIP + MediaPipe perception,
  XGBoost classifier, live inference engine, rule-based action layer,
  FastAPI transport). See [`backend/README.md`](backend/README.md) for the
  full workflow.
* **`web/`** — Next.js frontend (live view + preferences) that consumes
  the FastAPI snapshots in real time.
* **`frontend/`** — earlier Vite scratch frontend, kept for reference.

## Quick start

```powershell
# 1. Backend
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py                 # http://127.0.0.1:8000

# 2. Frontend (in a second terminal)
cd web
npm install
npm run dev                   # http://127.0.0.1:3000
```

The live `/live` page subscribes to `ws://127.0.0.1:8000/api/live/ws`
automatically and falls back to a built-in mock if the backend or the
inference engine isn't running.

See [`backend/README.md`](backend/README.md) for capture / labeling /
training / inference / action-engine workflows.
