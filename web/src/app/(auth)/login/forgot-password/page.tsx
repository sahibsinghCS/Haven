import { redirect } from "next/navigation"

import { ForgotPasswordForm } from "@/components/auth/forgot-password-form"
import { isSupabaseAuthEnabled } from "@/lib/supabase/env"

export default function ForgotPasswordPage() {
  if (!isSupabaseAuthEnabled()) {
    redirect("/login")
  }

  return <ForgotPasswordForm />
}
