"use client"

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react"
import type { Session, User } from "@supabase/supabase-js"

import {
  createSupabaseBrowserClient,
  getSupabasePublicConfig,
  type SupabasePublicConfig,
} from "@/lib/supabase/client"
import { resetHavenAuthClient } from "@/lib/roomos/haven-auth"

type HavenAuthContextValue = {
  enabled: boolean
  loading: boolean
  session: Session | null
  user: User | null
}

const HavenAuthContext = createContext<HavenAuthContextValue | null>(null)

export function HavenAuthProvider({
  children,
  supabase: supabaseConfig,
}: {
  children: ReactNode
  supabase?: SupabasePublicConfig | null
}) {
  const config = useMemo(
    () => supabaseConfig ?? getSupabasePublicConfig(),
    [supabaseConfig],
  )
  const enabled = config !== null
  const [loading, setLoading] = useState(enabled)
  const [session, setSession] = useState<Session | null>(null)

  const supabase = useMemo(() => {
    if (!config) return null
    resetHavenAuthClient()
    return createSupabaseBrowserClient(config)
  }, [config])

  useEffect(() => {
    if (!supabase) {
      setLoading(false)
      return
    }

    let mounted = true

    supabase.auth.getSession().then(({ data }) => {
      if (!mounted) return
      setSession(data.session)
      setLoading(false)
    })

    const { data: sub } = supabase.auth.onAuthStateChange((_event, next) => {
      setSession(next)
      setLoading(false)
    })

    return () => {
      mounted = false
      sub.subscription.unsubscribe()
    }
  }, [supabase])

  const value = useMemo<HavenAuthContextValue>(
    () => ({
      enabled,
      loading,
      session,
      user: session?.user ?? null,
    }),
    [enabled, loading, session],
  )

  return <HavenAuthContext.Provider value={value}>{children}</HavenAuthContext.Provider>
}

export function useHavenAuth() {
  const ctx = useContext(HavenAuthContext)
  if (!ctx) throw new Error("useHavenAuth must be used within HavenAuthProvider")
  return ctx
}
