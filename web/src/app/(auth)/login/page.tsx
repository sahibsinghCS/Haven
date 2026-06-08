import Link from "next/link"
import { Suspense } from "react"

import { SignInForm } from "@/components/auth/sign-in-form"
import { AuthCard } from "@/components/auth/auth-card"
import { Button } from "@/components/ui/button"
import { isSupabaseAuthEnabled } from "@/lib/supabase/env"

function SignInWithNext({ next, authError }: { next: string; authError?: string }) {
  return <SignInForm next={next} authError={authError} />
}

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string; error?: string }>
}) {
  const params = await searchParams
  const next = params.next?.startsWith("/") ? params.next : "/live"
  const authError = params.error?.trim() || undefined

  if (!isSupabaseAuthEnabled()) {
    return (
      <AuthCard
        title="Sign in unavailable"
        description="Supabase is not configured for this web app."
      >
        <p className="text-[14px] leading-relaxed text-[color:var(--haven-muted)]">
          Add <span className="font-mono text-[12px]">NEXT_PUBLIC_SUPABASE_URL</span> and{" "}
          <span className="font-mono text-[12px]">NEXT_PUBLIC_SUPABASE_ANON_KEY</span> to{" "}
          <span className="font-mono text-[12px]">web/.env.local</span>, then restart the dev server.
        </p>
        <Button asChild variant="outline" className="mt-6 w-full">
          <Link href="/live">Continue without account</Link>
        </Button>
      </AuthCard>
    )
  }

  return (
    <Suspense
      fallback={
        <AuthCard title="Sign in" description="Loading…">
          <div className="h-32 animate-pulse rounded-xl bg-stone-100/80" />
        </AuthCard>
      }
    >
      <SignInWithNext next={next} authError={authError} />
    </Suspense>
  )
}
