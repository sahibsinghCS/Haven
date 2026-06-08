"use client"

import { useActionState } from "react"
import { Loader2 } from "lucide-react"

import { updatePassword, type AuthActionState } from "@/app/(auth)/actions"
import { AuthAlert } from "@/components/auth/auth-alert"
import { AuthCard } from "@/components/auth/auth-card"
import { AuthFormField } from "@/components/auth/auth-form-field"
import { PasswordField } from "@/components/auth/password-field"
import { Button } from "@/components/ui/button"

const initialState: AuthActionState = {}

export function ResetPasswordForm() {
  const [state, formAction, pending] = useActionState(updatePassword, initialState)

  return (
    <AuthCard
      title="Choose a new password"
      description="Enter a new password for your Haven account."
    >
      <form action={formAction} className="flex flex-col gap-4">
        {state.error ? <AuthAlert variant="error">{state.error}</AuthAlert> : null}
        <AuthFormField id="password" label="New password" error={state.fieldErrors?.password}>
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
        <Button
          type="submit"
          disabled={pending}
          className="h-11 w-full bg-[color:var(--haven-ink)] text-[color:var(--haven-paper)]"
        >
          {pending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
          {pending ? "Updating…" : "Update password"}
        </Button>
      </form>
    </AuthCard>
  )
}
