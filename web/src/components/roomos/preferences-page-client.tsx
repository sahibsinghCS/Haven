"use client"

import { useCallback, useEffect, useLayoutEffect, useMemo, useState } from "react"
import Link from "next/link"
import { zodResolver } from "@hookform/resolvers/zod"
import { useQuery } from "@tanstack/react-query"
import { useForm } from "react-hook-form"
import { toast } from "sonner"
import { Check, RotateCcw } from "lucide-react"

import { useHavenAuth } from "@/components/auth/haven-auth-provider"
import { AddMoodWizard } from "@/components/roomos/moods/add-mood-wizard"
import { MoodBurstReviewPanel } from "@/components/roomos/moods/mood-burst-review-panel"
import { MoodFilterBar } from "@/components/roomos/moods/mood-filter-bar"
import { moodLifecycleFilter, type MoodFilter } from "@/components/roomos/moods/mood-lifecycle-chip"
import { MoodPreferenceCard } from "@/components/roomos/moods/mood-preference-card"
import { PreferencesTrainingInline } from "@/components/roomos/moods/preferences-training-inline"
import { HavenOfflineBanner } from "@/components/roomos/haven-offline-banner"
import { HavenSurfaceState } from "@/components/roomos/haven-surface-state"
import { HavenDashboardSkeleton } from "@/components/roomos/haven-loading-states"
import { HavenPageHeader } from "@/components/roomos/haven-primitives"
import { useMoods } from "@/hooks/use-moods"
import { Button } from "@/components/ui/button"
import { Form } from "@/components/ui/form"
import { savePreferenceDocument } from "@/lib/roomos/api-client"
import {
  integrationsQueryOptions,
  preferencesQueryOptions,
} from "@/lib/roomos/dashboard-queries"
import {
  defaultDeviceSettingsDocument,
  parseDeviceSettingsDocument,
} from "@/lib/roomos/device-settings-schema"
import { loadDeviceSettingsLocal } from "@/lib/roomos/device-settings-persistence"
import { buildPreferenceDocument, parsePreferenceDocument } from "@/lib/roomos/preferences-document-schema"
import {
  listConnectedDevices,
  mergeDevicesIntoMatrix,
  migratePreferenceMatrix,
} from "@/lib/roomos/preferences-device-helpers"
import {
  defaultPreferenceDocument,
  EMPTY_PREFERENCE_MATRIX,
  preferenceMatrixSchema,
  type PreferenceMatrixFormValues,
} from "@/lib/roomos/preferences-schema"
import { usePreferencesWsRefresh } from "@/hooks/use-preferences-ws-refresh"
import { useClientHydrated } from "@/hooks/use-client-hydrated"
import { loadRoomOsPreferences } from "@/lib/roomos/preferences-persistence"
import { roomosUi } from "@/lib/roomos/roomos-ui"
import { useRoomOsPreferencesStore } from "@/stores/roomos-store"
import type { MoodDefinition, PreferencePreset } from "@/types/roomos"

import { cn } from "@/lib/utils"

function presetToFormValues(
  preset: PreferencePreset,
  integrationsDoc = defaultDeviceSettingsDocument(),
  moodIds: readonly string[],
): PreferenceMatrixFormValues {
  return mergeDevicesIntoMatrix(
    migratePreferenceMatrix(
      preset.preferences as Record<string, unknown>,
      integrationsDoc,
      moodIds,
    ),
    listConnectedDevices(integrationsDoc),
  )
}

function ensureMoodInForm(
  values: PreferenceMatrixFormValues,
  moodId: string,
  connected: ReturnType<typeof listConnectedDevices>,
): PreferenceMatrixFormValues {
  if (values[moodId]) return values
  const next = { ...values, [moodId]: { devices: {} } }
  return mergeDevicesIntoMatrix(next, connected)
}

