/**
 * Home-Assistant-style camera connection fields.
 *
 * HA patterns mirrored here:
 * - Generic Camera: stream URL + optional credentials (inline in RTSP URL)
 * - ONVIF: LAN discovery, then user enters credentials + profile path
 * - Brand integrations: preset RTSP paths (Hikvision, Reolink, Tapo, …)
 */

export type CameraConnectionType = "scan" | "phone_ip" | "wifi_rtsp" | "wifi_http"

export interface CameraConnectionTypeOption {
  id: CameraConnectionType
  label: string
  hint: string
}

/** Like HA integration picker — brand selects the default RTSP/HTTP path template. */
export type WifiCameraBrand =
  | "generic_rtsp"
  | "onvif"
  | "hikvision"
  | "reolink"
  | "tapo"
  | "amcrest"
  | "dahua"
  | "generic_http"

export interface WifiCameraBrandOption {
  id: WifiCameraBrand
  label: string
  hint: string
  defaultPort: string
  streamLabel: string
}

export const CAMERA_CONNECTION_TYPES: CameraConnectionTypeOption[] = [
  {
    id: "scan",
    label: "USB webcam or scanned device",
    hint: "Webcams, DroidCam phones, and ONVIF cameras found on your LAN.",
  },
  {
    id: "phone_ip",
    label: "Phone camera (DroidCam Wi‑Fi)",
    hint: "Enter the phone IP from the DroidCam app — same idea as HA Generic Camera with an HTTP stream URL.",
  },
  {
    id: "wifi_rtsp",
    label: "WiFi / IP camera (RTSP)",
    hint: "Reolink, Hikvision, Tapo, ONVIF, and other RTSP cameras — like HA Generic Camera stream source.",
  },
  {
    id: "wifi_http",
    label: "WiFi camera (HTTP / MJPEG)",
    hint: "MJPEG or snapshot URL — like HA Generic Camera still image / HTTP stream.",
  },
]

export const WIFI_CAMERA_BRANDS: WifiCameraBrandOption[] = [
  {
    id: "generic_rtsp",
    label: "Generic RTSP",
    hint: "Paste a path or use rtsp://host:554/… from your camera manual.",
    defaultPort: "554",
    streamLabel: "Stream path",
  },
  {
    id: "onvif",
    label: "ONVIF (discovered or manual)",
    hint: "Use after Rescan finds an ONVIF camera, or enter IP from your router.",
    defaultPort: "554",
    streamLabel: "Profile path (often /onvif1 or from ONVIF tool)",
  },
  {
    id: "hikvision",
    label: "Hikvision",
    hint: "Channel 101 = main, 102 = substream (ISAPI/Streaming).",
    defaultPort: "554",
    streamLabel: "Channel (101 main, 102 sub)",
  },
  {
    id: "reolink",
    label: "Reolink",
    hint: "h264Preview_01_main or _sub — enable RTSP in Reolink app.",
    defaultPort: "554",
    streamLabel: "Stream (main / sub)",
  },
  {
    id: "tapo",
    label: "TP-Link Tapo",
    hint: "Enable RTSP in Tapo app → Advanced → Camera account.",
    defaultPort: "554",
    streamLabel: "Stream (usually stream1)",
  },
  {
    id: "amcrest",
    label: "Amcrest / Dahua-style",
    hint: "cam/realmonitor?channel=1&subtype=0 (main) or subtype=1 (sub).",
    defaultPort: "554",
    streamLabel: "Channel",
  },
  {
    id: "dahua",
    label: "Dahua",
    hint: "Same path pattern as Amcrest NVRs.",
    defaultPort: "554",
    streamLabel: "Channel",
  },
  {
    id: "generic_http",
    label: "Generic HTTP",
    hint: "Full path after host, e.g. /mjpeg or /ISAPI/Streaming/channels/101/picture",
    defaultPort: "80",
    streamLabel: "URL path",
  },
]

export type CameraManualFields = {
  host: string
  port: string
  path: string
  username: string
  password: string
  wifiBrand: WifiCameraBrand
  substream: boolean
  useAdvancedUrl: boolean
  rtspUrl: string
  httpUrl: string
}

