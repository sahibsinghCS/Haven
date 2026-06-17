import { isSupabaseAuthEnabled } from "@/lib/supabase/env"

/**
 * Marketing → app entry URL. When Supabase auth is configured, routes through login.
 */
export function havenAppHref(path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`
  if (!isSupabaseAuthEnabled()) {
    return normalized
  }
  const q = normalized.indexOf("?")
  const pathname = q >= 0 ? normalized.slice(0, q) : normalized
  const search = q >= 0 ? normalized.slice(q) : ""
  return `/login?next=${encodeURIComponent(`${pathname}${search}`)}`
}
