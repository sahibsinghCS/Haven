export type SupabasePublicConfig = {
  url: string
  anonKey: string
}

/** Read Supabase URL + anon key from Next env (works in Server and Client Components). */
export function getSupabasePublicConfig(): SupabasePublicConfig | null {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL?.trim()
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY?.trim()
  if (!url || !anonKey) return null
  return { url, anonKey }
}

export function isSupabaseAuthEnabled(): boolean {
  return getSupabasePublicConfig() !== null
}
