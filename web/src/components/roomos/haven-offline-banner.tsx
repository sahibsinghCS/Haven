"use client"

import { WifiOff } from "lucide-react"

import { cn } from "@/lib/utils"
import { roomosUi } from "@/lib/roomos/roomos-ui"
import { HavenModeBadge } from "@/components/roomos/haven-mode-badge"
import { HavenOperatorActions } from "@/components/roomos/haven-operator-actions"

const CONTEXT_COPY: Record<
  "preferences" | "connections" | "settings" | "rhythm",
  { title: string; description: string }
> = {
  preferences: {
    title: "Editing browser only defaults",
    description:
 "Haven is offline. Changes save in this browser until the backend is running. nothing syncs to disk.",
  },
  connections: {
    title: "Device tests need the API",
    description:
      "Plug and light commands cannot run until Haven is running on this machine. Form state is kept in the browser.",
  },
  settings: {
    title: "Settings stored locally",
    description:
      "Cannot reach Haven on this machine. Values persist in the browser until npm run demo is running.",
  },
  rhythm: {
    title: "Rhythm needs the API",
    description:
      "Mood time and highlights are read from local inference logs on this machine. Start Haven to load your rhythm.",
  },
}

export function HavenOfflineBanner({
  context,
  className,
}: {
  context: "preferences" | "connections" | "settings" | "rhythm"
  className?: string
}) {
  const copy = CONTEXT_COPY[context]

  return (
    <div
      className={cn(
        roomosUi.prefsCallout,
        "border-stone-400/30 bg-stone-100/90 px-4 py-4 sm:px-5",
        className,
      )}
      role="status"
    >
      <div className="flex flex-wrap items-start gap-3">
        <WifiOff className="mt-0.5 size-4 shrink-0 text-stone-600" aria-hidden />
        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <HavenModeBadge mode="api_offline" size="md" className="!tracking-[0.12em]" />
            <p className="text-sm font-semibold text-[color:var(--haven-ink)]">{copy.title}</p>
          </div>
          <p className="text-[12.5px] leading-relaxed text-[color:var(--haven-muted)]">
            {copy.description}
          </p>
          <HavenOperatorActions
            variant="light"
            actions={[
              { step: "npm run demo", detail: "From repo root on this machine" },
              { step: "Verify GET /api/live/status", detail: "http://localhost:8000" },
              { step: "Reload this page" },
            ]}
          />
        </div>
      </div>
    </div>
  )
}
