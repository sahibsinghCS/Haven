"use client"

import { useEffect, useMemo } from "react"
import { zodResolver } from "@hookform/resolvers/zod"
import { useQuery } from "@tanstack/react-query"
import { useForm } from "react-hook-form"
import { toast } from "sonner"

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

const kicker =
  "text-zinc-500 text-[0.6875rem] font-semibold tracking-[0.2em] uppercase"

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
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-12 pb-28">
      <header className="space-y-4">
        <p className={kicker}>Haven</p>
        <h1 className="text-balance text-3xl font-semibold tracking-tight text-zinc-900 sm:text-4xl">
          Preferences
        </h1>
        <p className="max-w-2xl text-pretty text-sm leading-relaxed text-zinc-600 sm:text-[0.9375rem]">
          Choose how each mood should feel — lights, airflow, and temperature. Everything you
          save stays on this computer until you connect a hub or account later.
        </p>
      </header>

      <section aria-labelledby="preset-heading" className="space-y-5">
        <h2
          id="preset-heading"
          className="text-sm font-semibold tracking-tight text-zinc-700"
        >
          Preset
        </h2>
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
          className={cn(roomosUi.prefsCallout, "px-4 py-3.5")}
          role="note"
        >
          {isBasic
            ? "Basic Preference is the profile we recommend starting with — calm, familiar, and ready for real homes."
            : "Custom is for when you know exactly how you like the room. Adjust any mood, then save — Haven keeps it here on this device."}
        </p>
      </section>

      <Form {...form}>
        <form
          className="space-y-10"
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
          <section aria-labelledby="moods-heading" className="space-y-6">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <h2
                id="moods-heading"
                className="text-sm font-semibold tracking-tight text-zinc-700"
              >
                Moods
              </h2>
              <p className="text-xs text-zinc-600 sm:text-sm">
                Five moods — same layout on every card so you can compare at a glance.
              </p>
            </div>
            <div className="grid gap-6 lg:grid-cols-2">
              {ROOM_STATE_ORDER.map((stateId) => (
                <StatePreferenceCard key={stateId} stateId={stateId} />
              ))}
            </div>
          </section>

          <div
            className={cn(
              roomosUi.prefsStickyBar,
              "sticky bottom-4 z-20 flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between sm:px-5 sm:py-4",
            )}
          >
            <p className="text-sm text-zinc-600">
              {isDirty ? (
                <span className="font-medium text-amber-800">You have unsaved changes</span>
              ) : (
                <span>Saved on this device</span>
              )}
            </p>
            <div className="flex flex-wrap items-center justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                className={cn(
                  "border-zinc-300 bg-white text-zinc-800 hover:bg-zinc-50",
                  roomosUi.focusRingLight,
                )}
                disabled={!isDirty || isSubmitting}
                onClick={() => form.reset(presetToFormValues(activePreset))}
              >
                Reset
              </Button>
              <Button
                type="submit"
                disabled={!isDirty || isSubmitting}
                className={cn(
                  "min-w-[8rem] font-medium shadow-sm",
                  roomosUi.focusRingLight,
                )}
              >
                Save changes
              </Button>
            </div>
          </div>
        </form>
      </Form>
    </div>
  )
}
