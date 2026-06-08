"use client"

import Link from "next/link"
import { useActionState } from "react"
import { Loader2 } from "lucide-react"

import { signInWithEmail, type AuthActionState } from "@/app/(auth)/actions"
import { AuthAlert } from "@/components/auth/auth-alert"
import { AuthCard } from "@/components/auth/auth-card"
import { AuthFormField, authInputClassName } from "@/components/auth/auth-form-field"
import { PasswordField } from "@/components/auth/password-field"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

const initialState: AuthActionState = {}

export function SignInForm({ next, authError }: { next: string; authError?: string }) {
  const [state, formAction, pending] = useActionState(signInWithEmail, initialState)
  const errorMessage = state.error ?? authError

  return (
    <AuthCard
      title="Sign in"
      description="Your preferences and device connections stay tied to this account."
      footer={
        <p className="text-center text-[13px] text-[color:var(--haven-muted)]">
          New here?{" "}
          <Link
            href={`/login/sign-up${next !== "/live" ? `?next=${encodeURIComponent(next)}` : ""}`}
            className="font-semibold text-teal-800 underline-offset-2 hover:underline"
          >
            Create an account
          </Link>
        </p>
      }
    >
      <form action={formAction} className="flex flex-col gap-4">
        <input type="hidden" name="next" value={next} />
        {errorMessage ? <AuthAlert variant="error">{errorMessage}</AuthAlert> : null}
        <AuthFormField id="email" label="Email" error={state.fieldErrors?.email}>
          <Input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            required
            className={authInputClassName()}
          />
        </AuthFormField>
        <AuthFormField id="password" label="Password" error={state.fieldErrors?.password}>
          <PasswordField id="password" name="password" autoComplete="current-password" />
        </AuthFormField>
        <div className="flex justify-end">
          <Link
            href="/login/forgot-password"
            className="text-[13px] font-medium text-teal-800 underline-offset-2 hover:underline"
          >
            Forgot password?
          </Link>
        </div>
        <Button
          type="submit"
          disabled={pending}
          className="h-11 w-full bg-[color:var(--haven-ink)] text-[color:var(--haven-paper)]"
        >
          {pending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
          {pending ? "Signing in…" : "Sign in"}
        </Button>
      </form>
    </AuthCard>
  )
}
