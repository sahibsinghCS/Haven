"use client"

import type { ReactNode } from "react"
import type { LucideIcon } from "lucide-react"
import { CheckCircle2, Circle, Loader2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"
import { roomosUi } from "@/lib/roomos/roomos-ui"

export function DeviceConnectionCard({
  icon: Icon,
  title,
  description,
  enabled,
  onEnabledChange,
  connected,
  children,
  onTest,
  testLabel = "Test connection",
  testing = false,
  footer,
}: {
  icon: LucideIcon
  title: string
  description: string
  enabled: boolean
  onEnabledChange: (v: boolean) => void
  connected: boolean
  children?: ReactNode
  onTest?: () => void
  testLabel?: string
  testing?: boolean
  footer?: ReactNode
}) {
  return (
    <article
      className={cn(
        roomosUi.prefsPresetCard,
        "relative overflow-hidden p-6 sm:p-7",
        enabled && "border-teal-800/25 ring-1 ring-teal-900/10",
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 items-start gap-3">
          <span
            className={cn(
              "flex size-11 shrink-0 items-center justify-center rounded-2xl border border-[color:var(--haven-line-strong)]",
              enabled
                ? "bg-[linear-gradient(168deg,#0f766e_0%,#115e59_100%)] text-white shadow-[0_12px_28px_-14px_rgba(15,118,110,0.55)]"
                : "bg-[color-mix(in_oklab,#fffefb_90%,transparent)] text-[color:var(--haven-muted)]",
            )}
          >
            <Icon className="size-5" strokeWidth={1.85} aria-hidden />
          </span>
          <div className="min-w-0 space-y-1">
            <h2 className="text-[17px] font-semibold tracking-tight text-[color:var(--haven-ink)]">
              {title}
            </h2>
            <p className="text-[13px] leading-relaxed text-[color:var(--haven-muted)]">{description}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide",
              connected
                ? "border-teal-700/20 bg-teal-50 text-teal-900"
                : "border-stone-300/80 bg-stone-100/80 text-stone-600",
            )}
          >
            {connected ? (
              <CheckCircle2 className="size-3.5" aria-hidden />
            ) : (
              <Circle className="size-3.5" aria-hidden />
            )}
            {connected ? "Connected" : "Not connected"}
          </span>
          <div className="flex items-center gap-2">
            <Label htmlFor={`enable-${title}`} className="sr-only">
              Enable {title}
            </Label>
            <span className="text-[12px] font-medium text-[color:var(--haven-muted)]">
              Mood automations
            </span>
            <Switch
              id={`enable-${title}`}
              checked={enabled}
              onCheckedChange={onEnabledChange}
            />
          </div>
        </div>
      </div>

      {children ? (
        <div className="mt-6 space-y-4 border-t border-[color:var(--haven-line)] pt-6">
          {children}
          {!enabled ? (
            <p className="text-[12px] leading-relaxed text-[color:var(--haven-muted)]">
              You can connect and test below. Turn on <strong className="font-medium">Mood automations</strong>{" "}
              when Live should control this device from Preferences.
            </p>
          ) : null}
        </div>
      ) : null}

      {onTest || footer ? (
        <div className="mt-5 flex flex-wrap items-center gap-3">
          {onTest ? (
            <Button type="button" variant="outline" size="sm" onClick={onTest} disabled={testing}>
              {testing ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
              {testLabel}
            </Button>
          ) : null}
          {footer}
        </div>
      ) : null}
    </article>
  )
}

export function SettingsField({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: ReactNode
}) {
  return (
    <div className="space-y-2">
      <Label className="text-[13px] font-semibold text-[color:var(--haven-ink)]">{label}</Label>
      {children}
      {hint ? (
        <p className="text-[12px] leading-relaxed text-[color:var(--haven-muted)]">{hint}</p>
      ) : null}
    </div>
  )
}

export { Input as SettingsInput, Textarea as SettingsTextarea }
