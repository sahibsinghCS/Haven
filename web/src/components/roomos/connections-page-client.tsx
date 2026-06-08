"use client"

import { useCallback, useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Lightbulb, Plug, Thermometer } from "lucide-react"
import { toast } from "sonner"

import { useHavenAuth } from "@/components/auth/haven-auth-provider"
import { ConnectionDeviceRow } from "@/components/roomos/connections/connection-device-row"
import { ConnectionSetupPanel } from "@/components/roomos/connections/connection-setup-panel"
import { HavenAccountBar } from "@/components/roomos/haven-account-bar"
import { PreferencesSkeleton } from "@/components/roomos/roomos-loading-states"
import {
  fetchDeviceSettingsDocument,
  saveDeviceSettingsDocument,
  testLights,
  testSmartPlug,
  testThermostat,
} from "@/lib/roomos/api-client"
import {
  canConnectCategory,
  deviceRowPresentation,
  lightsFields,
  plugFields,
  resolveSmartPlugBrand,
  thermostatFields,
  validateLightsConnect,
  validatePlugConnect,
  validateThermostatConnect,
} from "@/lib/roomos/device-connection-fields"
import { defaultDeviceSettingsDocument } from "@/lib/roomos/device-settings-schema"
import { loadDeviceSettingsLocal, saveDeviceSettingsLocal } from "@/lib/roomos/device-settings-persistence"
import {
  getGuide,
  LIGHTS_GUIDES,
  SMART_PLUG_GUIDES,
  THERMOSTAT_GUIDES,
} from "@/lib/roomos/device-setup-guides"
import { roomosUi } from "@/lib/roomos/roomos-ui"
import type { DeviceSettingsDocument, LightsBrand, SmartPlugBrand, ThermostatBrand } from "@/types/device-settings"
import { cn } from "@/lib/utils"

type DeviceKey = "smartPlug" | "lights" | "thermostat"
type ExpandKey = DeviceKey | null

const DEVICE_META: {
  key: DeviceKey
  title: string
  icon: typeof Plug
}[] = [
  { key: "smartPlug", title: "Smart plug", icon: Plug },
  { key: "lights", title: "Lights", icon: Lightbulb },
  { key: "thermostat", title: "Thermostat", icon: Thermometer },
]

