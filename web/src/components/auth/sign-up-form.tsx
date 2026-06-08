"use client"

import Link from "next/link"
import { useActionState } from "react"
import { Loader2 } from "lucide-react"

import { signUpWithEmail, type AuthActionState } from "@/app/(auth)/actions"
import { AuthAlert } from "@/components/auth/auth-alert"
import { AuthCard } from "@/components/auth/auth-card"
import { AuthFormField, authInputClassName } from "@/components/auth/auth-form-field"
import { PasswordField } from "@/components/auth/password-field"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

const initialState: AuthActionState = {}

export function SignUpForm({ next }: { next: string }) {
  const [state, formAction, pending] = useActionState(signUpWithEmail, initialState)

  if (state.success) {
    return (
      <AuthCard title="Check your email" description={state.success}>
        <AuthAlert variant="success">
          We sent a confirmation link if your email provider accepts messages from Supabase. After
          confirming, return here to sign in.
        </AuthAlert>
        <Button asChild className="mt-6 h-11 w-full bg-[color:var(--haven-ink)] text-[color:var(--haven-paper)]">
          <Link href={`/login${next !== "/live" ? `?next=${encodeURIComponent(next)}` : ""}`}>
            Back to sign in
          </Link>
        </Button>
      </AuthCard>
    )
  }

  return (
    <AuthCard
      title="Create account"
      description="One account for connections, mood presets, and cloud sync."
      footer={
        <p className="text-center text-[13px] text-[color:var(--haven-muted)]">
          Already have an account?{" "}
          <Link
            href={`/login${next !== "/live" ? `?next=${encodeURIComponent(next)}` : ""}`}
            className="font-semibold text-teal-800 underline-offset-2 hover:underline"
          >
            Sign in
          </Link>
        </p>
      }
    >
      <form action={formAction} className="flex flex-col gap-4">
        {state.error ? <AuthAlert variant="error">{state.error}</AuthAlert> : null}
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
          <PasswordField
            id="password"
            name="password"
            autoComplete="new-password"
            showStrengthHint
          />
        </AuthFormField>
        <AuthFormField
          id="confirmPassword"
          label="Confirm password"
          error={state.fieldErrors?.confirmPassword}
        >
          <PasswordField id="confirmPassword" name="confirmPassword" autoComplete="new-password" />
        </AuthFormField>
        <p className="text-[12px] leading-relaxed text-[color:var(--haven-muted)]">
          By creating an account, you agree to use Haven on your own devices and network.
        </p>
        <Button
          type="submit"
          disabled={pending}
          className="h-11 w-full bg-[color:var(--haven-ink)] text-[color:var(--haven-paper)]"
        >
          {pending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
          {pending ? "Creating account…" : "Create account"}
        </Button>
      </form>
    </AuthCard>
  )
}
