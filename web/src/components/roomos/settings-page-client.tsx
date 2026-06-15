"use client"

import { useCallback, useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Lightbulb, Save, Thermometer } from "lucide-react"
import { toast } from "sonner"

import {
  DeviceConnectionCard,
  SettingsField,
  SettingsInput,
  SettingsTextarea,
} from "@/components/roomos/settings/device-connection-card"
import { DeviceSetupInstructions } from "@/components/roomos/settings/device-setup-instructions"
import { HavenConnectHero } from "@/components/roomos/settings/haven-connect-hero"
import { SimplePlugConnect } from "@/components/roomos/settings/simple-plug-connect"
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
import { HavenOfflineBanner } from "@/components/roomos/haven-offline-banner"
import { RoomsSettingsSection } from "@/components/roomos/rooms-settings-section"
import {
  fetchDeviceSettingsDocument,
  saveDeviceSettingsDocument,
  testLights,
  testSmartPlug,
  testThermostat,
} from "@/lib/roomos/api-client"
import {
  defaultDeviceSettingsDocument,
  defaultLightsDevice,
  defaultSmartPlugDevice,
  defaultThermostatDevice,
  ensureMinimumDevices,
} from "@/lib/roomos/device-settings-schema"
import { loadDeviceSettingsLocal, saveDeviceSettingsLocal } from "@/lib/roomos/device-settings-persistence"
import { getGuide, LIGHTS_GUIDES, THERMOSTAT_GUIDES } from "@/lib/roomos/device-setup-guides"
import { roomosUi } from "@/lib/roomos/roomos-ui"
import type {
  DeviceSettingsDocument,
  LightsBrand,
  LightsDevice,
  SmartPlugBrand,
  SmartPlugDevice,
  ThermostatBrand,
  ThermostatDevice,
} from "@/types/device-settings"

import { cn } from "@/lib/utils"

const PLUG_CLOUD_ONLY: SmartPlugBrand[] = ["wyze", "amazon"]
const THERMOSTAT_TEST_BRANDS: ThermostatBrand[] = [
  "honeywell_home",
  "honeywell_tcc",
  "ecobee",
  "nest",
]