export const DEFAULT_PHONE_IP = "192.168.1.10"
export const DEFAULT_DROIDCAM_PORT = "4747"

export function defaultManualFields(): CameraManualFields {
  return {
    host: DEFAULT_PHONE_IP,
    port: DEFAULT_DROIDCAM_PORT,
    path: "/video",
    username: "",
    password: "",
    wifiBrand: "generic_rtsp",
    substream: false,
    useAdvancedUrl: false,
    rtspUrl: "",
    httpUrl: "",
  }
}

function normalizeHost(raw: string): string {
  return raw.trim().replace(/^https?:\/\//i, "").split("/")[0]?.split(":")[0] ?? ""
}

function encodeUserinfo(value: string): string {
  return encodeURIComponent(value)
}

/** Build RTSP URL with inline credentials (HA Generic Camera recommendation). */
export function buildRtspStreamUrl(
  brand: WifiCameraBrand,
  fields: Pick<CameraManualFields, "host" | "port" | "path" | "username" | "password" | "substream">,
): string | null {
  const host = normalizeHost(fields.host)
  if (!host) return null

  const port = fields.port.trim() || "554"
  const user = fields.username.trim()
  const pass = fields.password
  const auth =
    user.length > 0
      ? `${encodeUserinfo(user)}${pass ? `:${encodeUserinfo(pass)}` : ""}@`
      : ""

  let path = fields.path.trim()
  switch (brand) {
    case "hikvision": {
      const ch = path || (fields.substream ? "102" : "101")
      path = `/Streaming/Channels/${ch}`
      break
    }
    case "reolink":
      path = path || (fields.substream ? "/h264Preview_01_sub" : "/h264Preview_01_main")
      break
    case "tapo":
      path = path || "/stream1"
      break
    case "amcrest":
    case "dahua": {
      const ch = path.replace(/\D/g, "") || "1"
      const sub = fields.substream ? "1" : "0"
      path = `/cam/realmonitor?channel=${ch}&subtype=${sub}`
      break
    }
    case "onvif":
      path = path || "/onvif1"
      break
    default:
      path = path || "/"
  }

  if (!path.startsWith("/")) path = `/${path}`
  return `rtsp://${auth}${host}:${port}${path}`
}

export function buildHttpStreamUrl(
  brand: WifiCameraBrand,
  fields: Pick<CameraManualFields, "host" | "port" | "path" | "username" | "password">,
): string | null {
  const host = normalizeHost(fields.host)
  if (!host) return null

  const port = fields.port.trim() || "80"
  const user = fields.username.trim()
  const pass = fields.password

  let path = fields.path.trim()
  if (brand === "hikvision") {
    const ch = path.replace(/\D/g, "") || "101"
    path = `/ISAPI/Streaming/channels/${ch}/picture`
  } else {
    path = path || "/mjpeg"
  }
  if (!path.startsWith("/")) path = `/${path}`

  const portSuffix = port === "80" ? "" : `:${port}`
  const base = `http://${host}${portSuffix}${path}`
  if (!user) return base
  try {
    const u = new URL(base)
    u.username = user
    if (pass) u.password = pass
    return u.toString()
  } catch {
    return base
  }
}

export function buildCameraSource(
  type: CameraConnectionType,
  fields: CameraManualFields,
  scannedValue: string | null,
): { source: number | string; backend: string } | null {
  if (type === "scan") {
    if (!scannedValue) return null
    const [sourceRaw, backend] = scannedValue.split("::")
    const source =
      sourceRaw !== undefined && /^\d+$/.test(sourceRaw) ? Number(sourceRaw) : sourceRaw
    return { source: source ?? 0, backend: backend || "auto" }
  }

  if (type === "phone_ip") {
    const host = normalizeHost(fields.host)
    if (!host) return null
    const port = fields.port.trim() || DEFAULT_DROIDCAM_PORT
    const path = fields.path.trim() || "/video"
    const pathNorm = path.startsWith("/") ? path : `/${path}`
    return { source: `http://${host}:${port}${pathNorm}`, backend: "auto" }
  }

  if (type === "wifi_rtsp") {
    if (fields.useAdvancedUrl && fields.rtspUrl.trim()) {
      return { source: fields.rtspUrl.trim(), backend: "auto" }
    }
    const url = buildRtspStreamUrl(fields.wifiBrand, fields)
    return url ? { source: url, backend: "auto" } : null
  }

  if (fields.useAdvancedUrl && fields.httpUrl.trim()) {
    return { source: fields.httpUrl.trim(), backend: "auto" }
  }
  const url = buildHttpStreamUrl(
    fields.wifiBrand === "generic_http" ? "generic_http" : fields.wifiBrand,
    fields,
  )
  return url ? { source: url, backend: "auto" } : null
}

export function inferConnectionType(source: number | string): CameraConnectionType {
  if (typeof source === "number" || /^\d+$/.test(String(source))) {
    return "scan"
  }
  const s = String(source)
  if (s === "droidcam:auto" || s === "auto") {
    return "scan"
  }
  if (s.startsWith("rtsp://")) {
    return "wifi_rtsp"
  }
  if (isDroidcamHttpUrl(s)) {
    return "phone_ip"
  }
  if (s.startsWith("http://") || s.startsWith("https://")) {
    return "wifi_http"
  }
  return "scan"
}

function isDroidcamHttpUrl(url: string): boolean {
  try {
    const u = new URL(url)
    return u.port === "4747" || u.port === "4848" || u.pathname.endsWith("/video")
  } catch {
    return false
  }
}

function inferWifiBrandFromRtsp(url: string): WifiCameraBrand {
  const lower = url.toLowerCase()
  if (lower.includes("/streaming/channels/")) return "hikvision"
  if (lower.includes("h264preview")) return "reolink"
  if (lower.includes("/stream1")) return "tapo"
  if (lower.includes("realmonitor")) return "amcrest"
  if (lower.includes("onvif")) return "onvif"
  return "generic_rtsp"
}

export function manualFieldsFromSource(source: number | string): CameraManualFields {
  const base = defaultManualFields()
  if (typeof source === "number" || /^\d+$/.test(String(source))) {
    return base
  }
  const s = String(source)
  if (s.startsWith("rtsp://")) {
    try {
      const u = new URL(s)
      return {
        ...base,
        wifiBrand: inferWifiBrandFromRtsp(s),
        host: u.hostname,
        port: u.port || "554",
        path: u.pathname + u.search,
        username: u.username ? decodeURIComponent(u.username) : "",
        password: u.password ? decodeURIComponent(u.password) : "",
        rtspUrl: s,
        useAdvancedUrl: true,
      }
    } catch {
      return { ...base, rtspUrl: s, useAdvancedUrl: true }
    }
  }
  if (s.startsWith("http://") || s.startsWith("https://")) {
    if (isDroidcamHttpUrl(s)) {
      try {
        const u = new URL(s)
        return {
          ...base,
          host: u.hostname,
          port: u.port || DEFAULT_DROIDCAM_PORT,
          path: u.pathname || "/video",
        }
      } catch {
        return base
      }
    }
    try {
      const u = new URL(s)
      return {
        ...base,
        wifiBrand: "generic_http",
        host: u.hostname,
        port: u.port || "80",
        path: u.pathname + u.search,
        username: u.username ? decodeURIComponent(u.username) : "",
        password: u.password ? decodeURIComponent(u.password) : "",
        httpUrl: s,
        useAdvancedUrl: true,
      }
    } catch {
      return { ...base, httpUrl: s, useAdvancedUrl: true }
    }
  }
  return base
}

export function wifiBrandOption(brand: WifiCameraBrand): WifiCameraBrandOption {
  return WIFI_CAMERA_BRANDS.find((b) => b.id === brand) ?? WIFI_CAMERA_BRANDS[0]!
}

export function cameraValueKey(source: number | string, backend: string): string {
  return `${source}::${backend}`
}
