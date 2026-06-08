"use client"

import { CheckCircle2, ChevronRight, Loader2, Plug } from "lucide-react"

import { SettingsField, SettingsInput } from "@/components/roomos/settings/device-connection-card"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { SMART_PLUG_GUIDES } from "@/lib/roomos/device-setup-guides"
import { cn } from "@/lib/utils"
import { roomosUi } from "@/lib/roomos/roomos-ui"
import type { SmartPlugBrand, SmartPlugSettings } from "@/types/device-settings"

const PLUG_CLOUD_ONLY: SmartPlugBrand[] = ["wyze", "amazon"]
const PLUG_BRANDS_WITH_IP: SmartPlugBrand[] = ["tplink_kasa", "tapo", "shelly", "wemo", "other_plug"]

export function SimplePlugConnect({
  plug,
  connected,
  testing,
  canConnect,
  onConnect,
  onChange,
}: {
  plug: SmartPlugSettings
  connected: boolean
  testing: boolean
  canConnect: boolean
  onConnect: () => void
  onChange: (patch: Partial<SmartPlugSettings>) => void
}) {
  const isTapo = plug.brand === "tapo"
  const ready =
    isTapo &&
    Boolean(plug.tapoEmail?.trim() && plug.tapoPassword?.trim() && plug.host?.trim())

  return (
    <section
      className={cn(
        roomosUi.prefsPresetCard,
        "relative overflow-hidden p-6 sm:p-8",
        connected && "border-teal-700/30 ring-1 ring-teal-800/15",
      )}
      aria-labelledby="simple-plug-heading"
    >
      <div
        className="pointer-events-none absolute -right-20 -top-24 size-56 rounded-full bg-teal-400/10 blur-3xl"
        aria-hidden
      />

      <div className="relative flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <span className="flex size-12 shrink-0 items-center justify-center rounded-2xl bg-[linear-gradient(168deg,#0f766e_0%,#115e59_100%)] text-white shadow-[0_14px_32px_-16px_rgba(15,118,110,0.6)]">
            <Plug className="size-5" strokeWidth={1.85} aria-hidden />
          </span>
          <div>
            <h2
              id="simple-plug-heading"
              className="font-serif text-[clamp(1.5rem,3vw,1.85rem)] font-medium tracking-[-0.02em] text-[color:var(--haven-ink)]"
            >
              Connect your plug
            </h2>
            <p className="mt-1 max-w-md text-[14px] leading-relaxed text-[color:var(--haven-muted)]">
              {isTapo
                ? "Same Tapo login as your phone, plus the plug’s IP. Keep the plug in the Tapo app — don’t remove it."
                : "Enter your device details, then connect."}
            </p>
          </div>
        </div>

        {connected ? (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-teal-600/25 bg-teal-50 px-3 py-1.5 text-[12px] font-semibold text-teal-900">
            <CheckCircle2 className="size-4" aria-hidden />
            Connected
          </span>
        ) : null}
      </div>

      {connected ? (
        <p className="relative mt-5 rounded-2xl border border-teal-600/20 bg-teal-50/80 px-4 py-3 text-[13px] leading-relaxed text-teal-950">
          HAVEN can control this plug when your room mood changes. Set fan on/off per mood in{" "}
          <strong className="font-semibold">Preferences</strong>.
        </p>
      ) : null}

      <div className="relative mt-6 grid gap-4 sm:grid-cols-2">
        {isTapo ? (
          <>
            <SettingsField label="Tapo email">
              <SettingsInput
                type="email"
                autoComplete="username"
                placeholder="you@email.com"
                value={plug.tapoEmail ?? ""}
                onChange={(e) => onChange({ tapoEmail: e.target.value, connected: false })}
                className="h-11"
              />
            </SettingsField>
            <SettingsField label="Tapo password">
              <SettingsInput
                type="password"
                autoComplete="current-password"
                placeholder="••••••••"
                value={plug.tapoPassword ?? ""}
                onChange={(e) => onChange({ tapoPassword: e.target.value, connected: false })}
                className="h-11"
              />
            </SettingsField>
            <div className="sm:col-span-2">
              <SettingsField
                label="Plug IP address"
                hint="Tapo app → your plug → ⚙ Settings → Device Info → IP"
              >
                <SettingsInput
                  inputMode="decimal"
                  placeholder="192.168.1.50"
                  value={plug.host}
                  onChange={(e) => onChange({ host: e.target.value, connected: false })}
                  className="h-11 font-mono text-[14px]"
                />
              </SettingsField>
            </div>
          </>
        ) : (
          <AdvancedPlugFields plug={plug} onChange={onChange} />
        )}
      </div>

      <div className="relative mt-6 flex flex-col gap-3 sm:flex-row sm:items-center">
        <Button
          type="button"
          size="lg"
          disabled={testing || !canConnect || (isTapo && !ready)}
          onClick={onConnect}
          className="h-12 min-w-[10rem] gap-2 bg-[color:var(--haven-ink)] text-[color:var(--haven-paper)] hover:bg-[color:var(--haven-ink)]/90"
        >
          {testing ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
          {connected ? "Test again" : "Connect"}
          {!testing ? <ChevronRight className="size-4 opacity-70" aria-hidden /> : null}
        </Button>
        <p className="text-[12px] text-[color:var(--haven-faint)]">
          Plug should click on when connected. No Home Assistant needed.
        </p>
      </div>

      <details className="relative mt-6 rounded-xl border border-[color:var(--haven-line)] bg-white/40">
        <summary className="cursor-pointer list-none px-4 py-3 text-[13px] font-medium text-[color:var(--haven-muted)] marker:content-none [&::-webkit-details-marker]:hidden">
          Different brand or stuck?
        </summary>
        <div className="space-y-4 border-t border-[color:var(--haven-line)] px-4 py-4">
          {!isTapo ? null : (
            <p className="text-[12px] leading-relaxed text-[color:var(--haven-muted)]">
              On newer Tapo firmware: Tapo app → <strong className="font-medium">Me → Voice Assistant</strong> →
              turn on <strong className="font-medium">Third-Party Compatibility</strong>. Close the Tapo PC app
              if connect fails.
            </p>
          )}
          <SettingsField label="Plug brand">
            <Select
              value={plug.brand}
              onValueChange={(v) => onChange({ brand: v as SmartPlugBrand, connected: false })}
            >
              <SelectTrigger className="w-full max-w-sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {SMART_PLUG_GUIDES.filter((g) => g.id !== "other_plug").map((g) => (
                  <SelectItem key={g.id} value={g.id}>
                    {g.label}
                  </SelectItem>
                ))}
                <SelectItem value="other_plug">Other</SelectItem>
              </SelectContent>
            </Select>
          </SettingsField>
          {plug.brand !== "tapo" ? <AdvancedPlugFields plug={plug} onChange={onChange} /> : null}
        </div>
      </details>
    </section>
  )
}

