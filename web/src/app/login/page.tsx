"use client"

import { Suspense, useState } from "react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { toast } from "sonner"

import { useHavenAuth } from "@/components/auth/haven-auth-provider"
import { isSupabaseAuthEnabled } from "@/lib/supabase/client"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
function LoginForm() {
  const { signIn, signUp } = useHavenAuth()
  const router = useRouter()
  const searchParams = useSearchParams()
  const next = searchParams.get("next") || "/live"

  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [mode, setMode] = useState<"signin" | "signup">("signin")
  const [busy, setBusy] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    const fn = mode === "signin" ? signIn : signUp
    const { error } = await fn(email.trim(), password)
    setBusy(false)
    if (error) {
      toast.error(error)
      return
    }
    toast.success(mode === "signin" ? "Signed in" : "Account created — you are signed in")
    router.replace(next)
  }

  return (
    <div className="mx-auto flex min-h-full w-full max-w-md flex-col justify-center gap-8 px-6 py-16">
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-[color:var(--haven-faint)]">
          HAVEN
        </p>
        <h1 className="mt-2 font-serif text-[2rem] font-medium tracking-tight text-[color:var(--haven-ink)]">
          {mode === "signin" ? "Sign in" : "Create account"}
        </h1>
        <p className="mt-2 text-[14px] leading-relaxed text-[color:var(--haven-muted)]">
          Your preferences and device connections stay tied to this account across browsers and
          devices.
        </p>
      </div>

      <form onSubmit={submit} className="flex flex-col gap-4">
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            autoComplete={mode === "signin" ? "current-password" : "new-password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={6}
            required
          />
        </div>
        <Button type="submit" disabled={busy} className="w-full">
          {busy ? "Please wait…" : mode === "signin" ? "Sign in" : "Create account"}
        </Button>
      </form>

      <p className="text-center text-[13px] text-[color:var(--haven-muted)]">
        {mode === "signin" ? (
          <>
            New here?{" "}
            <button
              type="button"
              className="font-semibold text-teal-800 underline-offset-2 hover:underline"
              onClick={() => setMode("signup")}
            >
              Create an account
            </button>
          </>
        ) : (
          <>
            Already have an account?{" "}
            <button
              type="button"
              className="font-semibold text-teal-800 underline-offset-2 hover:underline"
              onClick={() => setMode("signin")}
            >
              Sign in
            </button>
          </>
        )}
      </p>
    </div>
  )
}

export default function LoginPage() {
  if (!isSupabaseAuthEnabled()) {
    return (
      <div className="mx-auto flex min-h-full max-w-md flex-col justify-center gap-4 px-6 py-16">
        <h1 className="font-serif text-2xl font-medium">Sign in</h1>
        <p className="text-[14px] leading-relaxed text-[color:var(--haven-muted)]">
          Add Supabase env vars to <span className="font-mono text-[12px]">web/.env.local</span> (see{" "}
          <span className="font-mono text-[12px]">web/.env.local.example</span>).
        </p>
        <Button asChild variant="outline">
          <Link href="/live">Continue without account</Link>
        </Button>
      </div>
    )
  }

  return (
    <Suspense
      fallback={
        <div className="flex min-h-full items-center justify-center text-[14px] text-[color:var(--haven-muted)]">
          Loading…
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  )
}
