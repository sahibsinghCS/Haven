import type { ReactNode } from "react"

import { cn } from "@/lib/utils"
import { roomosUi } from "@/lib/roomos/roomos-ui"

export function AuthCard({
  title,
  description,
  children,
  footer,
  className,
}: {
  title: string
  description?: string
  children: ReactNode
  footer?: ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        roomosUi.prefsPresetCard,
        "w-full max-w-md p-6 sm:p-8",
        className,
      )}
    >
      <header className="mb-6">
        <h1 className="font-serif text-[clamp(1.75rem,4vw,2.1rem)] font-medium tracking-[-0.03em] text-[color:var(--haven-ink)]">
          {title}
        </h1>
        {description ? (
          <p className="mt-2 text-[14px] leading-relaxed text-[color:var(--haven-muted)]">{description}</p>
        ) : null}
      </header>
      {children}
      {footer ? <div className="mt-6 border-t border-[color:var(--haven-line)] pt-5">{footer}</div> : null}
    </div>
  )
}
