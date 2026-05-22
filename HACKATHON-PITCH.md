# HAVEN — hackathon presentation package

Copy-ready copy for slides, Devpost, and stage. Operator flow: [`DEMO_RUNBOOK.md`](DEMO_RUNBOOK.md).

---

## 1. Project title

**Recommended (primary):**  
**HAVEN — Local Room Intelligence**

**Alternates (pick one subtitle on slides):**
- *HAVEN (RoomOS)* — if judges care about the repo name
- *HAVEN — Burst-Based Room State for Smart Spaces*

**Avoid:** “AI that reads your soul,” “autonomous living,” “fully autonomous home OS.”

---

## 2. One-line tagline

**Your room’s state—classified on your laptop, explained in plain language, improved when you correct it.**

Shorter slide version:  
**Local room intelligence you can see, correct, and trust.**

---

## 3. Thirty-second pitch

> Most smart-home systems ask you to build automations by hand—and they either ignore context or ship your video to the cloud. **HAVEN** runs on **your machine**: it samples the room in short bursts, classifies activity—work, gaming, sleep, relaxing, away—with **visible confidence**, maps that to **light, airflow, and temperature** from your preferences, and **learns from one-tap corrections** without retraining the whole model on stage. Same camera for preview and inference. No upload required for the demo. When the room is wrong, you teach it; when the venue is flaky, we still show the product story honestly with labeled demo replay.

---

## 4. Ninety-second demo narration

*Aligns with [`DEMO_RUNBOOK.md`](DEMO_RUNBOOK.md). Pause at bold beats.*

| Time | Say |
|------|-----|
| **0–15s** | “This is **HAVEN**—room intelligence that stays **on this laptop**. Nothing here depends on sending video to a cloud API.” |
| **15–30s** | “The feed you see is the **same camera** our classifier uses—backend capture, not a decorative browser webcam. Every few seconds we grab a **burst** of five frames.” |
| **30–45s** | “We fuse **scene context** and **motion** into a small **tabular model**—fast enough for real hardware, debuggable enough to explain. The hero state updates with **confidence bars** and a short **rationale**—if we’re unsure, the UI shows it.” |
| **45–60s** | “**Preferences** turn mood into concrete targets—brightness, fan, temperature—for work vs sleep vs away. One coherent scene, not four random toggles.” |
| **60–75s** | “If it mislabels me, I hit **Teach the room**. We store burst evidence **locally** and nudge similar moments next time. That’s **memory**, not magic—we’re honest that it’s not full retrain in one click.” |
| **75–90s** | “**Automations are simulated** in this build—rules log what *would* fire. We can wire Home Assistant when enabled. Bottom line: **local**, **explainable**, **correctable** room state—the kind of foundation you’d actually ship before bolting on gadgets.” |

**If using demo replay:** insert after 15s:  
*“We’re on **demo replay** now—a scripted walkthrough on the same UI so the story stays clear; live mode uses the real classifier on this camera.”*

---

## 5. Judge-facing technical credibility (5 bullets)

1. **Burst-level pipeline, not theater** — Five frames per ~2.5s decision window; OpenCLIP scene features + motion fused into named columns; **XGBoost** classifier with train/serve compatibility gate so live inference matches training schema.

2. **Single honest video path** — OpenCV `video.source` drives both **inference** and **`/api/live/preview.jpg`**; WebSocket + HTTP poll; `dataSource` distinguishes live ML (`roomos-ml`) from labeled replay (`demo-replay`).

3. **Explainability by design** — Per-class probabilities, rationale strings, smoothing over bursts, and optional **`eval_report/`** (confusion matrix, per-class precision/recall) for offline Q&A—not a black-box score alone.

4. **Correction loop with clear semantics** — `POST /api/live/feedback` persists burst features and frames under `data/feedback/`; similarity-based blend on subsequent bursts; documented as **memory**, not silent retrain.

5. **Production-shaped edges** — FastAPI transport, Next.js live HUD, dry-run action engine with optional Home Assistant/webhook, deterministic **`npm run demo:replay`** fallback, `npm run train:verify` compat checks.

---

## 6. Business / value (5 bullets)

