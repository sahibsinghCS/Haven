import { createSupabaseBrowserClient, isSupabaseAuthEnabled } from "@/lib/supabase/client"

let accessToken: string | null = null

export { isSupabaseAuthEnabled }

export function setHavenAccessToken(token: string | null) {
  accessToken = token?.trim() || null
}

export function getHavenAccessToken(): string | null {
  return accessToken
}

export async function refreshHavenAccessToken(): Promise<string | null> {
  if (!isSupabaseAuthEnabled()) return null
  try {
    const supabase = createSupabaseBrowserClient()
    const { data } = await supabase.auth.getSession()
    const token = data.session?.access_token ?? null
    setHavenAccessToken(token)
    return token
  } catch {
    return null
  }
}

export function havenRequestHeaders(extra?: HeadersInit): HeadersInit {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  }
  const token = getHavenAccessToken()
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }
  return { ...headers, ...extra }
}
