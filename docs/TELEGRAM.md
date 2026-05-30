# Telegram corrections

Send a natural-language correction from your phone; RoomOS captures the **current webcam frame**, saves it to feedback memory, and may auto-retrain (same as the web “Teach the room” flow).

## Setup

1. Fill `backend/.env`:
   - `TELEGRAM_BOT_TOKEN` — from @BotFather
   - `TELEGRAM_ALLOWED_CHAT_IDS` — **your** Telegram user id (see below)
   - `OPENAI_API_KEY` — maps sentences to `work` / `sleep` / `gaming` / `relaxing` / `away`
   - `TELEGRAM_ENABLED=1`

2. Install deps (once):

   ```bash
   npm run setup:venv
   # or: backend/.venv/Scripts/pip install -r backend/requirements.txt
   ```

3. Run the stack:

   ```bash
   npm run demo
   ```

4. In Telegram, open your bot → `/start` → send e.g. *I'm not sleeping, I'm working*.

5. Open **http://127.0.0.1:3000/live** on the same PC — a blue **Correction from Telegram** banner appears with the saved screenshot.

## Your chat id (not the bot token prefix)

| Value | What it is |
|-------|------------|
| Token `8827802941:AAH...` | `8827802941` is the **bot** id |
| `TELEGRAM_ALLOWED_CHAT_IDS` | **Your** user id from @userinfobot or `getUpdates` |

If these match, the bot will log an error and ignore you.

## Commands

| Command | Action |
|---------|--------|
| `/start` | Help + label buttons |
| `/status` | Current room state + memory count |
| Free text (activity) | OpenAI → label → snapshot feedback |
| Free text (preferences) | OpenAI → fan / light / brightness / temp → saves `data/preferences.json` |
| Buttons | Skip OpenAI; save activity label immediately |

### Preference examples

- `Turn the fan lower for work`
- `Change the light to blue when I'm gaming`
- `Dim the lights for relaxing`
- `Make it cooler` (temperature)

Edits apply to your **active preset** (see /preferences). The live page shows a violet banner; /preferences refetches automatically.

## Requirements

- Live engine running (`ROOMOS_AUTOSTART=1`, not `ROOMOS_DEMO_MODE=replay`)
- Webcam producing frames (`/api/live/preview.jpg` works)
- PC running RoomOS must stay on while you use Telegram
