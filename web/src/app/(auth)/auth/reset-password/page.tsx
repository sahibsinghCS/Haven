import { redirect } from "next/navigation"

import { ResetPasswordForm } from "@/components/auth/reset-password-form"
import { isSupabaseAuthEnabled } from "@/lib/supabase/env"

export default function ResetPasswordPage() {
  if (!isSupabaseAuthEnabled()) {
    redirect("/login")
  }

  return <ResetPasswordForm />
}
