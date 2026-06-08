import { cn } from "@/lib/utils"
import { roomosUi } from "@/lib/roomos/roomos-ui"

export function AuthAlert({
  variant = "error",
  children,
}: {
  variant?: "error" | "success"
  children: React.ReactNode
}) {
  return (
    <div
      role="alert"
      className={cn(
        "rounded-xl border px-3 py-2.5 text-[13px] leading-relaxed",
        variant === "error"
          ? roomosUi.prefsAlertPanel
          : "border-teal-700/25 bg-teal-50/90 text-teal-950",
      )}
    >
      {children}
    </div>
  )
}
