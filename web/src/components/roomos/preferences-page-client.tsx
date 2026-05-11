"use client"

import { useEffect, useMemo } from "react"
import { zodResolver } from "@hookform/resolvers/zod"
import { useQuery } from "@tanstack/react-query"
import { useForm } from "react-hook-form"
import { toast } from "sonner"
import { Check, RotateCcw, ShieldCheck } from "lucide-react"

import { PreferencesPresetToggle } from "@/components/roomos/preferences/preferences-preset-toggle"
import { StatePreferenceCard } from "@/components/roomos/preferences/state-preference-card"
import { PreferencesSkeleton } from "@/components/roomos/roomos-loading-states"
import { Button } from "@/components/ui/button"
import { Form } from "@/components/ui/form"
import { fetchMockPreferenceDocument } from "@/lib/mock/roomos-mock"
import {
  EMPTY_PREFERENCE_MATRIX,
  preferenceMatrixSchema,
  type PreferenceMatrixFormValues,
} from "@/lib/roomos/preferences-schema"
import { roomosUi } from "@/lib/roomos/roomos-ui"
import { useRoomOsPreferencesStore } from "@/stores/roomos-store"
import { ROOM_STATE_ORDER, type PreferencePreset } from "@/types/roomos"

import { cn } from "@/lib/utils"

const BASIC_PRESET_ID = "preset_basic"
const CUSTOM_PRESET_ID = "preset_custom"

function presetToFormValues(preset: PreferencePreset): PreferenceMatrixFormValues {
  return preset.preferences
}

export function PreferencesPageClient() {
  const presets = useRoomOsPreferencesStore((s) => s.presets)
  const selectedPresetId = useRoomOsPreferencesStore((s) => s.selectedPresetId)
  const hydrate = useRoomOsPreferencesStore((s) => s.hydrate)
  const selectPreset = useRoomOsPreferencesStore((s) => s.selectPreset)
  const replacePreset = useRoomOsPreferencesStore((s) => s.replacePreset)

  const docQuery = useQuery({
    queryKey: ["roomos", "preferences"],
    queryFn: fetchMockPreferenceDocument,
    staleTime: 60_000,
  })

  useEffect(() => {
    if (docQuery.data) hydrate(docQuery.data)
  }, [docQuery.data, hydrate])

  const activePreset = useMemo(() => {
    if (!presets || !selectedPresetId) return null
    return presets.find((p) => p.id === selectedPresetId) ?? null
  }, [presets, selectedPresetId])

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
    if (!selectedPresetId) return
    const preset = useRoomOsPreferencesStore
      .getState()
      .presets?.find((p) => p.id === selectedPresetId)
    if (!preset) return
    form.reset(presetToFormValues(preset))
  }, [selectedPresetId, form])

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

  if (!presets.length || !selectedPresetId || !activePreset) {
    return null
  }

  const isBasic = activePreset.id === basicId

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-14 pb-32">
      <header className="relative">
        <div
          aria-hidden
          className="pointer-events-none absolute -left-12 -top-10 hidden size-44 rounded-full bg-[radial-gradient(circle_at_30%_28%,rgba(15,118,110,0.16),transparent_70%)] blur-2xl sm:block"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -right-8 top-4 hidden size-40 rounded-full bg-[radial-gradient(circle_at_70%_30%,rgba(253,230,138,0.22),transparent_72%)] blur-2xl sm:block"
        />
        <div className="relative flex flex-col gap-5">
          <div className="flex items-center gap-3">
            <span className="font-mono text-[12px] font-semibold tabular-nums text-[color:var(--haven-faint)]">
              02
            </span>
            <span className="h-3 w-px bg-[color:var(--haven-line-strong)]" aria-hidden />
            <span className="text-[11px] font-semibold uppercase tracking-[0.28em] text-[color:var(--haven-muted)]">
              Preferences
            </span>
          </div>
          <h1 className="haven-display text-balance text-[clamp(2.25rem,5.4vw,3.5rem)] font-semibold leading-[1.04] tracking-[-0.038em] text-[color:var(--haven-ink)]">
            Tune the moods.
            <span className="block bg-gradient-to-br from-[#1a1816] via-[#1a3c39] to-[#0f766e] bg-clip-text text-transparent">
              Haven remembers the rest.
            </span>
          </h1>
          <p className="max-w-[40rem] text-pretty text-[15px] leading-[1.7] text-[color:var(--haven-muted)] sm:text-[16px]">
            Set how each mood should feel: light, airflow, and temperature, behaving as one
            scene. Everything you save stays on this device until you connect a hub or account.
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-[color:var(--haven-line-strong)] bg-[color-mix(in_oklab,#fffefb_92%,transparent)] px-2.5 py-1 text-[10.5px] font-semibold uppercase tracking-[0.18em] text-[color:var(--haven-muted)] shadow-[var(--haven-shadow-card)]">
              <ShieldCheck className="size-3 text-teal-700" aria-hidden />
              On device
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-[color:var(--haven-line-strong)] bg-[color-mix(in_oklab,#fffefb_92%,transparent)] px-2.5 py-1 text-[10.5px] font-semibold uppercase tracking-[0.18em] text-[color:var(--haven-muted)] shadow-[var(--haven-shadow-card)]">
              <span className="size-1.5 rounded-full bg-amber-500/85" aria-hidden />
              Five moods, five envelopes
            </span>
          </div>
        </div>
      </header>

      <section aria-labelledby="preset-heading" className="flex flex-col gap-6">
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
        <PreferencesPresetToggle
          value={selectedPresetId}
          basicPresetId={basicId}
          customPresetId={customId}
          onValueChange={(id) => {
            selectPreset(id)
            const next = presets.find((p) => p.id === id)
            if (next) form.reset(presetToFormValues(next))
          }}
        />
        <p
          className={cn(roomosUi.prefsCallout, "px-4 py-3.5 text-[13px] leading-relaxed")}
          role="note"
        >
          {isBasic
            ? "Basic Preference is the profile we recommend starting with: calm, familiar, and ready for real homes."
            : "Custom is for when you know exactly how you like the room. Adjust any mood, then save. Haven keeps it here on this device."}
        </p>
      </section>

      <Form {...form}>
        <form
          className="flex flex-col gap-10"
          onSubmit={form.handleSubmit((values) => {
            const updated: PreferencePreset = {
              ...activePreset,
              preferences: values,
            }
            replacePreset(updated)
            form.reset(values)
            toast.success("Preferences saved", {
              description: "Room scenes are stored locally on this device.",
            })
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
                    : "Encrypted at rest in your browser. Never sent unless you opt in."}
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

