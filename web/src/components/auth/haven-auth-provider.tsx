"use client"

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react"
import type { Session, User } from "@supabase/supabase-js"

import { createSupabaseBrowserClient, isSupabaseAuthEnabled } from "@/lib/supabase/client"
import { refreshHavenAccessToken, setHavenAccessToken } from "@/lib/roomos/haven-auth"

type HavenAuthContextValue = {
  enabled: boolean
  loading: boolean
  session: Session | null
  user: User | null
  signIn: (email: string, password: string) => Promise<{ error: string | null }>
  signUp: (email: string, password: string) => Promise<{ error: string | null }>
  signOut: () => Promise<void>
}

const HavenAuthContext = createContext<HavenAuthContextValue | null>(null)

export function HavenAuthProvider({ children }: { children: ReactNode }) {
  const enabled = isSupabaseAuthEnabled()
  const [loading, setLoading] = useState(enabled)
  const [session, setSession] = useState<Session | null>(null)

  const supabase = useMemo(() => (enabled ? createSupabaseBrowserClient() : null), [enabled])

  useEffect(() => {
    if (!supabase) {
      setLoading(false)
      return
    }

    let mounted = true

    supabase.auth.getSession().then(({ data }) => {
      if (!mounted) return
      setSession(data.session)
      setHavenAccessToken(data.session?.access_token ?? null)
      setLoading(false)
    })

    const { data: sub } = supabase.auth.onAuthStateChange((_event, next) => {
      setSession(next)
      setHavenAccessToken(next?.access_token ?? null)
      setLoading(false)
    })

    return () => {
      mounted = false
      sub.subscription.unsubscribe()
    }
  }, [supabase])

  const signIn = useCallback(
    async (email: string, password: string) => {
      if (!supabase) return { error: "Auth is not configured" }
      const { error } = await supabase.auth.signInWithPassword({ email, password })
      if (!error) await refreshHavenAccessToken()
      return { error: error?.message ?? null }
    },
    [supabase],
  )

  const signUp = useCallback(
    async (email: string, password: string) => {
      if (!supabase) return { error: "Auth is not configured" }
      const { error } = await supabase.auth.signUp({ email, password })
      if (!error) await refreshHavenAccessToken()
      return { error: error?.message ?? null }
    },
    [supabase],
  )

  const signOut = useCallback(async () => {
    if (supabase) await supabase.auth.signOut()
    setSession(null)
    setHavenAccessToken(null)
  }, [supabase])

  const value = useMemo<HavenAuthContextValue>(
    () => ({
      enabled,
      loading,
      session,
      user: session?.user ?? null,
      signIn,
      signUp,
      signOut,
    }),
    [enabled, loading, session, signIn, signUp, signOut],
  )

  return <HavenAuthContext.Provider value={value}>{children}</HavenAuthContext.Provider>
}

export function useHavenAuth() {
  const ctx = useContext(HavenAuthContext)
  if (!ctx) throw new Error("useHavenAuth must be used within HavenAuthProvider")
  return ctx
}
