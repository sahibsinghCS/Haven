"use client"

import { useFormContext, useWatch } from "react-hook-form"
import { Fan, Lightbulb, Plug, Thermometer } from "lucide-react"

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
import {
  lightsCapabilities,
  smartPlugCapabilities,
  thermostatCapabilities,
} from "@/lib/roomos/device-capabilities"
import type { PreferenceMatrixFormValues } from "@/lib/roomos/preferences-schema"
import { preferenceCardShell } from "@/lib/roomos/roomos-ui"
import {
  ROOM_STATE_LABEL,
  ROOM_STATE_LANDING_ATMOSPHERE,
  ROOM_STATE_LANDING_SKIN,
} from "@/lib/roomos/state-meta"
import { cn } from "@/lib/utils"
import type { ConnectedDeviceRef, PreferenceMoodId } from "@/types/roomos"
import type { LightsBrand, SmartPlugBrand } from "@/types/device-settings"

const STATE_DESCRIPTION: Record<PreferenceMoodId, string> = {
  sleep: "Rest-first posture: depth without glare.",
  work: "Even field for deep focus.",
  relaxing: "Recovery mode: warm, slow, wide.",
  away: "Absent, but not unmanaged.",
}

const STATE_NUMBER: Record<PreferenceMoodId, string> = {
  sleep: "01",
  work: "02",
  relaxing: "03",
  away: "04",
}

