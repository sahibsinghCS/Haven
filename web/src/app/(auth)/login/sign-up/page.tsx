import { Suspense } from "react"

import { SignUpForm } from "@/components/auth/sign-up-form"
import { AuthCard } from "@/components/auth/auth-card"
import { isSupabaseAuthEnabled } from "@/lib/supabase/env"
import { redirect } from "next/navigation"

export default async function SignUpPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string }>
}) {
  if (!isSupabaseAuthEnabled()) {
    redirect("/login")
  }

  const params = await searchParams
  const next = params.next?.startsWith("/") ? params.next : "/live"

  return (
    <Suspense
      fallback={
        <AuthCard title="Create account" description="Loading…">
          <div className="h-32 animate-pulse rounded-xl bg-stone-100/80" />
        </AuthCard>
      }
    >
      <SignUpForm next={next} />
    </Suspense>
  )
}
