import { NextResponse } from "next/server"

import { createSupabaseServerClient } from "@/lib/supabase/server"

export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url)
  const code = searchParams.get("code")
  const next = searchParams.get("next") ?? "/live"
  const authError = searchParams.get("error_description") ?? searchParams.get("error")

  if (authError) {
    const loginUrl = new URL("/login", origin)
    loginUrl.searchParams.set("error", authError)
    return NextResponse.redirect(loginUrl)
  }

  if (code) {
    const supabase = await createSupabaseServerClient()
    const { error } = await supabase.auth.exchangeCodeForSession(code)
    if (error) {
      const loginUrl = new URL("/login", origin)
      loginUrl.searchParams.set("error", error.message)
      return NextResponse.redirect(loginUrl)
    }
  }

  const destination = next.startsWith("/") ? next : "/live"
  return NextResponse.redirect(`${origin}${destination}`)
}
