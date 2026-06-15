"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Lightbulb, Plug, Plus, Radar, Thermometer } from "lucide-react"
import { toast } from "sonner"

import { useHavenAuth } from "@/components/auth/haven-auth-provider"
import { ConnectionDeviceRow } from "@/components/roomos/connections/connection-device-row"
import { ConnectionSetupPanel } from "@/components/roomos/connections/connection-setup-panel"
import { HavenAccountBar } from "@/components/roomos/haven-account-bar"
import { HavenOfflineBanner } from "@/components/roomos/haven-offline-banner"
import { PreferencesSkeleton } from "@/components/roomos/roomos-loading-states"
import { HavenSetupWizard } from "@/components/roomos/setup/haven-setup-wizard"
import { isSetupMarkedComplete } from "@/lib/roomos/setup-session"
import {
  discoverDevices,
  fetchDeviceSettingsDocument,
  fetchSmartPlugStatus,
  saveDeviceSettingsDocument,
  testLights,
  testSmartPlug,
  testThermostat,
  type DiscoveredDevice,
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
import {
  countConnectedDevices,
  defaultDeviceSettingsDocument,
  defaultLightsDevice,
  defaultSmartPlugDevice,
  defaultThermostatDevice,
} from "@/lib/roomos/device-settings-schema"
import { loadDeviceSettingsLocal, saveDeviceSettingsLocal } from "@/lib/roomos/device-settings-persistence"
import {
  getGuide,
  LIGHTS_GUIDES,
  SMART_PLUG_GUIDES,
  THERMOSTAT_GUIDES,
} from "@/lib/roomos/device-setup-guides"
import { roomosUi } from "@/lib/roomos/roomos-ui"
import type {
  DeviceCategoryKey,
  DeviceSettingsDocument,
  LightsBrand,
  LightsDevice,
  SmartPlugBrand,
  SmartPlugDevice,
  ThermostatBrand,
  ThermostatDevice,
} from "@/types/device-settings"
import { cn } from "@/lib/utils"

const DISCOVERY_BRAND_LABEL: Record<string, string> = {
  tapo: "TP-Link Tapo",
  tplink_kasa: "TP-Link Kasa",
  kasa_light: "Kasa / Tapo bulb",
  shelly: "Shelly",
  wemo: "Belkin Wemo",
  wiz: "WiZ",
  yeelight: "Yeelight",
  lifx: "LIFX",
  philips_hue: "Philips Hue",
  nanoleaf: "Nanoleaf",
  govee: "Govee",
}

type CategoryConfig = {
  arrayKey: DeviceCategoryKey
  category: "smart_plug" | "lights" | "thermostat"
  title: string
  addLabel: string
  icon: typeof Plug
}

const CATEGORIES: CategoryConfig[] = [
  { arrayKey: "smartPlugs", category: "smart_plug", title: "Smart plug", addLabel: "Add smart plug", icon: Plug },
  { arrayKey: "lights", category: "lights", title: "Lights", addLabel: "Add lights", icon: Lightbulb },
  { arrayKey: "thermostats", category: "thermostat", title: "Thermostat", addLabel: "Add thermostat", icon: Thermometer },
]

export function ConnectionsPageClient() {
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState<DeviceSettingsDocument | null>(null)
  const [dirty, setDirty] = useState(false)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [testingId, setTestingId] = useState<string | null>(null)
  const [plugTestAction, setPlugTestAction] = useState<"on" | "off" | null>(null)
  const [disconnectingId, setDisconnectingId] = useState<string | null>(null)
  const [removingId, setRemovingId] = useState<string | null>(null)
  const [scanning, setScanning] = useState(false)
  const [scanned, setScanned] = useState<DiscoveredDevice[] | null>(null)
  const [plugPowerState, setPlugPowerState] = useState<Record<string, "on" | "off">>({})
  const [readingPlugId, setReadingPlugId] = useState<string | null>(null)
  const [showSetupWizard, setShowSetupWizard] = useState(() => !isSetupMarkedComplete())
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
  const apiOnline = docQuery.data?.apiOnline ?? true

  const refreshPlugPower = useCallback(
    async (plug: SmartPlugDevice) => {
      if (!plug.connected || !canConnectCategory("smart_plug", plug)) return
      setReadingPlugId(plug.id)
      try {
        const brand = resolveSmartPlugBrand(plug)
        const result = await fetchSmartPlugStatus({
          device_id: plug.id,
          brand,
          host: plug.host,
        })
        if (result.state === "on" || result.state === "off") {
          setPlugPowerState((prev) => ({ ...prev, [plug.id]: result.state! }))
        }
      } catch {
        /* keep last known state */
      } finally {
        setReadingPlugId((current) => (current === plug.id ? null : current))
      }
    },
    [],
  )

  const connectedPlugKey = useMemo(
    () =>
      doc?.devices.smartPlugs
        .filter((p) => p.connected && canConnectCategory("smart_plug", p))
        .map((p) => p.id)
        .join(",") ?? "",
    [doc?.devices.smartPlugs],
  )

  useEffect(() => {
    if (!doc || !apiOnline || dirty) return
    for (const plug of doc.devices.smartPlugs) {
      if (plug.connected && canConnectCategory("smart_plug", plug)) {
        void refreshPlugPower(plug)
      }
    }
  }, [connectedPlugKey, apiOnline, dirty, doc, refreshPlugPower])

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

  const updateDevice = useCallback(
    (
      arrayKey: DeviceCategoryKey,
      deviceId: string,
      updater: (device: SmartPlugDevice | LightsDevice | ThermostatDevice) => SmartPlugDevice | LightsDevice | ThermostatDevice,
    ) => {
      patchDoc((d) => ({
        ...d,
        devices: {
          ...d.devices,
          [arrayKey]: d.devices[arrayKey].map((item) =>
            item.id === deviceId ? updater(item) : item,
          ),
        },
      }))
    },
    [patchDoc],
  )

  const addDevice = (arrayKey: DeviceCategoryKey) => {
    const created =
      arrayKey === "smartPlugs"
        ? defaultSmartPlugDevice()
        : arrayKey === "lights"
          ? defaultLightsDevice()
          : defaultThermostatDevice()
    patchDoc((d) => ({
      ...d,
      devices: {
        ...d.devices,
        [arrayKey]: [...d.devices[arrayKey], created],
      },
    }))
    setExpandedId(created.id)
  }

  const handleRemove = async (arrayKey: DeviceCategoryKey, deviceId: string) => {
    if (!doc) return
    setRemovingId(deviceId)
    try {
      const next: DeviceSettingsDocument = {
        ...doc,
        devices: {
          ...doc.devices,
          [arrayKey]: doc.devices[arrayKey].filter((item) => item.id !== deviceId),
        },
      }
      await persistDoc(next)
      if (arrayKey === "smartPlugs") {
        setPlugPowerState((prev) => {
          const copy = { ...prev }
          delete copy[deviceId]
          return copy
        })
      }
      if (expandedId === deviceId) setExpandedId(null)
      toast.success("Device removed")
    } catch {
      toast.error("Could not remove device")
    } finally {
      setRemovingId(null)
    }
  }

  const handleDisconnect = async (arrayKey: DeviceCategoryKey, deviceId: string) => {
    if (!doc) return
    setDisconnectingId(deviceId)
    try {
      const next: DeviceSettingsDocument = {
        ...doc,
        devices: {
          ...doc.devices,
          [arrayKey]: doc.devices[arrayKey].map((item) =>
            item.id === deviceId ? { ...item, connected: false, enabled: false } : item,
          ),
        },
      }
      await persistDoc(next)
      setPlugPowerState((prev) => {
        const copy = { ...prev }
        delete copy[deviceId]
        return copy
      })
      toast.success("Disconnected")
      if (expandedId === deviceId) setExpandedId(null)
    } catch {
      toast.error("Could not disconnect")
    } finally {
      setDisconnectingId(null)
    }
  }

  const handleScan = async () => {
    setScanning(true)
    try {
      const devices = await discoverDevices({ timeout: 8 })
      setScanned(devices)
      if (devices.length === 0) {
        toast.message("Scan complete — no devices found", {
          description: "Make sure devices are powered on and on the same Wi-Fi.",
        })
      } else {
        toast.success(`Found ${devices.length} device${devices.length === 1 ? "" : "s"}.`)
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Network scan failed")
    } finally {
      setScanning(false)
    }
  }

  const applyDiscovered = (device: DiscoveredDevice) => {
    if (device.category === "smart_plug") {
      const created: SmartPlugDevice = {
        ...defaultSmartPlugDevice(),
        brand: device.brand as SmartPlugBrand,
        host: device.host,
        label: device.name || "",
        connected: false,
        enabled: true,
      }
      patchDoc((d) => ({
        ...d,
        devices: { ...d.devices, smartPlugs: [...d.devices.smartPlugs, created] },
      }))
      setExpandedId(created.id)
    } else {
      const created: LightsDevice = {
        ...defaultLightsDevice(),
        brand: device.brand as LightsBrand,
        host: device.host,
        label: device.name || "",
        connected: false,
        enabled: true,
      }
      patchDoc((d) => ({
        ...d,
        devices: { ...d.devices, lights: [...d.devices.lights, created] },
      }))
      setExpandedId(created.id)
    }
    toast.message(`Added ${device.name || device.brand} (${device.host})`, {
      description: "Review the fields, then Connect.",
    })
  }

  const handlePlugPower = async (plug: SmartPlugDevice, state: "on" | "off") => {
    if (!doc) return
    const err = validatePlugConnect(plug)
    if (err) {
      toast.error(err)
      return
    }
    setTestingId(plug.id)
    setPlugTestAction(state)
    try {
      const { apiOnline } = await persistDoc(doc)
      if (!apiOnline) {
        toast.error("Start HAVEN API (npm run demo), then try again.")
        return
      }
      const brand = resolveSmartPlugBrand(plug)
      await testSmartPlug({ device_id: plug.id, brand, host: plug.host, state })
      void refreshPlugPower(plug)
      toast.success(state === "on" ? "Plug turned on." : "Plug turned off.")
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Plug control failed")
    } finally {
      setTestingId(null)
      setPlugTestAction(null)
    }
  }

  const handleConnectPlug = async (plug: SmartPlugDevice) => {
    if (!doc) return
    const err = validatePlugConnect(plug)
    if (err) {
      toast.error(err)
      return
    }
    if (plug.connected) {
      await handlePlugPower(plug, "on")
      return
    }
    setTestingId(plug.id)
    try {
      const { saved, apiOnline } = await persistDoc(doc)
      if (!apiOnline) {
        toast.error("Start HAVEN API (npm run demo), then try again.")
        return
      }
      const savedPlug = saved.devices.smartPlugs.find((p) => p.id === plug.id) ?? plug
      const brand = resolveSmartPlugBrand(savedPlug)
      await testSmartPlug({ device_id: savedPlug.id, brand, host: savedPlug.host, state: "on" })
      const connected: DeviceSettingsDocument = {
        ...saved,
        devices: {
          ...saved.devices,
          smartPlugs: saved.devices.smartPlugs.map((p) =>
            p.id === plug.id ? { ...p, brand, connected: true, enabled: true } : p,
          ),
        },
      }
      await persistDoc(connected)
      void refreshPlugPower({ ...savedPlug, connected: true, enabled: true })
      toast.success("Smart plug connected — you should have heard a click.")
      setExpandedId(null)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Connect failed")
    } finally {
      setTestingId(null)
    }
  }

  const handleConnectLights = async (lights: LightsDevice) => {
    if (!doc) return
    const err = validateLightsConnect(lights)
    if (err) {
      toast.error(err)
      return
    }
    setTestingId(lights.id)
    try {
      const { saved, apiOnline } = await persistDoc(doc)
      if (!apiOnline) {
        toast.error("Start HAVEN API (npm run demo), then try again.")
        return
      }
      await testLights({ device_id: lights.id, brightness: 60, light_color_hex: "#E8F4FF" })
      const connected: DeviceSettingsDocument = {
        ...saved,
        devices: {
          ...saved.devices,
          lights: saved.devices.lights.map((l) =>
            l.id === lights.id ? { ...l, connected: true, enabled: true } : l,
          ),
        },
      }
      await persistDoc(connected)
      toast.success("Lights connected")
      setExpandedId(null)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Connect failed")
    } finally {
      setTestingId(null)
    }
  }

  const handleConnectThermostat = async (thermo: ThermostatDevice) => {
    if (!doc) return
    const err = validateThermostatConnect(thermo)
    if (err) {
      toast.error(err)
      return
    }
    setTestingId(thermo.id)
    try {
      const { saved, apiOnline } = await persistDoc(doc)
      if (!apiOnline) {
        toast.error("Start HAVEN API (npm run demo), then try again.")
        return
      }
      const savedThermo = saved.devices.thermostats.find((t) => t.id === thermo.id) ?? thermo
      await testThermostat({
        device_id: savedThermo.id,
        heat_f: savedThermo.targetHeatF ?? 70,
        cool_f: savedThermo.targetCoolF,
      })
      const connected: DeviceSettingsDocument = {
        ...saved,
        devices: {
          ...saved.devices,
          thermostats: saved.devices.thermostats.map((t) =>
            t.id === thermo.id ? { ...t, connected: true, enabled: true } : t,
          ),
        },
      }
      await persistDoc(connected)
      toast.success("Thermostat connected")
      setExpandedId(null)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Connect failed")
    } finally {
      setTestingId(null)
    }
  }

  const connectionCounts = useMemo(
    () => (doc ? countConnectedDevices(doc) : { connected: 0, total: 0 }),
    [doc],
  )

  if (docQuery.isPending || !doc) {
    return <PreferencesSkeleton />
  }

  const authRequired = docQuery.data?.authRequired ?? false

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-8 pb-20">
      {authRequired && authEnabled && !session ? (
        <p className={cn(roomosUi.prefsCallout, "border-rose-500/25 bg-rose-50/90 px-4 py-3 text-[13px] text-rose-950")} role="alert">
          Sign in to save connections to your account.
        </p>
      ) : null}

      {!apiOnline && !authRequired ? (
        <HavenOfflineBanner context="connections" />
      ) : null}

      <header className="relative overflow-hidden rounded-[1.5rem] border border-stone-200/80 bg-[linear-gradient(145deg,#fffefb_0%,#f8f4ec_48%,#f0ebe2_100%)] px-6 py-7 shadow-[var(--haven-shadow-card)] sm:px-8 sm:py-9">
        <div className="pointer-events-none absolute -right-8 -top-20 h-48 w-64 rounded-full bg-teal-400/15 blur-3xl" aria-hidden />
        <div className="pointer-events-none absolute -bottom-16 left-8 h-32 w-40 rounded-full bg-amber-200/20 blur-3xl" aria-hidden />
        <p className="relative text-[11px] font-semibold uppercase tracking-[0.28em] text-stone-500">Devices</p>
        <div className="relative mt-2 flex flex-wrap items-end justify-between gap-4">
          <h1 className="font-serif text-[clamp(2rem,4vw,2.85rem)] font-medium tracking-[-0.03em] text-stone-900">
            Connections
          </h1>
          <p
            className={cn(
              "rounded-full border px-3.5 py-1 text-[12px] font-semibold",
              connectionCounts.connected > 0
                ? "border-teal-600/30 bg-teal-50 text-teal-900"
                : "border-stone-300/80 bg-white/80 text-stone-600",
            )}
          >
            {connectionCounts.connected} of {connectionCounts.total} connected
          </p>
        </div>
        <p className="relative mt-3 max-w-xl text-[15px] leading-relaxed text-stone-600">
          Add as many plugs, lights, and thermostats as you need. Name each device whatever you like.
        </p>
      </header>

      {showSetupWizard ? (
        <HavenSetupWizard
          variant="connections"
          onDismiss={() => setShowSetupWizard(false)}
          className="max-w-3xl"
        />
      ) : (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-stone-200/80 bg-white/70 px-4 py-3">
          <p className="text-[13px] text-stone-600">
            New to Haven? Run the guided setup for rooms and cameras.
          </p>
          <button
            type="button"
            onClick={() => setShowSetupWizard(true)}
            className={cn(
              "rounded-lg px-3 py-1.5 text-[12px] font-semibold",
              roomosUi.havenPrimaryBtn,
              "text-white",
            )}
          >
            Open setup wizard
          </button>
        </div>
      )}

      <section className="rounded-[1.25rem] border border-stone-200/80 bg-white/70 px-5 py-5 shadow-[var(--haven-shadow-card)] sm:px-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-serif text-[1.15rem] font-medium tracking-[-0.02em] text-stone-900">Scan my network</h2>
            <p className="mt-1 text-[13px] leading-relaxed text-stone-600">
              Find smart plugs and lights on your Wi-Fi automatically — no typing IP addresses.
            </p>
          </div>
          <button
            type="button"
            onClick={() => void handleScan()}
            disabled={scanning}
            className={cn(
              "inline-flex items-center gap-2 rounded-lg px-4 py-2 text-[13px] font-semibold",
              roomosUi.havenPrimaryBtn,
              scanning && "opacity-70",
            )}
          >
            <Radar className={cn("h-4 w-4", scanning && "animate-spin")} aria-hidden />
            {scanning ? "Scanning…" : "Scan my network"}
          </button>
        </div>

        {scanned && scanned.length > 0 ? (
          <ul className="mt-4 flex flex-col gap-2">
            {scanned.map((device, i) => (
              <li key={`${device.host}-${device.category}-${i}`}>
                <button
                  type="button"
                  onClick={() => applyDiscovered(device)}
                  className="flex w-full items-center justify-between gap-3 rounded-lg border border-stone-200/80 bg-white/80 px-3.5 py-2.5 text-left transition hover:border-teal-600/40 hover:bg-teal-50/50"
                >
                  <span className="flex items-center gap-2.5">
                    {device.category === "lights" ? (
                      <Lightbulb className="h-4 w-4 text-amber-500" aria-hidden />
                    ) : (
                      <Plug className="h-4 w-4 text-teal-700" aria-hidden />
                    )}
                    <span className="flex flex-col">
                      <span className="text-[13.5px] font-medium text-stone-900">
                        {device.name || device.model || DISCOVERY_BRAND_LABEL[device.brand] || device.brand}
                      </span>
                      <span className="font-mono text-[11.5px] text-stone-500">
                        {DISCOVERY_BRAND_LABEL[device.brand] ?? device.brand} · {device.host}
                      </span>
                    </span>
                  </span>
                  <span className="rounded-full border border-stone-300/80 px-2.5 py-0.5 text-[11px] font-semibold text-stone-600">
                    Add
                  </span>
                </button>
              </li>
            ))}
          </ul>
        ) : scanned && scanned.length === 0 ? (
          <p className="mt-4 text-[13px] text-stone-500">
            Nothing found yet. Power-cycle the device, confirm it's on this Wi-Fi, then scan again.
          </p>
        ) : null}
      </section>

      <div className="flex flex-col gap-8">
        {CATEGORIES.map(({ arrayKey, category, title, addLabel, icon: Icon }) => {
          const devices = doc.devices[arrayKey]
          const connectedInCategory = devices.filter((d) => d.connected).length

          return (
            <section key={arrayKey} className="flex flex-col gap-4">
              <div className="flex flex-wrap items-center justify-between gap-3 px-1">
                <div className="flex items-center gap-2.5">
                  <Icon className="size-4 text-stone-500" aria-hidden />
                  <h2 className="text-[13px] font-semibold uppercase tracking-[0.2em] text-stone-600">{title}</h2>
                  <span className="rounded-full bg-stone-100 px-2 py-0.5 text-[11px] font-semibold text-stone-600">
                    {connectedInCategory} connected
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => addDevice(arrayKey)}
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-lg border border-stone-300/90 bg-white/90 px-3 py-1.5 text-[12px] font-semibold text-stone-800 transition hover:border-teal-700/30 hover:bg-teal-50/60",
                  )}
                >
                  <Plus className="size-3.5" aria-hidden />
                  {addLabel}
                </button>
              </div>

              {devices.length === 0 ? (
                <p className="rounded-xl border border-dashed border-stone-300/80 bg-white/50 px-4 py-6 text-center text-[13px] text-stone-500">
                  No {title.toLowerCase()} yet. Click <span className="font-semibold text-stone-700">{addLabel}</span> or scan your network.
                </p>
              ) : (
                devices.map((device) => {
                  const presentation = deviceRowPresentation(category, device)
                  const isOpen = expandedId === device.id
                  const isPlug = arrayKey === "smartPlugs"
                  const plug = isPlug ? (device as SmartPlugDevice) : null

                  return (
                    <ConnectionDeviceRow
                      key={device.id}
                      icon={Icon}
                      eyebrow={presentation.eyebrow}
                      headline={presentation.headline}
                      detail={presentation.detail}
                      connected={device.connected}
                      testLabel={arrayKey === "lights" ? "Test lights" : arrayKey === "thermostats" ? "Test" : "Test plug"}
                      expanded={isOpen}
                      onToggleSetup={() => setExpandedId(isOpen ? null : device.id)}
                      onDisconnect={device.connected ? () => void handleDisconnect(arrayKey, device.id) : undefined}
                      onRemove={() => void handleRemove(arrayKey, device.id)}
                      removing={removingId === device.id}
                      disconnecting={disconnectingId === device.id}
                      onTestOn={
                        plug && device.connected && canConnectCategory("smart_plug", plug)
                          ? () => void handlePlugPower(plug, "on")
                          : undefined
                      }
                      onTestOff={
                        plug && device.connected && canConnectCategory("smart_plug", plug)
                          ? () => void handlePlugPower(plug, "off")
                          : undefined
                      }
                      testing={testingId === device.id}
                      testingAction={plug && testingId === device.id ? plugTestAction : null}
                      powerState={plug ? plugPowerState[plug.id] ?? null : null}
                      readingPower={plug ? readingPlugId === plug.id : false}
                    >
                      {arrayKey === "smartPlugs" && plug ? (
                        <ConnectionSetupPanel
                          categoryLabel="Plug"
                          guides={SMART_PLUG_GUIDES}
                          guide={getGuide("smart_plug", resolveSmartPlugBrand(plug))}
                          brand={plug.brand}
                          onBrandChange={(v) =>
                            updateDevice(arrayKey, device.id, (d) => ({
                              ...(d as SmartPlugDevice),
                              brand: v as SmartPlugBrand,
                              connected: false,
                            }))
                          }
                          fields={plugFields(plug.brand)}
                          values={plug as unknown as Record<string, unknown>}
                          onFieldChange={(fieldKey, value) =>
                            updateDevice(arrayKey, device.id, (d) => ({
                              ...(d as SmartPlugDevice),
                              [fieldKey]: fieldKey === "targetHeatF" ? Number(value) || 70 : value,
                              connected: false,
                            }))
                          }
                          canConnect={canConnectCategory("smart_plug", plug)}
                          connecting={testingId === device.id}
                          onConnect={() => void handleConnectPlug(plug)}
                          connectLabel={plug.connected ? "Turn plug on" : "Connect plug"}
                        />
                      ) : null}

                      {arrayKey === "lights" ? (
                        <ConnectionSetupPanel
                          categoryLabel="Lights"
                          guides={LIGHTS_GUIDES}
                          guide={getGuide("lights", (device as LightsDevice).brand)}
                          brand={(device as LightsDevice).brand}
                          onBrandChange={(v) =>
                            updateDevice(arrayKey, device.id, (d) => ({
                              ...(d as LightsDevice),
                              brand: v as LightsBrand,
                              connected: false,
                            }))
                          }
                          fields={lightsFields((device as LightsDevice).brand)}
                          values={device as unknown as Record<string, unknown>}
                          onFieldChange={(fieldKey, value) =>
                            updateDevice(arrayKey, device.id, (d) => ({
                              ...(d as LightsDevice),
                              [fieldKey]: value,
                              connected: false,
                            }))
                          }
                          canConnect={canConnectCategory("lights", device as LightsDevice)}
                          connecting={testingId === device.id}
                          onConnect={() => void handleConnectLights(device as LightsDevice)}
                          connectLabel={device.connected ? "Test lights" : "Connect lights"}
                        />
                      ) : null}

                      {arrayKey === "thermostats" ? (
                        <ConnectionSetupPanel
                          categoryLabel="Thermostat"
                          guides={THERMOSTAT_GUIDES}
                          guide={getGuide("thermostat", (device as ThermostatDevice).brand)}
                          brand={(device as ThermostatDevice).brand}
                          onBrandChange={(v) =>
                            updateDevice(arrayKey, device.id, (d) => ({
                              ...(d as ThermostatDevice),
                              brand: v as ThermostatBrand,
                              connected: false,
                            }))
                          }
                          fields={thermostatFields((device as ThermostatDevice).brand)}
                          values={device as unknown as Record<string, unknown>}
                          onFieldChange={(fieldKey, value) =>
                            updateDevice(arrayKey, device.id, (d) => ({
                              ...(d as ThermostatDevice),
                              [fieldKey]: fieldKey === "targetHeatF" ? Number(value) || 70 : value,
                              connected: false,
                            }))
                          }
                          canConnect={canConnectCategory("thermostat", device as ThermostatDevice)}
                          connecting={testingId === device.id}
                          onConnect={() => void handleConnectThermostat(device as ThermostatDevice)}
                          connectLabel={device.connected ? "Test thermostat" : "Connect thermostat"}
                        />
                      ) : null}
                    </ConnectionDeviceRow>
                  )
                })
              )}
            </section>
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
