"use client"

import { useQuery } from "@tanstack/react-query"

import { evaluateSetupHealth } from "@/lib/roomos/setup-health"

export function useSetupHealth(enabled = true) {
  return useQuery({
    queryKey: ["roomos", "setup-health"],
    queryFn: ({ signal }) => evaluateSetupHealth(signal),
    enabled,
    staleTime: 8_000,
    refetchInterval: (query) => {
      const ready = query.state.data?.readyForLive
      return ready ? 30_000 : 10_000
    },
  })
}