export function PreferencesPageClient() {
  const [moodFilter, setMoodFilter] = useState<MoodFilter>("all")
  const hydrated = useClientHydrated()
  const { user, enabled: authEnabled, session } = useHavenAuth()
  const presets = useRoomOsPreferencesStore((s) => s.presets)
  const activePresetId = useRoomOsPreferencesStore((s) => s.activePresetId)
  const hydrate = useRoomOsPreferencesStore((s) => s.hydrate)
  const replacePreset = useRoomOsPreferencesStore((s) => s.replacePreset)

  const moodsQuery = useMoods()
  const moodIds = useMemo(
    () => moodsQuery.data?.moods.map((m) => m.id) ?? [],
    [moodsQuery.data?.moods],
  )

  const loadPreferencesFallback = useCallback((): {
    doc: ReturnType<typeof defaultPreferenceDocument>
    apiOnline: false
  } => {
    const disk = loadRoomOsPreferences()
    if (disk) {
      const parsed =
        parsePreferenceDocument({
          schemaVersion: 2,
          updatedAt: new Date().toISOString(),
          presets: disk.presets,
          activePresetId: disk.activePresetId,
        }) ?? defaultPreferenceDocument()
      return { doc: parsed, apiOnline: false as const }
    }
    return { doc: defaultPreferenceDocument(), apiOnline: false as const }
  }, [])

  const docQuery = useQuery({
    ...preferencesQueryOptions(user?.id),
  })

  const integrationsQuery = useQuery({
    ...integrationsQueryOptions(user?.id),
  })

  const integrationsDoc = useMemo(() => {
    const raw = integrationsQuery.data
    if (!raw) return defaultDeviceSettingsDocument()
    const doc = "doc" in raw && raw.doc ? raw.doc : raw
    return parseDeviceSettingsDocument(doc)
  }, [integrationsQuery.data])

  const connectedDevices = useMemo(
    () => listConnectedDevices(integrationsDoc),
    [integrationsDoc],
  )

  useLayoutEffect(() => {
    if (useRoomOsPreferencesStore.getState().presets) return
    hydrate(loadPreferencesFallback().doc)
  }, [hydrate, loadPreferencesFallback])

  useEffect(() => {
    if (docQuery.data) hydrate(docQuery.data.doc)
  }, [docQuery.data, hydrate])

  const refetchFromTelegram = useCallback(() => {
    void docQuery.refetch()
  }, [docQuery])

  usePreferencesWsRefresh(refetchFromTelegram, docQuery.data?.apiOnline !== false)

  const activePreset = useMemo(() => {
    if (!presets || !activePresetId) return null
    return presets.find((p) => p.id === activePresetId) ?? null
  }, [presets, activePresetId])

  const form = useForm<PreferenceMatrixFormValues>({
    resolver: zodResolver(preferenceMatrixSchema),
    defaultValues: EMPTY_PREFERENCE_MATRIX,
    mode: "onChange",
  })

  const { isDirty, isSubmitting } = form.formState

  useEffect(() => {
    if (!activePresetId || integrationsQuery.isPending || moodIds.length === 0) return
    const preset = useRoomOsPreferencesStore
      .getState()
      .presets?.find((p) => p.id === activePresetId)
    if (!preset) return
    form.reset(presetToFormValues(preset, integrationsDoc, moodIds))
  }, [activePresetId, form, integrationsDoc, integrationsQuery.isPending, moodIds])

  const handleMoodCreated = useCallback(
    (mood: MoodDefinition) => {
      const connected = listConnectedDevices(integrationsDoc)
      const current = form.getValues()
      const next = ensureMoodInForm(current, mood.id, connected)
      form.reset(next)
    },
    [form, integrationsDoc],
  )

  const moodsStillLoading = moodsQuery.isLoading
  const prefsStillLoading = !presets && docQuery.isLoading

  if (!hydrated || prefsStillLoading || moodsStillLoading) {
    return <HavenDashboardSkeleton />
  }

  if (!presets?.length || !activePresetId || !activePreset) {
    return (
      <HavenSurfaceState
        variant="light"
        tone="error"
        role="alert"
        title="Preferences are not set up yet"
        description="Could not load a preset from this device or the local API. Refresh the page or check that Haven is running."
        className="mx-auto my-8"
      />
    )
  }

  if (moodsQuery.isError) {
    return (
      <HavenSurfaceState
        variant="light"
        tone="error"
        role="alert"
        title="Moods could not load"
        description={
          moodsQuery.error instanceof Error
            ? moodsQuery.error.message
            : "Haven may be offline on this machine. Start the backend and refresh."
        }
        className="mx-auto my-8"
      />
    )
  }

  const hasConnectedDevices = connectedDevices.length > 0
  const allMoods = moodsQuery.data?.moods ?? []
  const visibleMoods = allMoods.filter((m) => moodLifecycleFilter(m, moodFilter))

  const apiOnline = docQuery.data?.apiOnline ?? true
  const authRequired = docQuery.data?.authRequired ?? false

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-8 pb-28">
      <div className={roomosUi.pageEnterStagger1}>
        <PreferencesTrainingInline />
      </div>
      {authRequired && authEnabled && !session ? (
        <p
          className={cn(
            roomosUi.prefsCallout,
            "border-rose-500/25 bg-rose-50/90 px-4 py-3 text-[13px] leading-relaxed text-rose-950",
          )}
          role="alert"
        >
          Sign in to sync preferences with your account. Edits on this page stay in the browser until you
          log in.
        </p>
      ) : null}
      {!apiOnline && !authRequired ? <HavenOfflineBanner context="preferences" /> : null}

      {!hasConnectedDevices ? (
        <section className="rounded-[1.75rem] border border-dashed border-[color:var(--haven-line-strong)] bg-white/50 p-8 text-center">
          <h2 className="haven-display text-[1.35rem] font-semibold text-[color:var(--haven-ink)]">
            Connect devices first
          </h2>
          <p className="mx-auto mt-2 max-w-md text-[14px] leading-relaxed text-[color:var(--haven-muted)]">
            Preferences only appear for devices you have connected. Add a smart plug, lights, or thermostat on the Connections page.
          </p>
          <Link
            href="/connections"
            className={cn("mt-5 inline-flex rounded-full px-5 py-2.5 text-[13px] font-semibold", roomosUi.havenPrimaryBtn)}
          >
            Go to Connections
          </Link>
        </section>
      ) : null}

      <Form {...form}>
        <form
          className={cn("flex flex-col gap-10", !hasConnectedDevices && "hidden")}
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
                description: "Synced to Haven on this device.",
              })
            } catch {
              toast.success("Preferences saved", {
 description: "Stored locally. backend was unreachable.",
              })
            }
          })}
        >
          <section aria-labelledby="moods-heading" className="flex flex-col gap-6">
            <HavenPageHeader
              id="moods-heading"
              eyebrow="Device scenes"
              title="Moods / Preferences"
              lede={
                <>
                  Device scenes per mood. Teaching the camera and reviewing switches happen on{" "}
                  <Link href="/live" className="font-semibold text-teal-800 underline-offset-2 hover:underline">
                    Live
                  </Link>{" "}
                  and{" "}
                  <Link href="/review" className="font-semibold text-teal-800 underline-offset-2 hover:underline">
                    Review
                  </Link>
                  .
                </>
              }
            />
            <MoodFilterBar moods={allMoods} value={moodFilter} onChange={setMoodFilter} />
            <div className="haven-list-stagger grid gap-5 lg:grid-cols-2 lg:gap-6">
              {visibleMoods.map((mood) => (
                <MoodPreferenceCard
                  key={mood.id}
                  mood={mood}
                  connectedDevices={connectedDevices}
                  canDelete={allMoods.length > 1}
                />
              ))}
              {moodFilter === "all" ? <AddMoodWizard onMoodCreated={handleMoodCreated} /> : null}
            </div>
            {visibleMoods.length === 0 ? (
              <HavenSurfaceState
                variant="light"
                tone="empty"
                title="No moods in this filter"
                description="Try another tab or teach a mood on Live."
                footer={
                  <Link
                    href="/live"
                    className={cn(roomosUi.havenPrimaryBtn, "rounded-full px-5 py-2.5 text-[13px] font-semibold text-white")}
                  >
                    Open Live
                  </Link>
                }
              />
            ) : null}
          </section>

          <MoodBurstReviewPanel />

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
                      ? "Saved in this browser and on Haven on this device."
                      : authRequired && authEnabled && !session
                        ? "Saved in this browser until you sign in."
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
                onClick={() =>
                  form.reset(presetToFormValues(activePreset, integrationsDoc, moodIds))
                }
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

