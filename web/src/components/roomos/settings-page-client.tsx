"use client"

import { useCallback, useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Lightbulb, Plug, Save, Thermometer } from "lucide-react"
import { toast } from "sonner"

import {
  DeviceConnectionCard,
  SettingsField,
  SettingsInput,
  SettingsTextarea,
} from "@/components/roomos/settings/device-connection-card"
import {
  CategoryIntro,
  DeviceSetupInstructions,
} from "@/components/roomos/settings/device-setup-instructions"
import { PreferencesSkeleton } from "@/components/roomos/roomos-loading-states"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useHavenAuth } from "@/components/auth/haven-auth-provider"
import { HavenAccountBar } from "@/components/roomos/haven-account-bar"
import {
  fetchDeviceSettingsDocument,
  saveDeviceSettingsDocument,
  testLights,
  testSmartPlug,
  testThermostat,
} from "@/lib/roomos/api-client"
import { defaultDeviceSettingsDocument } from "@/lib/roomos/device-settings-schema"
import { loadDeviceSettingsLocal, saveDeviceSettingsLocal } from "@/lib/roomos/device-settings-persistence"
import {
  CATEGORY_INTROS,
  getGuide,
  LIGHTS_GUIDES,
  SMART_PLUG_GUIDES,
  THERMOSTAT_GUIDES,
} from "@/lib/roomos/device-setup-guides"
import { roomosUi } from "@/lib/roomos/roomos-ui"
import type { DeviceSettingsDocument, LightsBrand, SmartPlugBrand, ThermostatBrand } from "@/types/device-settings"

import { cn } from "@/lib/utils"

const PLUG_BRANDS_WITH_IP: SmartPlugBrand[] = ["tplink_kasa", "tapo", "shelly", "wemo", "other_plug"]
const PLUG_CLOUD_ONLY: SmartPlugBrand[] = ["wyze", "amazon"]
const THERMOSTAT_TEST_BRANDS: ThermostatBrand[] = [
  "honeywell_home",
  "honeywell_tcc",
  "ecobee",
  "nest",
]

function validatePlugForTest(plug: DeviceSettingsDocument["devices"]["smartPlug"]): string | null {
  if (PLUG_CLOUD_ONLY.includes(plug.brand)) {
    return "Wyze and Amazon plugs are not supported for direct control yet. Try TP-Link Kasa, Shelly, Tuya, or Meross."
  }
  if (plug.brand === "meross") {
    if (!plug.merossEmail?.trim() || !plug.merossPassword?.trim()) {
      return "Enter your Meross app email and password."
    }
    return null
  }
  if (plug.brand === "tuya" || plug.brand === "other_plug") {
    if (!plug.tuyaDeviceId?.trim() || !plug.tuyaLocalKey?.trim()) {
      return "Enter Tuya device ID and local key (run python -m tinytuya wizard on the HAVEN computer)."
    }
    return null
  }
  if (!plug.host?.trim()) {
    return "Enter the plug’s IP address from your router’s connected-devices list."
  }
  return null
}

