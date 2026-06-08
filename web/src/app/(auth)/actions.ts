"use server"

import { headers } from "next/headers"
import { redirect } from "next/navigation"
import { z } from "zod"

import { createSupabaseServerClient } from "@/lib/supabase/server"
import { getSupabasePublicConfig } from "@/lib/supabase/env"

export type AuthActionState = {
  error?: string
  fieldErrors?: Record<string, string>
  success?: string
  needsEmailConfirmation?: boolean
}

const emailSchema = z.string().email("Enter a valid email address.")
const passwordSchema = z.string().min(6, "Password must be at least 6 characters.")

const signInSchema = z.object({
  email: emailSchema,
  password: z.string().min(1, "Enter your password."),
})

const signUpSchema = z.object({
  email: emailSchema,
  password: passwordSchema,
  confirmPassword: z.string().min(1, "Confirm your password."),
}).refine((data) => data.password === data.confirmPassword, {
  message: "Passwords do not match.",
  path: ["confirmPassword"],
})

const forgotPasswordSchema = z.object({
  email: emailSchema,
})

const resetPasswordSchema = z.object({
  password: passwordSchema,
  confirmPassword: z.string().min(1, "Confirm your password."),
}).refine((data) => data.password === data.confirmPassword, {
  message: "Passwords do not match.",
  path: ["confirmPassword"],
})

async function siteOrigin(): Promise<string> {
  const headerList = await headers()
  const host = headerList.get("x-forwarded-host") ?? headerList.get("host")
  const proto = headerList.get("x-forwarded-proto") ?? "http"
  if (host) return `${proto}://${host}`
  return "http://127.0.0.1:3000"
}

function fieldErrorsFromZod(error: z.ZodError): Record<string, string> {
  const out: Record<string, string> = {}
  for (const issue of error.issues) {
    const key = issue.path[0]
    if (typeof key === "string" && !out[key]) {
      out[key] = issue.message
    }
  }
  return out
}

function requireSupabase() {
  if (!getSupabasePublicConfig()) {
    throw new Error("Supabase is not configured.")
  }
}

export async function signInWithEmail(
  _prev: AuthActionState,
  formData: FormData,
): Promise<AuthActionState> {
  requireSupabase()
  const parsed = signInSchema.safeParse({
    email: formData.get("email"),
    password: formData.get("password"),
  })
  if (!parsed.success) {
    return { fieldErrors: fieldErrorsFromZod(parsed.error) }
  }

  const supabase = await createSupabaseServerClient()
  const { error } = await supabase.auth.signInWithPassword({
    email: parsed.data.email,
    password: parsed.data.password,
  })
  if (error) {
    return { error: error.message }
  }

  const next = String(formData.get("next") || "/live")
  redirect(next.startsWith("/") ? next : "/live")
}

export async function signUpWithEmail(
  _prev: AuthActionState,
  formData: FormData,
): Promise<AuthActionState> {
  requireSupabase()
  const parsed = signUpSchema.safeParse({
    email: formData.get("email"),
    password: formData.get("password"),
    confirmPassword: formData.get("confirmPassword"),
  })
  if (!parsed.success) {
    return { fieldErrors: fieldErrorsFromZod(parsed.error) }
  }

  const origin = await siteOrigin()
  const supabase = await createSupabaseServerClient()
  const { data, error } = await supabase.auth.signUp({
    email: parsed.data.email,
    password: parsed.data.password,
    options: {
      emailRedirectTo: `${origin}/auth/callback?next=/live`,
    },
  })
  if (error) {
    return { error: error.message }
  }

  if (data.session) {
    redirect("/live")
  }

  return {
    success: "Check your email for a confirmation link, then sign in.",
    needsEmailConfirmation: true,
  }
}

export async function signOutAction(): Promise<void> {
  requireSupabase()
  const supabase = await createSupabaseServerClient()
  await supabase.auth.signOut()
  redirect("/login")
}

export async function requestPasswordReset(
  _prev: AuthActionState,
  formData: FormData,
): Promise<AuthActionState> {
  requireSupabase()
  const parsed = forgotPasswordSchema.safeParse({
    email: formData.get("email"),
  })
  if (!parsed.success) {
    return { fieldErrors: fieldErrorsFromZod(parsed.error) }
  }

  const origin = await siteOrigin()
  const supabase = await createSupabaseServerClient()
  const { error } = await supabase.auth.resetPasswordForEmail(parsed.data.email, {
    redirectTo: `${origin}/auth/callback?next=/auth/reset-password`,
  })
  if (error) {
    return { error: error.message }
  }

  return {
    success: "If an account exists for that email, we sent a reset link.",
  }
}

export async function updatePassword(
  _prev: AuthActionState,
  formData: FormData,
): Promise<AuthActionState> {
  requireSupabase()
  const parsed = resetPasswordSchema.safeParse({
    password: formData.get("password"),
    confirmPassword: formData.get("confirmPassword"),
  })
  if (!parsed.success) {
    return { fieldErrors: fieldErrorsFromZod(parsed.error) }
  }

  const supabase = await createSupabaseServerClient()
  const { error } = await supabase.auth.updateUser({
    password: parsed.data.password,
  })
  if (error) {
    return { error: error.message }
  }

  redirect("/live")
}
