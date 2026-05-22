"use client"

import { useEffect, useMemo } from "react"
import { zodResolver } from "@hookform/resolvers/zod"
import { useQuery } from "@tanstack/react-query"
import { useForm } from "react-hook-form"
import { toast } from "sonner"
import { Check, Fan, Lightbulb, RotateCcw, ShieldCheck, Sparkles, Thermometer } from "lucide-react"

import { PreferencesPresetToggle } from "@/components/roomos/preferences/preferences-preset-toggle"
import { StatePreferenceCard } from "@/components/roomos/preferences/state-preference-card"
import { PreferencesSkeleton } from "@/components/roomos/roomos-loading-states"
import { Button } from "@/components/ui/button"
import { Form } from "@/components/ui/form"
import { fetchPreferenceDocument, savePreferenceDocument } from "@/lib/roomos/api-client"
import { buildPreferenceDocument } from "@/lib/roomos/preferences-document-schema"
import {
  defaultPreferenceDocument,
  EMPTY_PREFERENCE_MATRIX,
  preferenceMatrixSchema,
  type PreferenceMatrixFormValues,
} from "@/lib/roomos/preferences-schema"
import { loadRoomOsPreferences } from "@/lib/roomos/preferences-persistence"
import { roomosUi } from "@/lib/roomos/roomos-ui"
import { ROOM_STATE_LABEL } from "@/lib/roomos/state-meta"
import { useRoomOsPreferencesStore } from "@/stores/roomos-store"
import { ROOM_STATE_ORDER, type PreferencePreset } from "@/types/roomos"

import { cn } from "@/lib/utils"

const BASIC_PRESET_ID = "preset_basic"
const CUSTOM_PRESET_ID = "preset_custom"

function summarizePreset(preset: PreferencePreset) {
  const values = ROOM_STATE_ORDER.map((stateId) => preset.preferences[stateId])
  const averageBrightness = Math.round(values.reduce((sum, pref) => sum + pref.brightness, 0) / values.length)
  const fanCount = values.filter((pref) => pref.fanOn).length
  const temperatures = values.map((pref) => pref.temperatureF)

  return {
    averageBrightness,
    fanCount,
    minTemp: Math.min(...temperatures),
    maxTemp: Math.max(...temperatures),
  }
}

function presetToFormValues(preset: PreferencePreset): PreferenceMatrixFormValues {
  return preset.preferences
}

