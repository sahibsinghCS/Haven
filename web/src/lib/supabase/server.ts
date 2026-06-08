import { createServerClient } from "@supabase/ssr"
import { cookies } from "next/headers"
import type { User } from "@supabase/supabase-js"

import { getSupabasePublicConfig } from "@/lib/supabase/env"

export async function createSupabaseServerClient() {
  const config = getSupabasePublicConfig()
  if (!config) {
    throw new Error("Missing Supabase env vars")
  }
  const { url, anonKey: key } = config

  const cookieStore = await cookies()

  return createServerClient(url, key, {
    cookies: {
      getAll() {
        return cookieStore.getAll()
      },
      setAll(cookiesToSet) {
        try {
          cookiesToSet.forEach(({ name, value, options }) => {
            cookieStore.set(name, value, options)
          })
        } catch {
          /* Server Component — ignore */
        }
      },
    },
  })
}

export async function getSupabaseUser(): Promise<User | null> {
  const config = getSupabasePublicConfig()
  if (!config) return null
  try {
    const supabase = await createSupabaseServerClient()
    const {
      data: { user },
    } = await supabase.auth.getUser()
    return user
  } catch {
    return null
  }
}
