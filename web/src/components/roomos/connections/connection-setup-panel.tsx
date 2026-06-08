"use client"

import { useState } from "react"
import { Eye, EyeOff, Loader2 } from "lucide-react"

import { ConnectionBrandPicker } from "@/components/roomos/connections/connection-brand-picker"
import { DeviceSetupInstructions } from "@/components/roomos/settings/device-setup-instructions"
import {
  SettingsField,
  SettingsInput,
  SettingsTextarea,
} from "@/components/roomos/settings/device-connection-card"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import type { ConnectionFieldSpec } from "@/lib/roomos/device-connection-fields"
import type { DeviceCategory, DeviceSetupGuide } from "@/lib/roomos/device-setup-guides"
import { roomosUi } from "@/lib/roomos/roomos-ui"

export function ConnectionSetupPanel({
  categoryLabel,
  guides,
  guide,
  brand,
  onBrandChange,
  fields,
  values,
  onFieldChange,
  canConnect,
  connectLabel = "Connect",
  connecting,
  onConnect,
  connectError,
}: {
  categoryLabel: string
  guides: DeviceSetupGuide[]
  guide: DeviceSetupGuide | undefined
  brand: string
  onBrandChange: (brand: string) => void
  fields: ConnectionFieldSpec[]
  values: Record<string, unknown>
  onFieldChange: (key: string, value: string) => void
  canConnect: boolean
  connectLabel?: string
  connecting: boolean
  onConnect: () => void
  connectError?: string | null
}) {
  return (
    <div className="space-y-6 font-sans">
      <div className="rounded-xl border border-stone-200/80 bg-white/80 px-4 py-3.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.95)]">
        <p className="text-[13px] leading-relaxed text-stone-600">
          Choose your brand, follow the steps, then connect. Your custom name is what shows on the card
          once linked.
        </p>
      </div>

      <ConnectionBrandPicker
        label={`${categoryLabel} brand`}
        guides={guides}
        value={brand}
        onChange={onBrandChange}
      />

      {guide && guide.id !== "none" ? <DeviceSetupInstructions guide={guide} /> : null}

      {fields.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2">
          {fields.map((field) => (
            <FieldInput
              key={field.key}
              field={field}
              value={String(values[field.key] ?? "")}
              onChange={(v) => onFieldChange(field.key, v)}
              className={field.key === "notes" ? "sm:col-span-2" : undefined}
            />
          ))}
        </div>
      ) : null}

      {connectError ? (
        <p className="rounded-lg border border-rose-400/30 bg-rose-50 px-3 py-2 text-[13px] text-rose-900" role="alert">
          {connectError}
        </p>
      ) : null}

      {canConnect ? (
        <Button
          type="button"
          size="lg"
          disabled={connecting}
          onClick={onConnect}
          className={cn("h-11 gap-2 px-6 font-semibold", roomosUi.havenPrimaryBtn)}
        >
          {connecting ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
          {connectLabel}
        </Button>
      ) : guide && !guide.supportsDirectControl ? (
        <p className="text-[13px] leading-relaxed text-[color:var(--haven-muted)]">
          HAVEN cannot connect to this brand automatically yet. Save your device names below so
          automations are ready when support ships.
        </p>
      ) : null}
    </div>
  )
}

function FieldInput({
  field,
  value,
  onChange,
  className,
}: {
  field: ConnectionFieldSpec
  value: string
  onChange: (v: string) => void
  className?: string
}) {
  if (field.key === "notes") {
    return (
      <div className={className}>
        <SettingsField label={field.label} hint={field.hint}>
          <SettingsTextarea
            value={value}
            onChange={(e) => onChange(e.target.value)}
            rows={3}
            placeholder={field.placeholder}
          />
        </SettingsField>
      </div>
    )
  }

  const inputClassName = cn(
    "h-11 border-stone-200/90 bg-white/95 font-sans text-stone-900 shadow-sm placeholder:text-stone-400",
    field.mono && "font-mono text-[13px]",
    field.type === "password" && "pr-11",
    roomosUi.focusRingLight,
  )

  return (
    <div className={className}>
      <SettingsField label={field.label} hint={field.hint}>
        {field.type === "password" ? (
          <PasswordInput
            value={value}
            onChange={onChange}
            placeholder={field.placeholder}
            className={inputClassName}
          />
        ) : (
          <SettingsInput
            type={field.type === "email" ? "email" : "text"}
            inputMode={field.type === "number" ? "decimal" : undefined}
            placeholder={field.placeholder}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            className={inputClassName}
            autoComplete={field.type === "email" ? "username" : undefined}
          />
        )}
      </SettingsField>
    </div>
  )
}

function PasswordInput({
  value,
  onChange,
  placeholder,
  className,
}: {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  className?: string
}) {
  const [visible, setVisible] = useState(false)

  return (
    <div className="relative">
      <SettingsInput
        type={visible ? "text" : "password"}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={className}
        autoComplete="current-password"
      />
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="absolute top-1/2 right-1 size-9 -translate-y-1/2 text-stone-500 hover:bg-stone-900/5 hover:text-stone-800"
        onClick={() => setVisible((v) => !v)}
        aria-label={visible ? "Hide password" : "Show password"}
      >
        {visible ? <EyeOff className="size-4" aria-hidden /> : <Eye className="size-4" aria-hidden />}
      </Button>
    </div>
  )
}
