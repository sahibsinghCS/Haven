import { createServerClient } from "@supabase/ssr"
import { NextResponse, type NextRequest } from "next/server"

import { getSupabasePublicConfig } from "@/lib/supabase/env"

const PROTECTED_PREFIXES = [
  "/live",
  "/review",
  "/rhythm",
  "/preferences",
  "/connections",
  "/settings",
]

const AUTH_PAGES = ["/login"]

function isProtectedPath(pathname: string): boolean {
  return PROTECTED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  )
}

function isAuthPage(pathname: string): boolean {
  return AUTH_PAGES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  )
}

function isAuthCallback(pathname: string): boolean {
  return pathname === "/auth/callback" || pathname.startsWith("/auth/reset-password")
}

export async function updateSession(request: NextRequest) {
  const config = getSupabasePublicConfig()
  const { pathname } = request.nextUrl

  if (!config) {
    return NextResponse.next({ request })
  }

  let supabaseResponse = NextResponse.next({ request })

  const supabase = createServerClient(config.url, config.anonKey, {
    cookies: {
      getAll() {
        return request.cookies.getAll()
      },
      setAll(cookiesToSet) {
        cookiesToSet.forEach(({ name, value }) => {
          request.cookies.set(name, value)
        })
        supabaseResponse = NextResponse.next({ request })
        cookiesToSet.forEach(({ name, value, options }) => {
          supabaseResponse.cookies.set(name, value, options)
        })
      },
    },
  })

  const {
    data: { user },
  } = await supabase.auth.getUser()

  if (isProtectedPath(pathname) && !user) {
    const loginUrl = request.nextUrl.clone()
    loginUrl.pathname = "/login"
    loginUrl.searchParams.set("next", `${pathname}${request.nextUrl.search}`)
    return NextResponse.redirect(loginUrl)
  }

  if (isAuthPage(pathname) && !isAuthCallback(pathname) && user) {
    const next = request.nextUrl.searchParams.get("next") || "/live"
    const redirectUrl = request.nextUrl.clone()
    const safeNext = next.startsWith("/") ? next : "/live"
    const q = safeNext.indexOf("?")
    redirectUrl.pathname = q >= 0 ? safeNext.slice(0, q) : safeNext
    redirectUrl.search = q >= 0 ? safeNext.slice(q) : ""
    return NextResponse.redirect(redirectUrl)
  }

  return supabaseResponse
}
