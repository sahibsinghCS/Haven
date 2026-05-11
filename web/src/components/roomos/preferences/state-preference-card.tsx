"use client"

import { useFormContext, useWatch } from "react-hook-form"

import { LightTonePreview } from "@/components/roomos/preferences/light-tone-preview"
import {
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { Slider } from "@/components/ui/slider"
import { Switch } from "@/components/ui/switch"
import type { PreferenceMatrixFormValues } from "@/lib/roomos/preferences-schema"
import { preferenceCardShell } from "@/lib/roomos/roomos-ui"
import { ROOM_STATE_LABEL } from "@/lib/roomos/state-meta"
import { cn } from "@/lib/utils"
import type { RoomStateId } from "@/types/roomos"

export function StatePreferenceCard({ stateId }: { stateId: RoomStateId }) {
  const { control } = useFormContext<PreferenceMatrixFormValues>()
  const watched = useWatch({ control, name: stateId })
  const title = ROOM_STATE_LABEL[stateId]

  return (
    <fieldset className={cn(preferenceCardShell(stateId))}>
      <legend className="sr-only">{title} — lighting and comfort</legend>

      <div className="flex flex-col gap-4 border-b border-zinc-200/90 pb-5 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-1.5">
          <h3 className="text-xl font-semibold tracking-tight text-zinc-900 sm:text-2xl">
            {title}
          </h3>
          <p className="max-w-md text-sm leading-relaxed text-zinc-600">
            When Haven picks this mood, the room moves toward these settings.
          </p>
        </div>
        <LightTonePreview
          hex={watched?.lightColorHex ?? "#71717a"}
          brightness={watched?.brightness ?? 0}
          className="shrink-0 sm:pl-2"
        />
      </div>

      <div className="grid gap-5 pt-6 sm:grid-cols-2 sm:gap-6">
        <FormField
          control={control}
          name={`${stateId}.lightColorHex`}
          render={({ field }) => (
            <FormItem className="sm:col-span-2">
              <FormLabel className="text-zinc-800">Light color</FormLabel>
              <div className="flex flex-wrap items-center gap-3">
                <FormControl>
                  <Input
                    {...field}
                    className="border-zinc-200 bg-white font-mono text-sm tracking-tight text-zinc-900 shadow-sm"
                    autoComplete="off"
                    spellCheck={false}
                    aria-describedby={`${stateId}-color-hint`}
                  />
                </FormControl>
                <label className="relative size-12 cursor-pointer overflow-hidden rounded-xl border border-zinc-200 bg-zinc-50 shadow-inner focus-within:ring-2 focus-within:ring-cyan-600/35 focus-within:ring-offset-2 focus-within:ring-offset-white">
                  <span className="sr-only">Color picker for {title}</span>
                  <input
                    type="color"
                    className="absolute inset-0 h-[200%] w-[200%] -translate-x-1/4 -translate-y-1/4 cursor-pointer opacity-0"
                    value={field.value}
                    onChange={(e) => field.onChange(e.target.value)}
                  />
                  <span
                    className="pointer-events-none absolute inset-1 rounded-lg border border-zinc-200/80"
                    style={{ backgroundColor: field.value }}
                    aria-hidden
                  />
                </label>
              </div>
              <FormDescription id={`${stateId}-color-hint`} className="text-zinc-600">
                Type a hex code or use the swatch.
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={control}
          name={`${stateId}.brightness`}
          render={({ field }) => (
            <FormItem>
              <div className="flex items-center justify-between gap-3">
                <FormLabel className="text-zinc-800">Brightness</FormLabel>
                <span className="text-sm tabular-nums text-zinc-600">{field.value}%</span>
              </div>
              <FormControl>
                <Slider
                  min={0}
                  max={100}
                  step={1}
                  value={[field.value]}
                  onValueChange={(v) => field.onChange(v[0] ?? 0)}
                  aria-label={`${title} brightness`}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={control}
          name={`${stateId}.temperatureF`}
          render={({ field }) => (
            <FormItem>
              <div className="flex items-center justify-between gap-3">
                <FormLabel className="text-zinc-800">Temperature</FormLabel>
                <span className="text-sm tabular-nums text-zinc-600">{field.value}°F</span>
              </div>
              <FormControl>
                <Slider
                  min={60}
                  max={82}
                  step={1}
                  value={[field.value]}
                  onValueChange={(v) => field.onChange(v[0] ?? field.value)}
                  aria-label={`${title} target temperature`}
                />
              </FormControl>
              <FormDescription className="text-zinc-600">
                For thermostats when Haven has access.
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={control}
          name={`${stateId}.fanOn`}
          render={({ field }) => (
            <FormItem className="sm:col-span-2">
              <div className="flex flex-col gap-4 rounded-xl border border-zinc-200/90 bg-zinc-50/80 p-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="space-y-1">
                  <FormLabel className="text-zinc-800">Fan</FormLabel>
                  <FormDescription className="text-xs leading-relaxed text-zinc-600">
                    Often a smart plug on a dumb fan.
                  </FormDescription>
                </div>
                <div className="flex items-center gap-3">
                  <span
                    className="min-w-[2rem] text-sm tabular-nums text-zinc-700"
                    aria-live="polite"
                  >
                    {field.value ? "On" : "Off"}
                  </span>
                  <FormControl>
                    <Switch checked={field.value} onCheckedChange={field.onChange} />
                  </FormControl>
                </div>
              </div>
              <FormMessage />
            </FormItem>
          )}
        />
      </div>
    </fieldset>
  )
}