function AdvancedPlugFields({
  plug,
  onChange,
}: {
  plug: SmartPlugSettings
  onChange: (patch: Partial<SmartPlugSettings>) => void
}) {
  return (
    <>
      {plug.brand === "meross" && (
        <>
          <SettingsField label="Meross email">
            <SettingsInput
              type="email"
              value={plug.merossEmail ?? ""}
              onChange={(e) => onChange({ merossEmail: e.target.value })}
            />
          </SettingsField>
          <SettingsField label="Meross password">
            <SettingsInput
              type="password"
              value={plug.merossPassword ?? ""}
              onChange={(e) => onChange({ merossPassword: e.target.value })}
            />
          </SettingsField>
        </>
      )}
      {(plug.brand === "tuya" || plug.brand === "other_plug") && (
        <>
          <SettingsField label="Tuya device ID">
            <SettingsInput
              value={plug.tuyaDeviceId ?? ""}
              onChange={(e) => onChange({ tuyaDeviceId: e.target.value })}
              className="font-mono text-[13px]"
            />
          </SettingsField>
          <SettingsField label="Local key">
            <SettingsInput
              type="password"
              value={plug.tuyaLocalKey ?? ""}
              onChange={(e) => onChange({ tuyaLocalKey: e.target.value })}
              className="font-mono text-[13px]"
            />
          </SettingsField>
        </>
      )}
      {(PLUG_BRANDS_WITH_IP.includes(plug.brand) || plug.brand === "tuya") &&
      !PLUG_CLOUD_ONLY.includes(plug.brand) ? (
        <SettingsField label="IP address">
          <SettingsInput
            value={plug.host}
            onChange={(e) => onChange({ host: e.target.value, connected: false })}
            placeholder="192.168.1.50"
            className="font-mono text-[13px]"
          />
        </SettingsField>
      ) : null}
    </>
  )
}
