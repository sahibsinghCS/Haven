import {
  createSupabaseBrowserClient,
  getSupabasePublicConfig,
  isSupabaseAuthEnabled,
} from "@/lib/supabase/client"
import { getHavenRoomId } from "@/lib/roomos/haven-room"

export { isSupabaseAuthEnabled }

let browserClient: ReturnType<typeof createSupabaseBrowserClient> | null = null

function getBrowserClient() {
  if (!isSupabaseAuthEnabled()) return null
  if (!browserClient) {
    browserClient = createSupabaseBrowserClient()
  }
  return browserClient
}

export async function refreshHavenAccessToken(): Promise<string | null> {
  const client = getBrowserClient()
  if (!client) return null
  try {
    const { data } = await client.auth.getSession()
    return data.session?.access_token ?? null
  } catch {
    return null
  }
}

export async function havenRequestHeaders(extra?: HeadersInit): Promise<HeadersInit> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Haven-Room-Id": getHavenRoomId(),
  }

  const client = getBrowserClient()
  if (client) {
    const { data } = await client.auth.getSession()
    const token = data.session?.access_token
    if (token) {
      headers.Authorization = `Bearer ${token}`
    }
  }

  return { ...headers, ...extra }
}

/** @deprecated Use async havenRequestHeaders() */
export function setHavenAccessToken(_token: string | null) {
 /* no-op. session cookies are the source of truth */
}

/** @deprecated Use async havenRequestHeaders() */
export function getHavenAccessToken(): string | null {
  return null
}

export function resetHavenAuthClient() {
  browserClient = null
}

export function getSupabaseConfigFromEnv() {
  return getSupabasePublicConfig()
}
