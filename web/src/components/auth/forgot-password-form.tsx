"use client"

import Link from "next/link"
import { useActionState } from "react"
import { Loader2 } from "lucide-react"

import { requestPasswordReset, type AuthActionState } from "@/app/(auth)/actions"
import { AuthAlert } from "@/components/auth/auth-alert"
import { AuthCard } from "@/components/auth/auth-card"
import { AuthFormField, authInputClassName } from "@/components/auth/auth-form-field"
import { Input } from "@/components/ui/input"
import { havenBtnPrimary } from "@/components/roomos/haven-primitives"
import { cn } from "@/lib/utils"

const initialState: AuthActionState = {}

export function ForgotPasswordForm() {
  const [state, formAction, pending] = useActionState(requestPasswordReset, initialState)

  return (
    <AuthCard
      title="Reset password"
      description="Enter your account email and we’ll send a reset link."
      footer={
        <p className="text-center text-[13px] text-[color:var(--haven-muted)]">
          <Link href="/login" className="font-semibold text-teal-800 underline-offset-2 hover:underline">
            Back to sign in
          </Link>
        </p>
      }
    >
      {state.success ? (
        <AuthAlert variant="success">{state.success}</AuthAlert>
      ) : (
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
          <button type="submit" disabled={pending} className={cn(havenBtnPrimary, "w-full")}>
            {pending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
            {pending ? "Sending…" : "Send reset link"}
          </button>
        </form>
      )}
    </AuthCard>
  )
}