export function PreferencesPageClient() {
  const presets = useRoomOsPreferencesStore((s) => s.presets)
  const activePresetId = useRoomOsPreferencesStore((s) => s.activePresetId)
  const hydrate = useRoomOsPreferencesStore((s) => s.hydrate)
  const selectPreset = useRoomOsPreferencesStore((s) => s.selectPreset)
  const replacePreset = useRoomOsPreferencesStore((s) => s.replacePreset)

  const docQuery = useQuery({
    queryKey: ["roomos", "preferences"],
    queryFn: async () => {
      try {
        const doc = await fetchPreferenceDocument()
        return { doc, apiOnline: true as const }
      } catch {
        const disk = loadRoomOsPreferences()
        if (disk) {
          return {
            doc: {
              schemaVersion: 1 as const,
              updatedAt: new Date().toISOString(),
              presets: disk.presets,
              activePresetId: disk.activePresetId,
            },
            apiOnline: false as const,
          }
        }
        return { doc: defaultPreferenceDocument(), apiOnline: false as const }
      }
    },
    staleTime: 60_000,
  })

  useEffect(() => {
    if (docQuery.data) hydrate(docQuery.data.doc)
  }, [docQuery.data, hydrate])

  const activePreset = useMemo(() => {
    if (!presets || !activePresetId) return null
    return presets.find((p) => p.id === activePresetId) ?? null
  }, [presets, activePresetId])

  const basicId = useMemo(() => {
    return presets?.find((p) => p.id === BASIC_PRESET_ID)?.id ?? presets?.[0]?.id ?? BASIC_PRESET_ID
  }, [presets])

  const customId = useMemo(() => {
    return presets?.find((p) => p.id === CUSTOM_PRESET_ID)?.id ?? presets?.[1]?.id ?? CUSTOM_PRESET_ID
  }, [presets])

  const form = useForm<PreferenceMatrixFormValues>({
    resolver: zodResolver(preferenceMatrixSchema),
    defaultValues: EMPTY_PREFERENCE_MATRIX,
    mode: "onChange",
  })

  const { isDirty, isSubmitting } = form.formState

  useEffect(() => {
    if (!activePresetId) return
    const preset = useRoomOsPreferencesStore
      .getState()
      .presets?.find((p) => p.id === activePresetId)
    if (!preset) return
    form.reset(presetToFormValues(preset))
  }, [activePresetId, form])

  if (docQuery.isPending || !presets) {
    return <PreferencesSkeleton />
  }

  if (docQuery.isError) {
    return (
      <div
        className={cn(
          roomosUi.prefsAlertPanel,
          "mx-auto my-8 max-w-md p-6 text-sm",
        )}
      >
        <p className="font-medium text-rose-900">Something went wrong</p>
        <p className="mt-2 text-xs leading-relaxed text-rose-800/90">
          Preferences could not be loaded. Try again in a moment.
        </p>
      </div>
    )
  }

  if (!presets.length || !activePresetId || !activePreset) {
    return null
  }

  const isBasic = activePreset.id === basicId
  const presetSummary = summarizePreset(activePreset)

  const apiOnline = docQuery.data?.apiOnline ?? true

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-12 pb-32">
      {!apiOnline ? (
        <p
          className={cn(
            roomosUi.prefsCallout,
            "border-amber-500/25 bg-amber-50/90 px-4 py-3 text-[13px] leading-relaxed text-amber-950",
          )}
          role="status"
        >
          RoomOS API is offline — showing defaults saved in this browser. Start the
          backend (<span className="font-mono text-[12px]">npm run dev</span> from the
          repo root) to sync preferences to disk on this machine.
        </p>
      ) : null}
      <header className="relative overflow-hidden rounded-[2.15rem] border border-[color:var(--haven-line-strong)] bg-[linear-gradient(165deg,rgba(255,254,251,0.995)_0%,rgba(251,246,238,0.97)_44%,rgba(236,228,218,0.94)_100%)] p-6 shadow-[var(--haven-shadow-float)] ring-1 ring-[color:var(--haven-edge-light)] sm:p-8 lg:p-10">
        <div
          aria-hidden
          className="pointer-events-none absolute -left-20 -top-16 size-64 rounded-full bg-[radial-gradient(circle_at_30%_28%,rgba(15,118,110,0.2),transparent_70%)] blur-3xl"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -right-12 top-6 size-56 rounded-full bg-[radial-gradient(circle_at_70%_30%,rgba(253,230,138,0.28),transparent_72%)] blur-3xl"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-[0.055]"
          style={{
            backgroundImage:
              "linear-gradient(to right, currentColor 1px, transparent 1px), linear-gradient(to bottom, currentColor 1px, transparent 1px)",
            backgroundSize: "64px 64px",
            maskImage: "radial-gradient(ellipse 72% 70% at 50% 18%, black 0%, transparent 72%)",
          }}
        />

        <div className="relative grid gap-8 lg:grid-cols-[minmax(0,1.05fr)_minmax(22rem,0.95fr)] lg:items-end">
          <div className="flex flex-col gap-5">
            <div className="flex items-center gap-3">
              <span className="font-mono text-[12px] font-semibold tabular-nums text-[color:var(--haven-faint)]">
                02
              </span>
              <span className="h-3 w-px bg-[color:var(--haven-line-strong)]" aria-hidden />
              <span className="text-[11px] font-semibold uppercase tracking-[0.28em] text-[color:var(--haven-muted)]">
                Preferences
              </span>
            </div>
            <h1 className="haven-display text-balance text-[clamp(2.45rem,5.8vw,4.35rem)] font-semibold leading-[0.98] tracking-[-0.045em] text-[color:var(--haven-ink)]">
              Author the room.
              <span className="block bg-gradient-to-br from-[#1a1816] via-[#1a3c39] to-[#0f766e] bg-clip-text text-transparent">
                Let Haven carry it.
              </span>
            </h1>
            <p className="max-w-[40rem] text-pretty text-[15px] leading-[1.72] text-[color:var(--haven-muted)] sm:text-[16.5px]">
              Set how each mood should feel: light, airflow, and temperature moving as one
              composed scene. Saves go to the local RoomOS API on this machine (and your browser).
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-[color:var(--haven-line-strong)] bg-[color-mix(in_oklab,#fffefb_92%,transparent)] px-3 py-1.5 text-[10.5px] font-semibold uppercase tracking-[0.18em] text-[color:var(--haven-muted)] shadow-[var(--haven-shadow-card)]">
                <ShieldCheck className="size-3 text-teal-700" aria-hidden />
                On device
              </span>
              <span className="inline-flex items-center gap-1.5 rounded-full border border-[color:var(--haven-line-strong)] bg-[color-mix(in_oklab,#fffefb_92%,transparent)] px-3 py-1.5 text-[10.5px] font-semibold uppercase tracking-[0.18em] text-[color:var(--haven-muted)] shadow-[var(--haven-shadow-card)]">
                <Sparkles className="size-3 text-amber-700" aria-hidden />
                Five authored envelopes
              </span>
            </div>
          </div>

          <div className="relative overflow-hidden rounded-[1.65rem] border border-white/[0.11] bg-[linear-gradient(152deg,#242220_0%,#141312_46%,#0b0a09_100%)] p-4 text-stone-100 shadow-[var(--haven-shadow-primary)] ring-1 ring-black/10 sm:p-5">
            <div
              aria-hidden
              className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_80%_58%_at_16%_0%,rgba(20,184,166,0.2),transparent_62%),radial-gradient(ellipse_70%_60%_at_100%_15%,rgba(245,158,11,0.13),transparent_60%)]"
            />
            <div className="relative">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-teal-50/58">
                    Active envelope
                  </p>
                  <h2 className="haven-display mt-2 text-[1.55rem] font-semibold tracking-[-0.035em] text-stone-50">
                    {activePreset.name}
                  </h2>
                </div>
                <span className="rounded-full border border-white/[0.1] bg-white/[0.06] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-stone-300">
                  Local
                </span>
              </div>

              <div className="mt-5 grid grid-cols-3 gap-2">
                <div className="rounded-2xl border border-white/[0.08] bg-white/[0.055] p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]">
                  <Lightbulb className="size-3.5 text-amber-200/90" aria-hidden />
                  <p className="mt-3 font-mono text-[1.15rem] font-semibold tabular-nums text-stone-50">
                    {presetSummary.averageBrightness}%
                  </p>
                  <p className="mt-0.5 text-[10px] uppercase tracking-[0.14em] text-stone-500">
                    Avg light
                  </p>
                </div>
                <div className="rounded-2xl border border-white/[0.08] bg-white/[0.055] p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]">
                  <Fan className="size-3.5 text-sky-200/90" aria-hidden />
                  <p className="mt-3 font-mono text-[1.15rem] font-semibold tabular-nums text-stone-50">
                    {presetSummary.fanCount}/5
                  </p>
                  <p className="mt-0.5 text-[10px] uppercase tracking-[0.14em] text-stone-500">
                    Air lanes
                  </p>
                </div>
                <div className="rounded-2xl border border-white/[0.08] bg-white/[0.055] p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]">
                  <Thermometer className="size-3.5 text-teal-200/90" aria-hidden />
                  <p className="mt-3 font-mono text-[1.15rem] font-semibold tabular-nums text-stone-50">
                    {presetSummary.minTemp}-{presetSummary.maxTemp}
                  </p>
                  <p className="mt-0.5 text-[10px] uppercase tracking-[0.14em] text-stone-500">
                    Temp span
                  </p>
                </div>
              </div>

              <ul className="mt-5 space-y-2" aria-label={`${activePreset.name} mood summary`}>
                {ROOM_STATE_ORDER.map((stateId) => {
                  const pref = activePreset.preferences[stateId]
                  return (
                    <li
                      key={stateId}
                      className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 rounded-xl border border-white/[0.06] bg-white/[0.035] px-3 py-2"
                    >
                      <span
                        className="size-3 rounded-full shadow-[0_0_18px_rgba(255,255,255,0.18)] ring-1 ring-white/25"
                        style={{ backgroundColor: pref.lightColorHex }}
                        aria-hidden
                      />
                      <span className="truncate text-[12.5px] font-medium text-stone-200">
                        {ROOM_STATE_LABEL[stateId]}
                      </span>
                      <span className="font-mono text-[11px] font-semibold tabular-nums text-stone-400">
                        {pref.brightness}%
                      </span>
                    </li>
                  )
                })}
              </ul>
            </div>
          </div>
        </div>
      </header>

      <section
        aria-labelledby="preset-heading"
        className="relative overflow-hidden rounded-[1.75rem] border border-[color:var(--haven-line-strong)] bg-[color-mix(in_oklab,#fffefb_74%,transparent)] p-5 shadow-[var(--haven-shadow-card)] ring-1 ring-[color:var(--haven-edge-light)] sm:p-6"
      >
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-[10.5px] font-semibold uppercase tracking-[0.24em] text-[color:var(--haven-faint)]">
              Step 01
            </p>
            <h2
              id="preset-heading"
              className="haven-display mt-1.5 text-[1.5rem] font-semibold tracking-[-0.024em] text-[color:var(--haven-ink)]"
            >
              Pick a starting posture
            </h2>
          </div>
          <p className="max-w-[18rem] text-right text-[12.5px] leading-relaxed text-[color:var(--haven-muted)]">
            Either is a save away. Switching never overwrites the other.
          </p>
        </div>
        <div className="mt-6">
          <PreferencesPresetToggle
            value={activePresetId}
            basicPresetId={basicId}
            customPresetId={customId}
            onValueChange={(id) => {
              selectPreset(id)
              const next = presets.find((p) => p.id === id)
              if (next) form.reset(presetToFormValues(next))
            }}
          />
        </div>
        <p
          className={cn(roomosUi.prefsCallout, "mt-4 px-4 py-3.5 text-[13px] leading-relaxed")}
          role="note"
        >
          {isBasic
            ? "Basic Preference is the profile we recommend starting with: calm, familiar, and ready for real homes."
            : "Custom is for when you know exactly how you like the room. Adjust any mood, then save. Switching presets updates the live engine immediately."}
        </p>
      </section>

      <Form {...form}>
        <form
          className="flex flex-col gap-10"
          onSubmit={form.handleSubmit(async (values) => {
            const updated: PreferencePreset = {
              ...activePreset,
              preferences: values,
            }
            replacePreset(updated)
            form.reset(values)

            const allPresets = useRoomOsPreferencesStore.getState().presets ?? [updated]
            const nextPresets = allPresets.map((p) => (p.id === updated.id ? updated : p))
            const activeId =
              useRoomOsPreferencesStore.getState().activePresetId ?? updated.id
            try {
              await savePreferenceDocument(
                buildPreferenceDocument(nextPresets, activeId),
              )
              toast.success("Preferences saved", {
                description: "Synced to the local RoomOS backend.",
              })
            } catch {
              toast.success("Preferences saved", {
                description: "Stored locally — backend was unreachable.",
              })
            }
          })}
        >
          <section aria-labelledby="moods-heading" className="flex flex-col gap-6">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <p className="text-[10.5px] font-semibold uppercase tracking-[0.24em] text-[color:var(--haven-faint)]">
                  Step 02
                </p>
                <h2
                  id="moods-heading"
                  className="haven-display mt-1.5 text-[1.5rem] font-semibold tracking-[-0.024em] text-[color:var(--haven-ink)]"
                >
                  Author each mood
                </h2>
              </div>
              <p className="max-w-[20rem] text-right text-[12.5px] leading-relaxed text-[color:var(--haven-muted)]">
                Same controls on every card so you can compare at a glance.
              </p>
            </div>
            <div className="grid gap-5 lg:grid-cols-2 lg:gap-6">
              {ROOM_STATE_ORDER.map((stateId) => (
                <StatePreferenceCard key={stateId} stateId={stateId} />
              ))}
            </div>
          </section>

          <div
            className={cn(
              roomosUi.prefsStickyBar,
              "sticky bottom-4 z-20 flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between sm:px-5 sm:py-3.5",
            )}
          >
            <div className="flex min-w-0 items-center gap-3">
              <span
                className={cn(
                  "flex size-8 shrink-0 items-center justify-center rounded-full",
                  isDirty
                    ? "bg-amber-500/[0.14] text-amber-700"
                    : "bg-teal-500/[0.14] text-teal-700",
                )}
                aria-hidden
              >
                {isDirty ? (
                  <span className="relative flex size-2">
                    <span className="absolute inline-flex size-full animate-ping rounded-full bg-amber-500/55 motion-reduce:hidden" />
                    <span className="relative inline-flex size-2 rounded-full bg-amber-500/95" />
                  </span>
                ) : (
                  <Check className="size-4" aria-hidden />
                )}
              </span>
              <div className="min-w-0">
                <p className="text-[13.5px] font-semibold tracking-tight text-[color:var(--haven-ink)]">
                  {isDirty ? "Unsaved changes" : "All saved on this device"}
                </p>
                <p className="text-[11.5px] leading-relaxed text-[color:var(--haven-muted)]">
                  {isDirty
                    ? "Save to update the active preset. Reset to discard."
                    : apiOnline
                      ? "Saved in this browser and on the local RoomOS API."
                      : "Saved in this browser until the API is running."}
                </p>
              </div>
            </div>
            <div className="flex flex-wrap items-center justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                size="lg"
                className={cn(
                  "h-10 gap-2 rounded-full border-stone-300 bg-white px-4 text-[13px] font-semibold text-[color:var(--haven-ink)] hover:bg-stone-50",
                  roomosUi.focusRingLight,
                )}
                disabled={!isDirty || isSubmitting}
                onClick={() => form.reset(presetToFormValues(activePreset))}
              >
                <RotateCcw className="size-3.5" aria-hidden />
                Reset
              </Button>
              <Button
                type="submit"
                size="lg"
                disabled={!isDirty || isSubmitting}
                className={cn(
                  "h-10 min-w-[9rem] gap-2 rounded-full px-5 text-[13px] font-semibold text-white",
                  "bg-[linear-gradient(168deg,#2e2c29_0%,#1e1c19_42%,#171513_100%)]",
                  "shadow-[var(--haven-shadow-primary)] ring-1 ring-inset ring-white/16",
                  "transition-[transform,box-shadow] duration-200 ease-out",
                  "motion-safe:hover:-translate-y-px",
                  roomosUi.focusRingLight,
                )}
              >
                <Check className="size-3.5" aria-hidden />
                Save changes
              </Button>
            </div>
          </div>
        </form>
      </Form>
    </div>
  )
}

