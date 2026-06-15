# Mood lifecycle

RoomOS moods are user-manageable room states. Each mood has a **registry record** (in `data/moods.json`), optional **on-device training data**, and an **inference eligibility** flag derived from the deployed model bundle.

## States

| Lifecycle | Meaning | In registry | Live inference |
|-----------|---------|-------------|----------------|
| `ready` | ML enabled; class in deployed bundle | yes | yes |
| `collecting` | Burst capture session active | yes | no (not in bundle yet for custom) |
| `training` | Personal training job running | yes | no |
| `error` | Last training job failed | yes | no |
| `custom_untrained` | Custom mood; bundle has no class | yes | no |
| `builtin_untrained` | Builtin active; bundle lacks class | yes | no |
| `inference_hidden` | `ml.enabled=false` | yes | no |
| `builtin_deleted` | Builtin removed; restorable via API | no | no (masked if still in bundle) |

`gaming` is **not** a mood. It is a legacy inference-only label: allowed when the bundle includes it, never stored in the registry or preferences matrix.

## Derived API fields

`GET /api/moods` returns per mood:

- `lifecycle` — row in the table above (for active moods)
- `inferenceEligible` — mood id is in `inferenceLabels`
- `inBundle` — deployed `label_encoder.json` contains this id

Top-level:

- `inferenceLabels` — labels the live engine may surface (excludes `unknown`)
- `uiStateOrder` — live HUD distribution order
- `restorableBuiltins[].lifecycle` — always `builtin_deleted`

## Train/serve compatibility

When `data/moods.json` exists, startup checks that **inference-eligible** labels are non-empty (at least one active, ML-enabled mood or legacy label the bundle can predict). Deleted moods still in the bundle are masked at runtime, not a startup failure.

## Preferences

All **active** registry moods have preference presets. Deleted moods are stripped from presets on `DELETE /api/moods/{id}`. Inference-hidden moods keep preference rows but do not receive live predictions.
