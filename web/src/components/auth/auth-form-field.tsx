"use client"

import { Label } from "@/components/ui/label"
import { cn } from "@/lib/utils"
import { roomosUi } from "@/lib/roomos/roomos-ui"

export function AuthFormField({
  id,
  label,
  hint,
  error,
  children,
  className,
}: {
  id: string
  label: string
  hint?: string
  error?: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn("space-y-2", className)}>
      <Label htmlFor={id} className="text-[13px] font-medium text-[color:var(--haven-ink)]">
        {label}
      </Label>
      {children}
      {hint && !error ? (
        <p className="text-[12px] leading-relaxed text-[color:var(--haven-muted)]">{hint}</p>
      ) : null}
      {error ? (
        <p className="text-[12px] font-medium text-rose-700" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  )
}

export function authInputClassName(extra?: string) {
  return cn(
    "h-11 border-[color:var(--haven-line-strong)] bg-white/90 text-[color:var(--haven-ink)] placeholder:text-[color:var(--haven-faint)]",
    roomosUi.focusRingLight,
    extra,
  )
}
