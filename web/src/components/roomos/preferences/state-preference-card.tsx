"use client"

import { useFormContext, useWatch } from "react-hook-form"
import { Fan, Lightbulb, Thermometer } from "lucide-react"

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

const STATE_DESCRIPTION: Record<RoomStateId, string> = {
  sleep: "Rest-first posture: depth without glare.",
  gaming: "Contrast for play: energy without spectacle.",
  work: "Even field for deep focus.",
  relaxing: "Recovery mode: warm, slow, wide.",
  away: "Absent, but not unmanaged.",
}

const STATE_NUMBER: Record<RoomStateId, string> = {
  sleep: "01",
  gaming: "02",
  work: "03",
  relaxing: "04",
  away: "05",
}

export function StatePreferenceCard({ stateId }: { stateId: RoomStateId }) {
  const { control } = useFormContext<PreferenceMatrixFormValues>()
  const watched = useWatch({ control, name: stateId })
  const title = ROOM_STATE_LABEL[stateId]

  return (
    <fieldset className={cn(preferenceCardShell(stateId), "relative overflow-hidden")}>
      <legend className="sr-only">{title}: lighting and comfort</legend>

      <header className="flex flex-col gap-5 border-b border-[color:var(--haven-line)] pb-5 sm:flex-row sm:items-start sm:justify-between sm:gap-6">
        <div className="min-w-0 space-y-2">
          <div className="flex items-center gap-2.5">
            <span className="font-mono text-[11px] font-semibold tabular-nums text-[color:var(--haven-faint)]">
              {STATE_NUMBER[stateId]}
            </span>
            <span className="h-3 w-px bg-[color:var(--haven-line-strong)]" aria-hidden />
            <span className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[color:var(--haven-muted)]">
              Mood
            </span>
          </div>
          <h3 className="haven-display text-[1.5rem] font-semibold tracking-[-0.025em] text-[color:var(--haven-ink)] sm:text-[1.6rem]">
            {title}
          </h3>
          <p className="max-w-md text-[13px] leading-relaxed text-[color:var(--haven-muted)]">
            {STATE_DESCRIPTION[stateId]}
          </p>
        </div>
        <LightTonePreview
          hex={watched?.lightColorHex ?? "#71717a"}
          brightness={watched?.brightness ?? 0}
          className="shrink-0"
        />
      </header>

      <div className="grid gap-5 pt-5 sm:grid-cols-2 sm:gap-6 sm:pt-6">
        <FormField
          control={control}
          name={`${stateId}.lightColorHex`}
          render={({ field }) => (
            <FormItem className="sm:col-span-2">
              <FormLabel className="flex items-center gap-1.5 text-[12px] font-semibold uppercase tracking-[0.16em] text-[color:var(--haven-muted)]">
                <Lightbulb className="size-3.5 text-amber-700/80" aria-hidden strokeWidth={2} />
                Light color
              </FormLabel>
              <div className="mt-2 flex flex-wrap items-center gap-3">
                <FormControl>
                  <Input
                    {...field}
                    className="h-10 rounded-xl border-stone-300 bg-white font-mono text-[13px] tracking-tight text-[color:var(--haven-ink)] shadow-[inset_0_1px_0_rgba(255,255,255,1),0_1px_2px_rgba(18,17,15,0.04)]"
                    autoComplete="off"
                    spellCheck={false}
                    aria-describedby={`${stateId}-color-hint`}
                  />
                </FormControl>
                <label className="relative size-12 cursor-pointer overflow-hidden rounded-xl border border-stone-300 bg-stone-50 shadow-[inset_0_1px_2px_rgba(18,17,15,0.06),0_1px_2px_rgba(18,17,15,0.05)] focus-within:ring-2 focus-within:ring-cyan-600/35 focus-within:ring-offset-2 focus-within:ring-offset-white">
                  <span className="sr-only">Color picker for {title}</span>
                  <input
                    type="color"
                    className="absolute inset-0 h-[200%] w-[200%] -translate-x-1/4 -translate-y-1/4 cursor-pointer opacity-0"
                    value={field.value}
                    onChange={(e) => field.onChange(e.target.value)}
                  />
                  <span
                    className="pointer-events-none absolute inset-1 rounded-lg border border-white/85 shadow-[inset_0_1px_2px_rgba(255,255,255,0.6)]"
                    style={{ backgroundColor: field.value }}
                    aria-hidden
                  />
                </label>
              </div>
              <FormDescription
                id={`${stateId}-color-hint`}
                className="mt-2 text-[12px] text-[color:var(--haven-muted)]"
              >
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
                <FormLabel className="text-[12px] font-semibold uppercase tracking-[0.16em] text-[color:var(--haven-muted)]">
                  Brightness
                </FormLabel>
                <span className="font-mono text-[13px] font-semibold tabular-nums text-[color:var(--haven-ink)]">
                  {field.value}
                  <span className="ml-0.5 text-[11px] font-medium text-[color:var(--haven-faint)]">
                    %
                  </span>
                </span>
              </div>
              <FormControl>
                <Slider
                  min={0}
                  max={100}
                  step={1}
                  value={[field.value]}
                  onValueChange={(v) => field.onChange(v[0] ?? 0)}
                  aria-label={`${title} brightness`}
                  className="mt-3 [&_[data-slot=slider-track]]:bg-stone-200/95 [&_[data-slot=slider-track]]:shadow-[inset_0_1px_2px_rgba(18,17,15,0.08)] [&_[data-slot=slider-range]]:bg-[linear-gradient(90deg,rgba(180,83,9,0.78),rgba(245,158,11,0.95))] [&_[data-slot=slider-thumb]]:size-3.5 [&_[data-slot=slider-thumb]]:border-stone-400 [&_[data-slot=slider-thumb]]:bg-white [&_[data-slot=slider-thumb]]:shadow-[0_1px_3px_rgba(18,17,15,0.18),0_0_0_1px_rgba(18,17,15,0.04)] [&_[data-slot=slider-thumb]]:ring-amber-500/30"
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
                <FormLabel className="flex items-center gap-1.5 text-[12px] font-semibold uppercase tracking-[0.16em] text-[color:var(--haven-muted)]">
                  <Thermometer className="size-3.5 text-teal-700/80" aria-hidden strokeWidth={2} />
                  Temperature
                </FormLabel>
                <span className="font-mono text-[13px] font-semibold tabular-nums text-[color:var(--haven-ink)]">
                  {field.value}
                  <span className="ml-0.5 text-[11px] font-medium text-[color:var(--haven-faint)]">
                    °F
                  </span>
                </span>
              </div>
              <FormControl>
                <Slider
                  min={60}
                  max={82}
                  step={1}
                  value={[field.value]}
                  onValueChange={(v) => field.onChange(v[0] ?? field.value)}
                  aria-label={`${title} target temperature`}
                  className="mt-3 [&_[data-slot=slider-track]]:bg-stone-200/95 [&_[data-slot=slider-track]]:shadow-[inset_0_1px_2px_rgba(18,17,15,0.08)] [&_[data-slot=slider-range]]:bg-[linear-gradient(90deg,rgba(8,145,178,0.7),rgba(15,118,110,0.95))] [&_[data-slot=slider-thumb]]:size-3.5 [&_[data-slot=slider-thumb]]:border-stone-400 [&_[data-slot=slider-thumb]]:bg-white [&_[data-slot=slider-thumb]]:shadow-[0_1px_3px_rgba(18,17,15,0.18),0_0_0_1px_rgba(18,17,15,0.04)] [&_[data-slot=slider-thumb]]:ring-teal-500/30"
                />
              </FormControl>
              <FormDescription className="mt-2 text-[12px] text-[color:var(--haven-muted)]">
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
              <div className="flex flex-col gap-4 rounded-xl border border-[color:var(--haven-line-strong)] bg-[color-mix(in_oklab,#fffefb_88%,transparent)] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.96)] sm:flex-row sm:items-center sm:justify-between">
                <div className="flex min-w-0 items-center gap-3">
                  <span
                    className={cn(
                      "flex size-9 shrink-0 items-center justify-center rounded-lg border border-[color:var(--haven-line-strong)] transition-colors",
                      field.value
                        ? "bg-sky-50 text-sky-700"
                        : "bg-white text-stone-500",
                    )}
                    aria-hidden
                  >
                    <Fan
                      className={cn("size-[1.05rem]", field.value && "motion-safe:animate-spin")}
                      style={field.value ? { animationDuration: "3.4s" } : undefined}
                      strokeWidth={1.85}
                    />
                  </span>
                  <div className="space-y-0.5">
                    <FormLabel className="text-[13px] font-semibold tracking-tight text-[color:var(--haven-ink)]">
                      Fan
                    </FormLabel>
                    <FormDescription className="text-[12px] leading-relaxed text-[color:var(--haven-muted)]">
                      Often a smart plug on a dumb fan.
                    </FormDescription>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span
                    className="min-w-[2.25rem] text-right text-[13px] font-semibold tabular-nums text-[color:var(--haven-ink-soft)]"
                    aria-live="polite"
                  >
                    {field.value ? "On" : "Off"}
                  </span>
                  <FormControl>
                    <Switch
                      checked={field.value}
                      onCheckedChange={field.onChange}
                      className="h-5 w-9 border-stone-300 data-checked:bg-[linear-gradient(168deg,#1e1c19,#0f766e)] data-unchecked:bg-stone-300/85 dark:data-unchecked:bg-stone-300/90 [&_[data-slot=switch-thumb]]:size-4 [&_[data-slot=switch-thumb]]:bg-white [&_[data-slot=switch-thumb]]:shadow-[0_1px_3px_rgba(18,17,15,0.22)] dark:[&_[data-slot=switch-thumb]]:bg-white dark:data-checked:[&_[data-slot=switch-thumb]]:bg-white dark:data-unchecked:[&_[data-slot=switch-thumb]]:bg-white [&_[data-slot=switch-thumb]]:data-checked:translate-x-[calc(100%-2px)] [&_[data-slot=switch-thumb]]:data-unchecked:translate-x-0"
                    />
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
