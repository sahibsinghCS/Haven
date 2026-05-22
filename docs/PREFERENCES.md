# Preferences & active preset

## Source of truth

**`backend/data/preferences.json`** (path from `configs/inference.yaml` → `inference.preferences_path`).

The document includes:

| Field | Meaning |
|-------|---------|
| `presets[]` | Named mood→scene matrices (Basic, Custom, …) |
| `activePresetId` | **Which preset the live engine uses** for `appliedScene` |
| `isDefault` | UI hint only (“recommended starting profile”); **not** used for live inference when `activePresetId` is set |

## Resolution order (backend)

1. `activePresetId` if it matches a preset `id`
2. Else first preset with `isDefault: true`
3. Else `presets[0].id`

Implemented in `backend/roomos/preferences/document.py` and used by:

- `PUT /api/preferences` (normalize before write)
- `GET /api/preferences` (normalize on read, migrates old files)
- `LiveInferenceEngine._load_preference_scenes()` (mtime-cached)

## Frontend

- Zustand `activePresetId` mirrors the document field.
- **Hydrate:** API document wins for preset list + `activePresetId`; localStorage is a cache updated after hydrate.
- **Toggle preset:** updates store + localStorage, then `PUT` full document with new `activePresetId` (live engine picks it up on next file read).
- **Save mood edits:** `PUT` with `presets` + current `activePresetId`.

## Manual test

1. `npm run dev` → open `/preferences`.
2. Select **Custom**, change Work brightness to **90**, Save.
3. Open `/live` — when state is **Work**, Applied scene should show **90%** light (not Basic’s 72%).
4. Switch to **Basic** (no save required) — wait one burst — Work targets should return to Basic values when inferred as Work.
5. Inspect `backend/data/preferences.json` — `"activePresetId": "preset_basic"` or `"preset_custom"` matches UI toggle.