function validatePlugForTest(plug: SmartPlugDevice): string | null {
  if (PLUG_CLOUD_ONLY.includes(plug.brand)) {
    return "Wyze and Amazon plugs are not supported for direct control yet. Try TP-Link Kasa, Shelly, Tuya, or Meross."
  }
  if (plug.brand === "tapo") {
    if (!plug.tapoEmail?.trim() || !plug.tapoPassword?.trim()) {
      return "Enter your Tapo app email and password (same login as on your phone)."
    }
    if (!plug.host?.trim()) {
      return "Enter the plug’s IP from Tapo → Device Info or your router."
    }
    return null
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

type DeviceArrayKey = "smartPlugs" | "lights" | "thermostats"

function patchPrimaryDevice(
  doc: DeviceSettingsDocument,
  key: DeviceArrayKey,
  patch: Record<string, unknown>,
): DeviceSettingsDocument {
  const ensured = ensureMinimumDevices(doc)
  return {
    ...ensured,
    devices: {
      ...ensured.devices,
      [key]: ensured.devices[key].map((item, index) =>
        index === 0 ? { ...item, ...patch } : item,
      ),
    },
  }
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

  const primaryPlug = doc?.devices.smartPlugs[0]
  const primaryLights = doc?.devices.lights[0]
  const primaryThermostat = doc?.devices.thermostats[0]

  const lightsGuide = useMemo(
    () => getGuide("lights", primaryLights?.brand ?? "none"),
    [primaryLights?.brand],
  )
  const thermostatGuide = useMemo(
    () => getGuide("thermostat", primaryThermostat?.brand ?? "none"),
    [primaryThermostat?.brand],
  )

  const canTestPlug =
    primaryPlug &&
    getGuide("smart_plug", primaryPlug.brand)?.supportsDirectControl &&
    !PLUG_CLOUD_ONLY.includes(primaryPlug.brand)

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
    key: "smartPlugs" | "lights" | "thermostats",
    deviceId: string,
    extra?: Partial<SmartPlugDevice>,
  ) => {
    const connectedDoc: DeviceSettingsDocument = {
      ...payload,
      devices: {
        ...payload.devices,
        [key]: payload.devices[key].map((item) =>
          item.id === deviceId
            ? {
                ...item,
                connected: true,
                enabled: true,
                ...(key === "smartPlugs" ? extra : {}),
              }
            : item,
        ),
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
    const plug = doc.devices.smartPlugs[0] ?? defaultSmartPlugDevice()
    const validation = validatePlugForTest(plug)
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
      const savedPlug = saved.devices.smartPlugs[0] ?? plug
      await testSmartPlug({
        device_id: savedPlug.id,
        brand: savedPlug.brand,
        host: savedPlug.host,
        state: "on",
      })
      await markDeviceConnected(saved, "smartPlugs", savedPlug.id)
      toast.success("Connected — your plug should have turned on. Set fan on/off per mood in Preferences.")
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Plug test failed")
    } finally {
      setTestingPlug(false)
    }
  }

  const handleTestLights = async () => {
    if (!doc) return
    const lights = doc.devices.lights[0] ?? defaultLightsDevice()
    if (lights.brand !== "tuya") {
      toast.error("Direct light control is available for Tuya / Smart Life bulbs today. Pick that brand or use the manufacturer app.")
      return
    }
    if (!lights.tuyaDeviceId?.trim() || !lights.tuyaLocalKey?.trim()) {
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
      const savedLights = saved.devices.lights[0] ?? lights
      await testLights({ device_id: savedLights.id, brightness: 60, light_color_hex: "#E8F4FF" })
      await markDeviceConnected(saved, "lights", savedLights.id)
      toast.success("Lights connected — check the bulb.")
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Lights test failed")
    } finally {
      setTestingLights(false)
    }
  }

  const handleTestThermostat = async () => {
    if (!doc) return
    const t = doc.devices.thermostats[0] ?? defaultThermostatDevice()
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
      const thermo = saved.devices.thermostats[0] ?? t
      const result = await testThermostat({
        device_id: thermo.id,
        heat_f: thermo.targetHeatF ?? 70,
        cool_f: thermo.targetCoolF,
      })
      await markDeviceConnected(saved, "thermostats", thermo.id)
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
  const docWithDefaults = ensureMinimumDevices(doc)
  const smartPlug = docWithDefaults.devices.smartPlugs[0]!
  const lights = docWithDefaults.devices.lights[0]!
  const thermostat = docWithDefaults.devices.thermostats[0]!

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-8 pb-24">
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

      {!apiOnline && !authRequired ? <HavenOfflineBanner context="settings" /> : null}

      <HavenConnectHero />

      <SimplePlugConnect
        plug={smartPlug}
        connected={smartPlug.connected}
        testing={testingPlug}
        canConnect={Boolean(canTestPlug)}
        onConnect={() => void handleTestPlug()}
        onChange={(patch) =>
          patchDoc((d) => {
            const ensured = ensureMinimumDevices(d)
            return {
              ...ensured,
              devices: {
                ...ensured.devices,
                smartPlugs: ensured.devices.smartPlugs.map((p, i) =>
                  i === 0 ? { ...p, ...patch } : p,
                ),
              },
            }
          })
        }
      />

      <HavenAccountBar />

      <details className="group rounded-2xl border border-[color:var(--haven-line)] bg-[color-mix(in_oklab,#fffefb_88%,transparent)]">
        <summary className="cursor-pointer list-none px-5 py-4 text-[14px] font-semibold text-[color:var(--haven-ink)] marker:content-none [&::-webkit-details-marker]:hidden">
          More devices
          <span className="ml-2 text-[12px] font-normal text-[color:var(--haven-faint)]">
            lights, thermostat
          </span>
        </summary>
        <div className="flex flex-col gap-6 border-t border-[color:var(--haven-line)] p-5">

        <DeviceConnectionCard
          icon={Lightbulb}
          title="Lights"
          description="Bulbs, strips, and switches — Hue, LIFX, WiZ, Govee, Matter, and more."
          enabled={lights.enabled}
          onEnabledChange={(v) => patchDoc((d) => patchPrimaryDevice(d, "lights", { enabled: v }))}
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
                patchDoc((d) =>
                  patchPrimaryDevice(d, "lights", { brand: v as LightsBrand, connected: false }),
                )
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
                    patchDoc((d) => patchPrimaryDevice(d, "lights", { tuyaDeviceId: e.target.value }))
                  }
                  className="font-mono text-[13px]"
                />
              </SettingsField>
              <SettingsField label="Local key">
                <SettingsInput
                  type="password"
                  value={lights.tuyaLocalKey ?? ""}
                  onChange={(e) =>
                    patchDoc((d) => patchPrimaryDevice(d, "lights", { tuyaLocalKey: e.target.value }))
                  }
                  className="font-mono text-[13px]"
                />
              </SettingsField>
              <SettingsField label="Bulb IP (optional)">
                <SettingsInput
                  value={lights.host ?? ""}
                  onChange={(e) => patchDoc((d) => patchPrimaryDevice(d, "lights", { host: e.target.value }))}
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
              onChange={(e) => patchDoc((d) => patchPrimaryDevice(d, "lights", { notes: e.target.value }))}
              rows={3}
              placeholder="Bedroom main, Desk strip, Sleep scene…"
            />
          </SettingsField>
        </DeviceConnectionCard>

        <DeviceConnectionCard
          icon={Thermometer}
          title="Thermostat"
          description="Nest, ecobee, Honeywell Home, Sensi, and other Wi‑Fi thermostats."
          enabled={thermostat.enabled}
          onEnabledChange={(v) => patchDoc((d) => patchPrimaryDevice(d, "thermostats", { enabled: v }))}
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
                patchDoc((d) =>
                  patchPrimaryDevice(d, "thermostats", { brand: v as ThermostatBrand, connected: false }),
                )
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
                    patchDoc((d) => patchPrimaryDevice(d, "thermostats", { username: e.target.value }))
                  }
                />
              </SettingsField>
              <SettingsField label="Password">
                <SettingsInput
                  type="password"
                  value={thermostat.password ?? ""}
                  onChange={(e) =>
                    patchDoc((d) => patchPrimaryDevice(d, "thermostats", { password: e.target.value }))
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
                    patchDoc((d) => patchPrimaryDevice(d, "thermostats", { nestProjectId: e.target.value }))
                  }
                  className="font-mono text-[13px]"
                />
              </SettingsField>
              <SettingsField label="OAuth client ID" hint="Google Cloud → APIs & Services → Credentials.">
                <SettingsInput
                  value={thermostat.nestClientId ?? ""}
                  onChange={(e) =>
                    patchDoc((d) => patchPrimaryDevice(d, "thermostats", { nestClientId: e.target.value }))
                  }
                  className="font-mono text-[13px]"
                />
              </SettingsField>
              <SettingsField label="OAuth client secret">
                <SettingsInput
                  type="password"
                  value={thermostat.nestClientSecret ?? ""}
                  onChange={(e) =>
                    patchDoc((d) => patchPrimaryDevice(d, "thermostats", { nestClientSecret: e.target.value }))
                  }
                />
              </SettingsField>
              <SettingsField label="Refresh token" hint="From one-time Google OAuth authorization.">
                <SettingsInput
                  type="password"
                  value={thermostat.nestRefreshToken ?? ""}
                  onChange={(e) =>
                    patchDoc((d) => patchPrimaryDevice(d, "thermostats", { nestRefreshToken: e.target.value }))
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
                    patchDoc((d) => patchPrimaryDevice(d, "thermostats", { ecobeeApiKey: e.target.value }))
                  }
                  className="font-mono text-[13px]"
                />
              </SettingsField>
              <SettingsField label="Refresh token" hint="One-time PIN authorization on the developer portal.">
                <SettingsInput
                  type="password"
                  value={thermostat.ecobeeRefreshToken ?? ""}
                  onChange={(e) =>
                    patchDoc((d) => patchPrimaryDevice(d, "thermostats", { ecobeeRefreshToken: e.target.value }))
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
                  patchDoc((d) =>
                    patchPrimaryDevice(d, "thermostats", { targetHeatF: Number(e.target.value) || 70 }),
                  )
                }
              />
            </SettingsField>
          )}

          <SettingsField label="Home name & notes" hint="Thermostat label in the app, heat/cool limits, etc.">
            <SettingsTextarea
              value={thermostat.notes}
              onChange={(e) =>
                patchDoc((d) => patchPrimaryDevice(d, "thermostats", { notes: e.target.value }))
              }
              rows={3}
              placeholder="Downstairs, heat 68°F sleep / 72°F work…"
            />
          </SettingsField>
        </DeviceConnectionCard>
        </div>
      </details>

      {doc ? (
        <div className="rounded-2xl border border-[color:var(--haven-line)] bg-white/40 p-5">
          <RoomsSettingsSection devicesDoc={doc} />
        </div>
      ) : null}

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