export function SettingsPageClient() {
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState<DeviceSettingsDocument | null>(null)
  const [dirty, setDirty] = useState(false)
  const [testingPlug, setTestingPlug] = useState(false)
  const [testingThermostat, setTestingThermostat] = useState(false)
  const [testingLights, setTestingLights] = useState(false)
  const { user, enabled: authEnabled, session } = useHavenAuth()

  const docQuery = useQuery({
    queryKey: ["roomos", "integrations", user?.id ?? "local"],
    queryFn: async () => {
      try {
        const doc = await fetchDeviceSettingsDocument()
        return { doc, apiOnline: true as const, authRequired: false as const }
      } catch (e) {
        const message = e instanceof Error ? e.message : ""
        const authRequired = message.includes("Sign in required")
        const local = loadDeviceSettingsLocal()
        return {
          doc: local ?? defaultDeviceSettingsDocument(),
          apiOnline: false as const,
          authRequired,
        }
      }
    },
    staleTime: 30_000,
  })

  const doc = dirty && draft ? draft : docQuery.data?.doc ?? null

  const patchDoc = useCallback((updater: (prev: DeviceSettingsDocument) => DeviceSettingsDocument) => {
    setDraft((prev) => {
      const base = prev ?? docQuery.data?.doc ?? defaultDeviceSettingsDocument()
      const next = updater(structuredClone(base))
      setDirty(true)
      return next
    })
  }, [docQuery.data?.doc])

  const saveMutation = useMutation({
    mutationFn: async (payload: DeviceSettingsDocument) => {
      try {
        return { doc: await saveDeviceSettingsDocument(payload), apiOnline: true as const }
      } catch {
        saveDeviceSettingsLocal(payload)
        return { doc: payload, apiOnline: false as const }
      }
    },
    onSuccess: (result) => {
      setDraft(null)
      setDirty(false)
      saveDeviceSettingsLocal(result.doc)
      queryClient.setQueryData(["roomos", "integrations", user?.id ?? "local"], {
        doc: result.doc,
        apiOnline: result.apiOnline,
        authRequired: false,
      })
      toast.success(
        result.apiOnline
          ? user
            ? "Device connections saved to your account"
            : "Device connections saved"
          : "Saved in this browser — start the API (npm run demo) to sync",
      )
    },
    onError: () => toast.error("Could not save settings"),
  })

  const plugGuide = useMemo(
    () => getGuide("smart_plug", doc?.devices.smartPlug.brand ?? "tplink_kasa"),
    [doc?.devices.smartPlug.brand],
  )
  const lightsGuide = useMemo(
    () => getGuide("lights", doc?.devices.lights.brand ?? "none"),
    [doc?.devices.lights.brand],
  )
  const thermostatGuide = useMemo(
    () => getGuide("thermostat", doc?.devices.thermostat.brand ?? "none"),
    [doc?.devices.thermostat.brand],
  )

  const canTestPlug =
    doc &&
    plugGuide?.supportsDirectControl &&
    !PLUG_CLOUD_ONLY.includes(doc.devices.smartPlug.brand)

  const persistBeforeTest = async (payload: DeviceSettingsDocument) => {
    try {
      const saved = await saveDeviceSettingsDocument(payload)
      saveDeviceSettingsLocal(saved)
      queryClient.setQueryData(["roomos", "integrations", user?.id ?? "local"], {
        doc: saved,
        apiOnline: true,
        authRequired: false,
      })
      setDraft(null)
      setDirty(false)
      return { saved, apiOnline: true as const }
    } catch (e) {
      const message = e instanceof Error ? e.message : ""
      if (message.includes("Sign in required")) {
        throw e
      }
      saveDeviceSettingsLocal(payload)
      toast.message("Saved in this browser only — start the API (npm run demo) so the test can reach your device.")
      return { saved: payload, apiOnline: false as const }
    }
  }

  const markDeviceConnected = async (
    payload: DeviceSettingsDocument,
    key: "smartPlug" | "lights" | "thermostat",
  ) => {
    const connectedDoc: DeviceSettingsDocument = {
      ...payload,
      devices: {
        ...payload.devices,
        [key]: { ...payload.devices[key], connected: true },
      },
    }
    try {
      const saved = await saveDeviceSettingsDocument(connectedDoc)
      saveDeviceSettingsLocal(saved)
      queryClient.setQueryData(["roomos", "integrations", user?.id ?? "local"], {
        doc: saved,
        apiOnline: true,
        authRequired: false,
      })
      setDraft(null)
      setDirty(false)
      return saved
    } catch {
      saveDeviceSettingsLocal(connectedDoc)
      setDraft(connectedDoc)
      setDirty(true)
      return connectedDoc
    }
  }

  const handleTestPlug = async () => {
    if (!doc) return
    const validation = validatePlugForTest(doc.devices.smartPlug)
    if (validation) {
      toast.error(validation)
      return
    }
    setTestingPlug(true)
    try {
      const { saved, apiOnline } = await persistBeforeTest(doc)
      if (!apiOnline) {
        toast.error("Start the HAVEN API on this computer (npm run demo), then try again.")
        return
      }
      const plug = saved.devices.smartPlug
      await testSmartPlug({
        brand: plug.brand,
        host: plug.host,
        state: "on",
      })
      await markDeviceConnected(saved, "smartPlug")
      toast.success("Plug connected — it should have turned on. Mood automations use Preferences when Live runs.")
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Plug test failed")
    } finally {
      setTestingPlug(false)
    }
  }

  const handleTestLights = async () => {
    if (!doc) return
    if (doc.devices.lights.brand !== "tuya") {
      toast.error("Direct light control is available for Tuya / Smart Life bulbs today. Pick that brand or use the manufacturer app.")
      return
    }
    if (!doc.devices.lights.tuyaDeviceId?.trim() || !doc.devices.lights.tuyaLocalKey?.trim()) {
      toast.error("Enter Tuya device ID and local key for your bulb.")
      return
    }
    setTestingLights(true)
    try {
      const { saved, apiOnline } = await persistBeforeTest(doc)
      if (!apiOnline) {
        toast.error("Start the HAVEN API (npm run demo), then try again.")
        return
      }
      await testLights({ brightness: 60, light_color_hex: "#E8F4FF" })
      await markDeviceConnected(saved, "lights")
      toast.success("Lights connected — check the bulb.")
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Lights test failed")
    } finally {
      setTestingLights(false)
    }
  }

  const handleTestThermostat = async () => {
    if (!doc) return
    const t = doc.devices.thermostat
    if (t.brand === "honeywell_home" || t.brand === "honeywell_tcc") {
      if (!t.username?.trim() || !t.password?.trim()) {
        toast.error("Enter the same Honeywell account email and password as the mobile app.")
        return
      }
    }
    if (t.brand === "ecobee" && !t.ecobeeRefreshToken?.trim()) {
      toast.error("Enter your ecobee API key and refresh token.")
      return
    }
    if (t.brand === "nest" && (!t.nestRefreshToken?.trim() || !t.nestProjectId?.trim())) {
      toast.error("Complete Nest Device Access setup (project ID, OAuth client, refresh token).")
      return
    }
    setTestingThermostat(true)
    try {
      const { saved, apiOnline } = await persistBeforeTest(doc)
      if (!apiOnline) {
        toast.error("Start the HAVEN API (npm run demo), then try again.")
        return
      }
      const thermo = saved.devices.thermostat
      const result = await testThermostat({
        heat_f: thermo.targetHeatF ?? 70,
        cool_f: thermo.targetCoolF,
      })
      await markDeviceConnected(saved, "thermostat")
      const temp =
        result.current_temperature_f != null
          ? ` Current temperature ${result.current_temperature_f}°F.`
          : ""
      toast.success(`Thermostat connected.${temp}`)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Thermostat test failed")
    } finally {
      setTestingThermostat(false)
    }
  }

  if (docQuery.isPending || !doc) {
    return <PreferencesSkeleton />
  }

  const apiOnline = docQuery.data?.apiOnline ?? true
  const authRequired = docQuery.data?.authRequired ?? false
  const { smartPlug, lights, thermostat } = doc.devices

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-10 pb-32">
      {authRequired && authEnabled && !session ? (
        <p
          className={cn(
            roomosUi.prefsCallout,
            "border-rose-500/25 bg-rose-50/90 px-4 py-3 text-[13px] leading-relaxed text-rose-950",
          )}
          role="alert"
        >
          Sign in to save and control devices from this computer. Connections you enter here are only
          stored in the browser until you log in.
        </p>
      ) : null}

      {!apiOnline && !authRequired ? (
        <p
          className={cn(
            roomosUi.prefsCallout,
            "border-amber-500/25 bg-amber-50/90 px-4 py-3 text-[13px] leading-relaxed text-amber-950",
          )}
          role="status"
        >
          HAVEN is offline on this computer — settings are stored in your browser until you run the app
          locally (<span className="font-mono text-[12px]">npm run demo</span>).
        </p>
      ) : null}

      <header className="relative overflow-hidden rounded-[2.15rem] border border-[color:var(--haven-line-strong)] bg-[linear-gradient(165deg,rgba(255,254,251,0.995)_0%,rgba(251,246,238,0.97)_44%,rgba(236,228,218,0.94)_100%)] p-6 shadow-[var(--haven-shadow-float)] ring-1 ring-[color:var(--haven-edge-light)] sm:p-8">
        <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-[color:var(--haven-faint)]">
          Connections
        </p>
        <h1 className="mt-2 font-serif text-[clamp(2rem,4.5vw,2.75rem)] font-medium leading-[1.08] tracking-[-0.03em] text-[color:var(--haven-ink)]">
          Settings
        </h1>
        <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-[color:var(--haven-muted)]">
          Pick your brand, enter Wi‑Fi IP or cloud credentials, then use{" "}
          <strong className="font-semibold text-[color:var(--haven-ink)]">Connect &amp; test</strong> — HAVEN
          talks to the real device from this computer (same network for local plugs).{" "}
          <strong className="font-semibold text-[color:var(--haven-ink)]">Preferences</strong> set comfort
          per mood; turn on <strong className="font-semibold">Mood automations</strong> on each card when
          Live should apply them.
        </p>
        <ol className="mt-4 max-w-2xl list-decimal space-y-1 pl-5 text-[13px] leading-relaxed text-[color:var(--haven-muted)]">
          <li>Run <span className="font-mono text-[12px]">npm run demo</span> on the PC on your home Wi‑Fi.</li>
          <li>Choose brand → fill IP or account fields → Connect &amp; test.</li>
          <li>Save if you edited without testing; cloud sync needs sign-in when Supabase is on.</li>
        </ol>
      </header>

      <HavenAccountBar />

      <CategoryIntro
        title="Works with most Wi‑Fi smart home gear"
        paragraphs={[
          "HAVEN connects over your home Wi‑Fi (local control) or through the same cloud accounts you already use in the manufacturer’s app — no extra hub required for many devices.",
          "Pick your brand, fill in the fields, save, then use Test connection. When your room mood changes on Live, HAVEN applies that mood’s Preferences to these devices (set dry_run: false in actions config).",
        ]}
      />

      <div className="flex flex-col gap-6">
        <DeviceConnectionCard
          icon={Plug}
          title="Smart plug"
          description="Outlets for fans, lamps, or desk gear — TP-Link, Meross, Shelly, Wyze, and more."
          enabled={smartPlug.enabled}
          onEnabledChange={(v) =>
            patchDoc((d) => ({
              ...d,
              devices: { ...d.devices, smartPlug: { ...d.devices.smartPlug, enabled: v } },
            }))
          }
          connected={smartPlug.connected}
          onTest={canTestPlug ? handleTestPlug : undefined}
          testLabel="Connect & test plug"
          testing={testingPlug}
          footer={
            PLUG_CLOUD_ONLY.includes(smartPlug.brand) ? (
              <p className="text-[12px] leading-relaxed text-[color:var(--haven-muted)]">
                {smartPlug.brand === "wyze" ? "Wyze" : "Amazon"} plugs need cloud linking (coming soon). Use
                TP-Link Kasa, Shelly, Tuya, or Meross for Connect &amp; test today.
              </p>
            ) : undefined
          }
        >
          <SettingsField label="Brand">
            <Select
              value={smartPlug.brand}
              onValueChange={(v) =>
                patchDoc((d) => ({
                  ...d,
                  devices: {
                    ...d.devices,
                    smartPlug: {
                      ...d.devices.smartPlug,
                      brand: v as SmartPlugBrand,
                      connected: false,
                    },
                  },
                }))
              }
            >
              <SelectTrigger className="w-full max-w-sm">
                <SelectValue placeholder="Choose brand…" />
              </SelectTrigger>
              <SelectContent>
                {SMART_PLUG_GUIDES.filter((g) => g.id !== "other_plug").map((g) => (
                  <SelectItem key={g.id} value={g.id}>
                    {g.label}
                  </SelectItem>
                ))}
                <SelectItem value="other_plug">Other brand</SelectItem>
              </SelectContent>
            </Select>
          </SettingsField>

          {plugGuide ? <DeviceSetupInstructions guide={plugGuide} /> : null}

          {(smartPlug.brand === "tuya" || smartPlug.brand === "other_plug") && (
            <>
              <SettingsField label="Tuya device ID" hint="From python -m tinytuya wizard or the Smart Life app device info.">
                <SettingsInput
                  value={smartPlug.tuyaDeviceId ?? ""}
                  onChange={(e) =>
                    patchDoc((d) => ({
                      ...d,
                      devices: {
                        ...d.devices,
                        smartPlug: {
                          ...d.devices.smartPlug,
                          tuyaDeviceId: e.target.value,
                          connected: false,
                        },
                      },
                    }))
                  }
                  className="font-mono text-[13px]"
                />
              </SettingsField>
              <SettingsField label="Local key">
                <SettingsInput
                  type="password"
                  value={smartPlug.tuyaLocalKey ?? ""}
                  onChange={(e) =>
                    patchDoc((d) => ({
                      ...d,
                      devices: {
                        ...d.devices,
                        smartPlug: {
                          ...d.devices.smartPlug,
                          tuyaLocalKey: e.target.value,
                          connected: false,
                        },
                      },
                    }))
                  }
                  className="font-mono text-[13px]"
                />
              </SettingsField>
              <SettingsField label="Protocol version" hint="Usually 3.3 — check wizard output if control fails.">
                <SettingsInput
                  value={smartPlug.tuyaVersion ?? "3.3"}
                  onChange={(e) =>
                    patchDoc((d) => ({
                      ...d,
                      devices: {
                        ...d.devices,
                        smartPlug: { ...d.devices.smartPlug, tuyaVersion: e.target.value },
                      },
                    }))
                  }
                  className="font-mono text-[13px]"
                />
              </SettingsField>
            </>
          )}

          {smartPlug.brand === "meross" && (
            <>
              <SettingsField label="Meross account email">
                <SettingsInput
                  type="email"
                  value={smartPlug.merossEmail ?? ""}
                  onChange={(e) =>
                    patchDoc((d) => ({
                      ...d,
                      devices: {
                        ...d.devices,
                        smartPlug: { ...d.devices.smartPlug, merossEmail: e.target.value },
                      },
                    }))
                  }
                />
              </SettingsField>
              <SettingsField label="Meross password">
                <SettingsInput
                  type="password"
                  value={smartPlug.merossPassword ?? ""}
                  onChange={(e) =>
                    patchDoc((d) => ({
                      ...d,
                      devices: {
                        ...d.devices,
                        smartPlug: { ...d.devices.smartPlug, merossPassword: e.target.value },
                      },
                    }))
                  }
                />
              </SettingsField>
            </>
          )}

          {PLUG_BRANDS_WITH_IP.includes(smartPlug.brand) || smartPlug.brand === "tuya" ? (
            <SettingsField
              label="Device IP address (on your Wi‑Fi)"
              hint="From your router’s device list. Tuya can use Auto if discovery works."
            >
              <SettingsInput
                value={smartPlug.host}
                onChange={(e) =>
                  patchDoc((d) => ({
                    ...d,
                    devices: {
                      ...d.devices,
                      smartPlug: { ...d.devices.smartPlug, host: e.target.value, connected: false },
                    },
                  }))
                }
                placeholder={smartPlug.brand === "tuya" ? "192.168.1.50 or leave blank for Auto" : "192.168.1.50"}
                className="font-mono text-[13px]"
              />
            </SettingsField>
          ) : null}

          {smartPlug.brand === "shelly" && (
            <SettingsField label="Shelly generation">
              <Select
                value={smartPlug.shellyGen ?? "1"}
                onValueChange={(v) =>
                  patchDoc((d) => ({
                    ...d,
                    devices: { ...d.devices, smartPlug: { ...d.devices.smartPlug, shellyGen: v } },
                  }))
                }
              >
                <SelectTrigger className="w-full max-w-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="1">Gen 1 (relay URL)</SelectItem>
                  <SelectItem value="2">Gen 2 (RPC)</SelectItem>
                </SelectContent>
              </Select>
            </SettingsField>
          )}

          {!PLUG_CLOUD_ONLY.includes(smartPlug.brand) && (
            <SettingsField label="Name in your home" hint="e.g. Fan — used to pick the right Meross plug if you have several.">
              <SettingsInput
                value={smartPlug.label}
                onChange={(e) =>
                  patchDoc((d) => ({
                    ...d,
                    devices: {
                      ...d.devices,
                      smartPlug: { ...d.devices.smartPlug, label: e.target.value },
                    },
                  }))
                }
              />
            </SettingsField>
          )}

          {PLUG_CLOUD_ONLY.includes(smartPlug.brand) && (
            <SettingsField label="Device name" hint="These brands need the manufacturer app; pick a LAN plug above for direct HAVEN control.">
              <SettingsInput
                value={smartPlug.label}
                onChange={(e) =>
                  patchDoc((d) => ({
                    ...d,
                    devices: {
                      ...d.devices,
                      smartPlug: { ...d.devices.smartPlug, label: e.target.value },
                    },
                  }))
                }
              />
            </SettingsField>
          )}
        </DeviceConnectionCard>

        <CategoryIntro title={CATEGORY_INTROS.lights.title} paragraphs={CATEGORY_INTROS.lights.paragraphs} />

        <DeviceConnectionCard
          icon={Lightbulb}
          title="Lights"
          description="Bulbs, strips, and switches — Hue, LIFX, WiZ, Govee, Matter, and more."
          enabled={lights.enabled}
          onEnabledChange={(v) =>
            patchDoc((d) => ({
              ...d,
              devices: { ...d.devices, lights: { ...d.devices.lights, enabled: v } },
            }))
          }
          connected={lights.connected}
          onTest={lights.brand === "tuya" ? handleTestLights : undefined}
          testLabel="Connect & test lights"
          testing={testingLights}
          footer={
            lights.brand !== "none" && lights.brand !== "tuya" ? (
              <p className="text-[12px] leading-relaxed text-[color:var(--haven-muted)]">
                Direct control in HAVEN is available for Tuya / Smart Life bulbs. Other brands: note room
                names below for future support, or switch brand to Tuya if your bulb uses Smart Life.
              </p>
            ) : undefined
          }
        >
          <SettingsField label="Brand">
            <Select
              value={lights.brand}
              onValueChange={(v) =>
                patchDoc((d) => ({
                  ...d,
                  devices: {
                    ...d.devices,
                    lights: {
                      ...d.devices.lights,
                      brand: v as LightsBrand,
                      connected: false,
                    },
                  },
                }))
              }
            >
              <SelectTrigger className="w-full max-w-sm">
                <SelectValue placeholder="Choose brand…" />
              </SelectTrigger>
              <SelectContent>
                {LIGHTS_GUIDES.map((g) => (
                  <SelectItem key={g.id} value={g.id}>
                    {g.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </SettingsField>

          {lightsGuide && lights.brand !== "none" ? (
            <DeviceSetupInstructions guide={lightsGuide} />
          ) : null}

          {lights.brand === "tuya" && (
            <>
              <SettingsField label="Tuya device ID">
                <SettingsInput
                  value={lights.tuyaDeviceId ?? ""}
                  onChange={(e) =>
                    patchDoc((d) => ({
                      ...d,
                      devices: {
                        ...d.devices,
                        lights: { ...d.devices.lights, tuyaDeviceId: e.target.value },
                      },
                    }))
                  }
                  className="font-mono text-[13px]"
                />
              </SettingsField>
              <SettingsField label="Local key">
                <SettingsInput
                  type="password"
                  value={lights.tuyaLocalKey ?? ""}
                  onChange={(e) =>
                    patchDoc((d) => ({
                      ...d,
                      devices: {
                        ...d.devices,
                        lights: { ...d.devices.lights, tuyaLocalKey: e.target.value },
                      },
                    }))
                  }
                  className="font-mono text-[13px]"
                />
              </SettingsField>
              <SettingsField label="Bulb IP (optional)">
                <SettingsInput
                  value={lights.host ?? ""}
                  onChange={(e) =>
                    patchDoc((d) => ({
                      ...d,
                      devices: { ...d.devices, lights: { ...d.devices.lights, host: e.target.value } },
                    }))
                  }
                  className="font-mono text-[13px]"
                />
              </SettingsField>
            </>
          )}

          <SettingsField
            label="Rooms, scenes, or device names"
            hint="What you called them in the brand’s app — HAVEN maps moods to these labels."
          >
            <SettingsTextarea
              value={lights.notes}
              onChange={(e) =>
                patchDoc((d) => ({
                  ...d,
                  devices: { ...d.devices, lights: { ...d.devices.lights, notes: e.target.value } },
                }))
              }
              rows={3}
              placeholder="Bedroom main, Desk strip, Sleep scene…"
            />
          </SettingsField>
        </DeviceConnectionCard>

        <CategoryIntro
          title={CATEGORY_INTROS.thermostat.title}
          paragraphs={CATEGORY_INTROS.thermostat.paragraphs}
        />

        <DeviceConnectionCard
          icon={Thermometer}
          title="Thermostat"
          description="Nest, ecobee, Honeywell Home, Sensi, and other Wi‑Fi thermostats."
          enabled={thermostat.enabled}
          onEnabledChange={(v) =>
            patchDoc((d) => ({
              ...d,
              devices: { ...d.devices, thermostat: { ...d.devices.thermostat, enabled: v } },
            }))
          }
          connected={thermostat.connected}
          onTest={
            THERMOSTAT_TEST_BRANDS.includes(thermostat.brand) ? handleTestThermostat : undefined
          }
          testLabel="Connect & test thermostat"
          testing={testingThermostat}
          footer={
            thermostat.brand !== "none" && !THERMOSTAT_TEST_BRANDS.includes(thermostat.brand) ? (
              <p className="text-[12px] leading-relaxed text-[color:var(--haven-muted)]">
                Nest, ecobee, and Honeywell can be tested here once credentials are filled in. This brand
                is not wired yet — pick a supported brand or use the manufacturer app.
              </p>
            ) : undefined
          }
        >
          <SettingsField label="Brand">
            <Select
              value={thermostat.brand}
              onValueChange={(v) =>
                patchDoc((d) => ({
                  ...d,
                  devices: {
                    ...d.devices,
                    thermostat: {
                      ...d.devices.thermostat,
                      brand: v as ThermostatBrand,
                      connected: false,
                    },
                  },
                }))
              }
            >
              <SelectTrigger className="w-full max-w-sm">
                <SelectValue placeholder="Choose brand…" />
              </SelectTrigger>
              <SelectContent>
                {THERMOSTAT_GUIDES.map((g) => (
                  <SelectItem key={g.id} value={g.id}>
                    {g.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </SettingsField>

          {thermostatGuide && thermostat.brand !== "none" ? (
            <DeviceSetupInstructions guide={thermostatGuide} />
          ) : null}

          {THERMOSTAT_TEST_BRANDS.includes(thermostat.brand) &&
          thermostat.brand !== "ecobee" &&
          thermostat.brand !== "nest" ? (
            <>
              <SettingsField label="Account email / username">
                <SettingsInput
                  value={thermostat.username ?? ""}
                  onChange={(e) =>
                    patchDoc((d) => ({
                      ...d,
                      devices: {
                        ...d.devices,
                        thermostat: { ...d.devices.thermostat, username: e.target.value },
                      },
                    }))
                  }
                />
              </SettingsField>
              <SettingsField label="Password">
                <SettingsInput
                  type="password"
                  value={thermostat.password ?? ""}
                  onChange={(e) =>
                    patchDoc((d) => ({
                      ...d,
                      devices: {
                        ...d.devices,
                        thermostat: { ...d.devices.thermostat, password: e.target.value },
                      },
                    }))
                  }
                />
              </SettingsField>
            </>
          ) : null}

          {thermostat.brand === "nest" && (
            <>
              <SettingsField
                label="Device Access project ID"
                hint="From console.nest.google.com → your project."
              >
                <SettingsInput
                  value={thermostat.nestProjectId ?? ""}
                  onChange={(e) =>
                    patchDoc((d) => ({
                      ...d,
                      devices: {
                        ...d.devices,
                        thermostat: { ...d.devices.thermostat, nestProjectId: e.target.value },
                      },
                    }))
                  }
                  className="font-mono text-[13px]"
                />
              </SettingsField>
              <SettingsField label="OAuth client ID" hint="Google Cloud → APIs & Services → Credentials.">
                <SettingsInput
                  value={thermostat.nestClientId ?? ""}
                  onChange={(e) =>
                    patchDoc((d) => ({
                      ...d,
                      devices: {
                        ...d.devices,
                        thermostat: { ...d.devices.thermostat, nestClientId: e.target.value },
                      },
                    }))
                  }
                  className="font-mono text-[13px]"
                />
              </SettingsField>
              <SettingsField label="OAuth client secret">
                <SettingsInput
                  type="password"
                  value={thermostat.nestClientSecret ?? ""}
                  onChange={(e) =>
                    patchDoc((d) => ({
                      ...d,
                      devices: {
                        ...d.devices,
                        thermostat: {
                          ...d.devices.thermostat,
                          nestClientSecret: e.target.value,
                        },
                      },
                    }))
                  }
                />
              </SettingsField>
              <SettingsField label="Refresh token" hint="From one-time Google OAuth authorization.">
                <SettingsInput
                  type="password"
                  value={thermostat.nestRefreshToken ?? ""}
                  onChange={(e) =>
                    patchDoc((d) => ({
                      ...d,
                      devices: {
                        ...d.devices,
                        thermostat: {
                          ...d.devices.thermostat,
                          nestRefreshToken: e.target.value,
                        },
                      },
                    }))
                  }
                  className="font-mono text-[13px]"
                />
              </SettingsField>
            </>
          )}

          {thermostat.brand === "ecobee" && (
            <>
              <SettingsField label="Ecobee API key" hint="From developer.ecobee.com → Create app.">
                <SettingsInput
                  value={thermostat.ecobeeApiKey ?? ""}
                  onChange={(e) =>
                    patchDoc((d) => ({
                      ...d,
                      devices: {
                        ...d.devices,
                        thermostat: { ...d.devices.thermostat, ecobeeApiKey: e.target.value },
                      },
                    }))
                  }
                  className="font-mono text-[13px]"
                />
              </SettingsField>
              <SettingsField label="Refresh token" hint="One-time PIN authorization on the developer portal.">
                <SettingsInput
                  type="password"
                  value={thermostat.ecobeeRefreshToken ?? ""}
                  onChange={(e) =>
                    patchDoc((d) => ({
                      ...d,
                      devices: {
                        ...d.devices,
                        thermostat: {
                          ...d.devices.thermostat,
                          ecobeeRefreshToken: e.target.value,
                        },
                      },
                    }))
                  }
                  className="font-mono text-[13px]"
                />
              </SettingsField>
            </>
          )}

          {THERMOSTAT_TEST_BRANDS.includes(thermostat.brand) && (
            <SettingsField label="Test heat setpoint (°F)" hint="Used only for Test connection — moods use Preferences.">
              <SettingsInput
                type="number"
                value={thermostat.targetHeatF ?? 70}
                onChange={(e) =>
                  patchDoc((d) => ({
                    ...d,
                    devices: {
                      ...d.devices,
                      thermostat: {
                        ...d.devices.thermostat,
                        targetHeatF: Number(e.target.value) || 70,
                      },
                    },
                  }))
                }
              />
            </SettingsField>
          )}

          <SettingsField label="Home name & notes" hint="Thermostat label in the app, heat/cool limits, etc.">
            <SettingsTextarea
              value={thermostat.notes}
              onChange={(e) =>
                patchDoc((d) => ({
                  ...d,
                  devices: {
                    ...d.devices,
                    thermostat: { ...d.devices.thermostat, notes: e.target.value },
                  },
                }))
              }
              rows={3}
              placeholder="Downstairs, heat 68°F sleep / 72°F work…"
            />
          </SettingsField>
        </DeviceConnectionCard>
      </div>

      <div
        className={cn(
          roomosUi.prefsStickyBar,
          "sticky bottom-4 z-20 flex flex-wrap items-center justify-between gap-4 px-5 py-4",
        )}
      >
        <p className="text-[13px] text-[color:var(--haven-muted)]">
          {dirty ? "Unsaved changes" : "All changes saved"}
        </p>
        <Button
          type="button"
          disabled={!dirty || saveMutation.isPending}
          onClick={() => doc && saveMutation.mutate(doc)}
          className="gap-2"
        >
          <Save className="size-4" aria-hidden />
          Save settings
        </Button>
      </div>
    </div>
  )
}
