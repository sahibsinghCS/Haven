"use client"

import type { ReactNode } from "react"
import { useState } from "react"
import dynamic from "next/dynamic"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { TooltipProvider } from "@/components/ui/tooltip"
import { Toaster } from "@/components/ui/sonner"

const ReactQueryDevtools = dynamic(
  () =>
    import("@tanstack/react-query-devtools").then((m) => m.ReactQueryDevtools),
  { ssr: false },
)

export function AppProviders({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            refetchOnWindowFocus: false,
          },
        },
      }),
  )

  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider delayDuration={200}>
        {children}
        <Toaster closeButton position="bottom-right" richColors={false} />
      </TooltipProvider>
      {process.env.NODE_ENV === "development" && process.env.NEXT_PUBLIC_RQ_DEVTOOLS === "1" ? (
        <ReactQueryDevtools buttonPosition="top-right" />
      ) : null}
    </QueryClientProvider>
  )
}
