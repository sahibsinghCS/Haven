import { createBrowserClient } from "@supabase/ssr"

import {
  getSupabasePublicConfig,
  isSupabaseAuthEnabled,
  type SupabasePublicConfig,
} from "@/lib/supabase/env"

export { getSupabasePublicConfig, isSupabaseAuthEnabled, type SupabasePublicConfig }

export function createSupabaseBrowserClient(config?: SupabasePublicConfig | null) {
  const resolved = config ?? getSupabasePublicConfig()
  if (!resolved) {
    throw new Error("Missing NEXT_PUBLIC_SUPABASE_URL or NEXT_PUBLIC_SUPABASE_ANON_KEY")
  }
  return createBrowserClient(resolved.url, resolved.anonKey)
}