export function StatePreferenceCard({
  stateId,
  connectedDevices,
}: {
  stateId: PreferenceMoodId
  connectedDevices: ConnectedDeviceRef[]
}) {
  const { control } = useFormContext<PreferenceMatrixFormValues>()
  const watched = useWatch({ control, name: stateId })
  const title = ROOM_STATE_LABEL[stateId]
  const skin = ROOM_STATE_LANDING_SKIN[stateId]
  const atmosphere = ROOM_STATE_LANDING_ATMOSPHERE[stateId]

  const plugs = connectedDevices.filter((d) => d.category === "smart_plug")
  const lights = connectedDevices.filter((d) => d.category === "lights")
  const thermostats = connectedDevices.filter((d) => d.category === "thermostat")

  const firstLights = lights[0]
  const previewHex =
    (firstLights && watched?.devices?.[firstLights.id]?.lightColorHex) ?? "#71717a"
  const previewBrightness =
    (firstLights && watched?.devices?.[firstLights.id]?.brightness) ?? 0

  if (connectedDevices.length === 0) {
    return null
  }

  return (
    <fieldset className={cn(preferenceCardShell(stateId), "relative overflow-hidden")}>
      <legend className="sr-only">{title}: device preferences</legend>
      <div className={cn("pointer-events-none absolute inset-0 bg-gradient-to-br opacity-[0.34]", skin.wash)} aria-hidden />
      <div className={cn("pointer-events-none absolute -right-14 -top-16 size-36 rounded-full blur-3xl opacity-50", skin.glow)} aria-hidden />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/90 to-transparent"
      />

      <header className="relative flex flex-col gap-5 border-b border-[color:var(--haven-line)] pb-5 sm:flex-row sm:items-start sm:justify-between sm:gap-6">
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
          <div className="flex flex-wrap gap-1.5 pt-1">
            <span className={cn("rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ring-1 ring-inset", skin.tag)}>
              {atmosphere.light.split(";")[0]}
            </span>
            <span className="rounded-full bg-white/65 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-[color:var(--haven-muted)] ring-1 ring-inset ring-[color:var(--haven-line)]">
              {atmosphere.air.split(";")[0]}
            </span>
          </div>
        </div>
        {firstLights ? (
          <LightTonePreview hex={previewHex} brightness={previewBrightness} className="shrink-0" />
        ) : null}
      </header>

      <div className="relative grid gap-5 pt-5 sm:gap-6 sm:pt-6">
        {plugs.map((device) => {
          const caps = smartPlugCapabilities(device.brand as SmartPlugBrand)
          if (!caps.powerOnly && !caps.brightness) return null
          return (
            <FormField
              key={device.id}
              control={control}
              name={`${stateId}.devices.${device.id}.fanOn`}
              render={({ field }) => (
                <FormItem>
                  <div className="flex flex-col gap-4 rounded-[1rem] border border-[color:var(--haven-line-strong)] bg-[color-mix(in_oklab,#fffefb_82%,transparent)] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.96),0_8px_20px_-18px_rgba(18,17,15,0.22)] backdrop-blur-sm sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex min-w-0 items-center gap-3">
                      <span
                        className={cn(
                          "flex size-9 shrink-0 items-center justify-center rounded-lg border border-[color:var(--haven-line-strong)] transition-colors",
                          field.value ? "bg-sky-50 text-sky-700" : "bg-white text-stone-500",
                        )}
                        aria-hidden
                      >
                        {device.category === "smart_plug" ? (
                          <Plug className="size-[1.05rem]" strokeWidth={1.85} />
                        ) : (
                          <Fan
                            className={cn("size-[1.05rem]", field.value && "motion-safe:animate-spin")}
                            style={field.value ? { animationDuration: "3.4s" } : undefined}
                            strokeWidth={1.85}
                          />
                        )}
                      </span>
                      <div className="space-y-0.5">
                        <FormLabel className="text-[13px] font-semibold tracking-tight text-[color:var(--haven-ink)]">
                          {device.label}
                        </FormLabel>
                        <FormDescription className="text-[12px] leading-relaxed text-[color:var(--haven-muted)]">
                          On/off only — relay smart plugs cannot dim.
                        </FormDescription>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="min-w-[2.25rem] text-right text-[13px] font-semibold tabular-nums text-[color:var(--haven-ink-soft)]" aria-live="polite">
                        {field.value ? "On" : "Off"}
                      </span>
                      <FormControl>
                        <Switch
                          checked={Boolean(field.value)}
                          onCheckedChange={field.onChange}
                          className={cn(
                            "h-6 w-11 border shadow-sm",
                            "data-unchecked:border-stone-300 data-unchecked:bg-stone-200",
                            "data-checked:border-teal-800 data-checked:bg-teal-700",
                            "[&_[data-slot=switch-thumb]]:size-5 [&_[data-slot=switch-thumb]]:bg-white [&_[data-slot=switch-thumb]]:shadow-md",
                            "group-data-[size=default]/switch:data-checked:translate-x-[calc(100%-2px)]",
                          )}
                        />
                      </FormControl>
                    </div>
                  </div>
                  <FormMessage />
                </FormItem>
              )}
            />
          )
        })}

        {lights.map((device) => {
          const caps = lightsCapabilities(device.brand as LightsBrand)
          return (
            <div key={device.id} className="space-y-5 rounded-[1rem] border border-[color:var(--haven-line-strong)] bg-white/40 p-4">
              <p className="flex items-center gap-1.5 text-[12px] font-semibold uppercase tracking-[0.16em] text-[color:var(--haven-muted)]">
                <Lightbulb className="size-3.5 text-amber-700/80" aria-hidden strokeWidth={2} />
                {device.label}
              </p>

              {caps.color ? (
                <FormField
                  control={control}
                  name={`${stateId}.devices.${device.id}.lightColorHex`}
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel className="text-[12px] font-semibold uppercase tracking-[0.16em] text-[color:var(--haven-muted)]">
                        Light color
                      </FormLabel>
                      <div className="mt-2 flex flex-wrap items-center gap-3">
                        <FormControl>
                          <Input
                            {...field}
                            value={field.value ?? "#71717a"}
                            className="h-10 rounded-xl border-stone-300 bg-white/88 font-mono text-[13px]"
                            autoComplete="off"
                            spellCheck={false}
                          />
                        </FormControl>
                        <label className="relative size-12 cursor-pointer overflow-hidden rounded-xl border border-stone-300 bg-stone-50">
                          <span className="sr-only">Color picker for {device.label}</span>
                          <input
                            type="color"
                            className="absolute inset-0 opacity-0"
                            value={field.value ?? "#71717a"}
                            onChange={(e) => field.onChange(e.target.value)}
                          />
                          <span
                            className="pointer-events-none absolute inset-1 rounded-lg border border-white/85"
                            style={{ backgroundColor: field.value ?? "#71717a" }}
                            aria-hidden
                          />
                        </label>
                      </div>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              ) : null}

              {caps.brightness ? (
                <FormField
                  control={control}
                  name={`${stateId}.devices.${device.id}.brightness`}
                  render={({ field }) => (
                    <FormItem>
                      <div className="flex items-center justify-between gap-3">
                        <FormLabel className="text-[12px] font-semibold uppercase tracking-[0.16em] text-[color:var(--haven-muted)]">
                          Brightness
                        </FormLabel>
                        <span className="font-mono text-[13px] font-semibold tabular-nums text-[color:var(--haven-ink)]">
                          {field.value ?? 0}%
                        </span>
                      </div>
                      <FormControl>
                        <Slider
                          min={0}
                          max={100}
                          step={1}
                          value={[field.value ?? 0]}
                          onValueChange={(v) => field.onChange(v[0] ?? 0)}
                          aria-label={`${device.label} brightness`}
                          className="mt-3"
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              ) : null}

              {!caps.brightness && !caps.color ? (
                <p className="text-[12px] text-[color:var(--haven-muted)]">
                  This lights brand does not support brightness or color control yet.
                </p>
              ) : null}
            </div>
          )
        })}

        {thermostats.map((device) => {
          const caps = thermostatCapabilities()
          if (!caps.temperature) return null
          return (
            <FormField
              key={device.id}
              control={control}
              name={`${stateId}.devices.${device.id}.temperatureF`}
              render={({ field }) => (
                <FormItem>
                  <div className="flex items-center justify-between gap-3">
                    <FormLabel className="flex items-center gap-1.5 text-[12px] font-semibold uppercase tracking-[0.16em] text-[color:var(--haven-muted)]">
                      <Thermometer className="size-3.5 text-teal-700/80" aria-hidden strokeWidth={2} />
                      {device.label}
                    </FormLabel>
                    <span className="font-mono text-[13px] font-semibold tabular-nums text-[color:var(--haven-ink)]">
                      {field.value ?? 72}°F
                    </span>
                  </div>
                  <FormControl>
                    <Slider
                      min={60}
                      max={82}
                      step={1}
                      value={[field.value ?? 72]}
                      onValueChange={(v) => field.onChange(v[0] ?? field.value)}
                      aria-label={`${device.label} target temperature`}
                      className="mt-3"
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          )
        })}
      </div>
    </fieldset>
  )
}