export function ConnectionsPageClient() {
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState<DeviceSettingsDocument | null>(null)
  const [dirty, setDirty] = useState(false)
  const [expanded, setExpanded] = useState<ExpandKey>(null)
  const [testing, setTesting] = useState<DeviceKey | null>(null)
  const [disconnecting, setDisconnecting] = useState<DeviceKey | null>(null)
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

  const persistDoc = useCallback(
    async (payload: DeviceSettingsDocument) => {
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
        if (message.includes("Sign in required")) throw e
        saveDeviceSettingsLocal(payload)
        return { saved: payload, apiOnline: false as const }
      }
    },
    [queryClient, user?.id],
  )

  const saveMutation = useMutation({
    mutationFn: persistDoc,
    onSuccess: () => toast.success("Connections saved"),
    onError: () => toast.error("Could not save"),
  })

  const handleDisconnect = async (key: DeviceKey) => {
    if (!doc) return
    setDisconnecting(key)
    try {
      const next: DeviceSettingsDocument = {
        ...doc,
        devices: {
          ...doc.devices,
          [key]: { ...doc.devices[key], connected: false, enabled: false },
        },
      }
      await persistDoc(next)
      toast.success("Disconnected")
      if (expanded && key === expanded) setExpanded(null)
    } catch {
      toast.error("Could not disconnect")
    } finally {
      setDisconnecting(null)
    }
  }

  const pulseSmartPlug = async (plug: DeviceSettingsDocument["devices"]["smartPlug"]) => {
    const brand = resolveSmartPlugBrand(plug)
    await testSmartPlug({ brand, host: plug.host, state: "on" })
    await new Promise((resolve) => setTimeout(resolve, 750))
    await testSmartPlug({ brand, host: plug.host, state: "off" })
  }

  const handleTestPlug = async () => {
    if (!doc) return
    const err = validatePlugConnect(doc.devices.smartPlug)
    if (err) {
      toast.error(err)
      return
    }
    setTesting("smartPlug")
    try {
      const { apiOnline } = await persistDoc(doc)
      if (!apiOnline) {
        toast.error("Start HAVEN API (npm run demo), then try again.")
        return
      }
      await pulseSmartPlug(doc.devices.smartPlug)
      toast.success("Plug clicked on and off — connection looks good.")
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Plug test failed")
    } finally {
      setTesting(null)
    }
  }

  const handleConnectPlug = async () => {
    if (!doc) return
    const err = validatePlugConnect(doc.devices.smartPlug)
    if (err) {
      toast.error(err)
      return
    }
    if (doc.devices.smartPlug.connected) {
      await handleTestPlug()
      return
    }
    setTesting("smartPlug")
    try {
      const { saved, apiOnline } = await persistDoc(doc)
      if (!apiOnline) {
        toast.error("Start HAVEN API (npm run demo), then try again.")
        return
      }
      const plug = saved.devices.smartPlug
      const brand = resolveSmartPlugBrand(plug)
      await testSmartPlug({ brand, host: plug.host, state: "on" })
      const connected: DeviceSettingsDocument = {
        ...saved,
        devices: {
          ...saved.devices,
          smartPlug: {
            ...saved.devices.smartPlug,
            brand,
            connected: true,
            enabled: true,
          },
        },
      }
      await persistDoc(connected)
      toast.success("Smart plug connected — you should have heard a click.")
      setExpanded(null)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Connect failed")
    } finally {
      setTesting(null)
    }
  }

  const handleConnectLights = async () => {
    if (!doc) return
    const err = validateLightsConnect(doc.devices.lights)
    if (err) {
      toast.error(err)
      return
    }
    setTesting("lights")
    try {
      const { saved, apiOnline } = await persistDoc(doc)
      if (!apiOnline) {
        toast.error("Start HAVEN API (npm run demo), then try again.")
        return
      }
      await testLights({ brightness: 60, light_color_hex: "#E8F4FF" })
      const connected: DeviceSettingsDocument = {
        ...saved,
        devices: {
          ...saved.devices,
          lights: { ...saved.devices.lights, connected: true, enabled: true },
        },
      }
      await persistDoc(connected)
      toast.success("Lights connected")
      setExpanded(null)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Connect failed")
    } finally {
      setTesting(null)
    }
  }

  const handleConnectThermostat = async () => {
    if (!doc) return
    const err = validateThermostatConnect(doc.devices.thermostat)
    if (err) {
      toast.error(err)
      return
    }
    setTesting("thermostat")
    try {
      const { saved, apiOnline } = await persistDoc(doc)
      if (!apiOnline) {
        toast.error("Start HAVEN API (npm run demo), then try again.")
        return
      }
      const t = saved.devices.thermostat
      await testThermostat({
        heat_f: t.targetHeatF ?? 70,
        cool_f: t.targetCoolF,
      })
      const connected: DeviceSettingsDocument = {
        ...saved,
        devices: {
          ...saved.devices,
          thermostat: { ...saved.devices.thermostat, connected: true, enabled: true },
        },
      }
      await persistDoc(connected)
      toast.success("Thermostat connected")
      setExpanded(null)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Connect failed")
    } finally {
      setTesting(null)
    }
  }

  const plugGuide = useMemo(
    () =>
      getGuide(
        "smart_plug",
        doc ? resolveSmartPlugBrand(doc.devices.smartPlug) : "tapo",
      ),
    [doc?.devices.smartPlug],
  )

  if (docQuery.isPending || !doc) {
    return <PreferencesSkeleton />
  }

  const apiOnline = docQuery.data?.apiOnline ?? true
  const authRequired = docQuery.data?.authRequired ?? false

  const connectedCount = DEVICE_META.filter(({ key }) => doc.devices[key].connected).length

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-8 pb-20">
      {authRequired && authEnabled && !session ? (
        <p className={cn(roomosUi.prefsCallout, "border-rose-500/25 bg-rose-50/90 px-4 py-3 text-[13px] text-rose-950")} role="alert">
          Sign in to save connections to your account.
        </p>
      ) : null}

      {!apiOnline && !authRequired ? (
        <p className={cn(roomosUi.prefsCallout, "border-amber-500/25 bg-amber-50/90 px-4 py-3 text-[13px] text-amber-950")} role="status">
          HAVEN API offline — run <span className="font-mono text-[12px]">npm run demo</span> to connect devices.
        </p>
      ) : null}

      <header className="relative overflow-hidden rounded-[1.5rem] border border-stone-200/80 bg-[linear-gradient(145deg,#fffefb_0%,#f8f4ec_48%,#f0ebe2_100%)] px-6 py-7 shadow-[var(--haven-shadow-card)] sm:px-8 sm:py-9">
        <div
          className="pointer-events-none absolute -right-8 -top-20 h-48 w-64 rounded-full bg-teal-400/15 blur-3xl"
          aria-hidden
        />
        <div
          className="pointer-events-none absolute -bottom-16 left-8 h-32 w-40 rounded-full bg-amber-200/20 blur-3xl"
          aria-hidden
        />
        <p className="relative text-[11px] font-semibold uppercase tracking-[0.28em] text-stone-500">
          Devices
        </p>
        <div className="relative mt-2 flex flex-wrap items-end justify-between gap-4">
          <h1 className="font-serif text-[clamp(2rem,4vw,2.85rem)] font-medium tracking-[-0.03em] text-stone-900">
            Connections
          </h1>
          <p
            className={cn(
              "rounded-full border px-3.5 py-1 text-[12px] font-semibold",
              connectedCount > 0
                ? "border-teal-600/30 bg-teal-50 text-teal-900"
                : "border-stone-300/80 bg-white/80 text-stone-600",
            )}
          >
            {connectedCount} of {DEVICE_META.length} connected
          </p>
        </div>
        <p className="relative mt-3 max-w-xl text-[15px] leading-relaxed text-stone-600">
          Name each device whatever you like — your name appears on the card after you connect. No Home
          Assistant required.
        </p>
      </header>

      <div className="flex flex-col gap-5">
        {DEVICE_META.map(({ key, icon }) => {
          const device = doc.devices[key]
          const connected = device.connected
          const category =
            key === "smartPlug" ? "smart_plug" : key === "lights" ? "lights" : "thermostat"
          const presentation = deviceRowPresentation(category, doc.devices)
          const isOpen = expanded === key

          return (
            <ConnectionDeviceRow
              key={key}
              icon={icon}
              eyebrow={presentation.eyebrow}
              headline={presentation.headline}
              detail={presentation.detail}
              connected={connected}
              testLabel={key === "smartPlug" ? "Test plug" : key === "lights" ? "Test lights" : "Test"}
              expanded={isOpen}
              onToggleSetup={() => setExpanded(isOpen ? null : key)}
              onDisconnect={connected ? () => void handleDisconnect(key) : undefined}
              disconnecting={disconnecting === key}
              onTest={
                connected && key === "smartPlug" && canConnectCategory("smart_plug", doc.devices)
                  ? () => void handleTestPlug()
                  : undefined
              }
              testing={testing === "smartPlug"}
            >
              {key === "smartPlug" ? (
                <ConnectionSetupPanel
                  categoryLabel="Plug"
                  guides={SMART_PLUG_GUIDES}
                  guide={plugGuide}
                  brand={doc.devices.smartPlug.brand}
                  onBrandChange={(v) =>
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
                  fields={plugFields(doc.devices.smartPlug.brand)}
                  values={doc.devices.smartPlug as unknown as Record<string, unknown>}
                  onFieldChange={(fieldKey, value) =>
                    patchDoc((d) => ({
                      ...d,
                      devices: {
                        ...d.devices,
                        smartPlug: {
                          ...d.devices.smartPlug,
                          [fieldKey]: fieldKey === "targetHeatF" ? Number(value) || 70 : value,
                          connected: false,
                        },
                      },
                    }))
                  }
                  canConnect={canConnectCategory("smart_plug", doc.devices)}
                  connecting={testing === "smartPlug"}
                  onConnect={() => void handleConnectPlug()}
                  connectLabel={connected ? "Test plug again" : "Connect plug"}
                />
              ) : null}

              {key === "lights" ? (
                <ConnectionSetupPanel
                  categoryLabel="Lights"
                  guides={LIGHTS_GUIDES}
                  guide={getGuide("lights", doc.devices.lights.brand)}
                  brand={doc.devices.lights.brand}
                  onBrandChange={(v) =>
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
                  fields={lightsFields(doc.devices.lights.brand)}
                  values={doc.devices.lights as unknown as Record<string, unknown>}
                  onFieldChange={(fieldKey, value) =>
                    patchDoc((d) => ({
                      ...d,
                      devices: {
                        ...d.devices,
                        lights: { ...d.devices.lights, [fieldKey]: value, connected: false },
                      },
                    }))
                  }
                  canConnect={canConnectCategory("lights", doc.devices)}
                  connecting={testing === "lights"}
                  onConnect={() => void handleConnectLights()}
                  connectLabel={connected ? "Test lights" : "Connect lights"}
                />
              ) : null}

              {key === "thermostat" ? (
                <ConnectionSetupPanel
                  categoryLabel="Thermostat"
                  guides={THERMOSTAT_GUIDES}
                  guide={getGuide("thermostat", doc.devices.thermostat.brand)}
                  brand={doc.devices.thermostat.brand}
                  onBrandChange={(v) =>
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
                  fields={thermostatFields(doc.devices.thermostat.brand)}
                  values={doc.devices.thermostat as unknown as Record<string, unknown>}
                  onFieldChange={(fieldKey, value) =>
                    patchDoc((d) => ({
                      ...d,
                      devices: {
                        ...d.devices,
                        thermostat: {
                          ...d.devices.thermostat,
                          [fieldKey]: fieldKey === "targetHeatF" ? Number(value) || 70 : value,
                          connected: false,
                        },
                      },
                    }))
                  }
                  canConnect={canConnectCategory("thermostat", doc.devices)}
                  connecting={testing === "thermostat"}
                  onConnect={() => void handleConnectThermostat()}
                  connectLabel={connected ? "Test thermostat" : "Connect thermostat"}
                />
              ) : null}
            </ConnectionDeviceRow>
          )
        })}
      </div>

      <HavenAccountBar />

      {dirty ? (
        <div className={cn(roomosUi.prefsStickyBar, "sticky bottom-4 flex justify-end px-4 py-3")}>
          <button
            type="button"
            disabled={saveMutation.isPending}
            onClick={() => saveMutation.mutate(doc)}
            className={cn("rounded-lg px-4 py-2 text-[13px] font-semibold", roomosUi.havenPrimaryBtn)}
          >
            Save draft
          </button>
        </div>
      ) : null}
    </div>
  )
}