1. **Privacy as default** — Room video and corrections stay on-device; no account or cloud upload required to run the hackathon build—aligned with how people actually want bedrooms and home offices treated.

2. **Lower setup friction than rule programming** — Users express **moods and scenes**, not brittle IF chains; the system proposes state from context and applies preset environments.

3. **Trust through correction, not surveys** — One-tap fixes build a **personal comfort model** over time without nagging configuration wizards.

4. **Hardware-agnostic path to impact** — Starts with lights, fan, and temperature targets; same signal can drive Home Assistant, webhooks, or future HVAC/lighting partners.

5. **Deployable on commodity laptops** — Tabular head + pretrained perception keeps inference bounded— viable for renters, dorms, and small offices where GPU clusters and always-on cloud inference don’t fit.

---

## 7. Three honest limitations (framed well)

1. **Personal data, personal accuracy** — Metrics are on **your** labeled bursts, not a public benchmark; live performance depends on camera angle, lighting, and whether the room matches training photos. We show confidence so uncertainty is visible, not hidden.

2. **Burst granularity, not full-video understanding** — We classify **short windows**, not every micro-gesture; default config uses **scene + motion**, not a heavy end-to-end video model—by choice, for speed and explainability on a laptop.

3. **Corrections improve memory first** — Teach-the-room nudges **similar future bursts**; changing offline evaluation scores requires **retrain** (`train:images`). Automations in the demo are **simulated** unless you explicitly enable integrations.

---

## 8. Devpost-style project description

### HAVEN — Local Room Intelligence

**Tagline:** Your room’s state—classified on your laptop, explained in plain language, improved when you correct it.

**The problem**  
Smart spaces still expect you to wire automations manually, while “AI” cameras often mean opaque labels or cloud-dependent video. Renters and hackers need something that runs **locally**, says **what it thinks and why**, and gets **better when corrected**—without shipping their bedroom to a server.

**Our solution**  
HAVEN (RoomOS) is a **local-first** stack: a Python burst pipeline (OpenCV → OpenCLIP + motion → XGBoost) plus a Next.js live dashboard. It infers five room states—work, gaming, sleep, relaxing, away—every few seconds, surfaces **confidence and rationale**, maps state to **preference-driven scene targets** (light, fan, temperature), and records **one-tap corrections** into on-disk memory that influences similar moments later. FastAPI streams snapshots and the same-camera preview; automations run **dry-run by default** with optional Home Assistant or webhook hooks.

**How we built it**  
- **Backend:** burst sampling, feature fusion, temporal smoothing, feedback reinforcement, train/serve compatibility gate, eval reports for judges  
- **Frontend:** `/live` HUD with status chips, teach-the-room, mode toggle (live vs honest demo replay)  
- **Ops:** `npm run demo` one-command startup, `demo:replay` for flaky venues, full runbook + troubleshooting  

**What we learned**  
Aligning **training and inference feature schemas** matters more than a bigger model. Judges trust **labeled replay** over fake live data. Explainability (bars, rationale, eval report) beats a single accuracy number.

**What's next**  
Room-specific training from phone/webcam stills, tighter pose cues where available, pilot with real HA automations, and privacy-reviewed optional sync—not required for core value.

**Try it**  
```bash
npm run setup:model && npm run demo
# http://127.0.0.1:3000/live
```

---

## 9. Why this matters now

Homes and workspaces are full of cameras and actuators, but most intelligence still asks users to **trade privacy for convenience** or **maintain endless automations** that break when routine changes. HAVEN matters now because the usable middle path is finally practical: **pretrained perception + small on-device classifiers** that run on a laptop, **explicit confidence** that respects user agency, and **local correction memory** that compounds without a data-harvesting business model. As regulation, renters, and employers push back on always-on cloud video, products that **classify context on-device, explain themselves, and improve from feedback** are the credible foundation for the next decade of smart rooms—not another hub of opaque triggers.

---

## Slide footer (optional)

`github.com/<you>/RoomOS` · `npm run demo` · Live: **127.0.0.1:3000/live** · Docs: README · DEMO_RUNBOOK · TROUBLESHOOTING
