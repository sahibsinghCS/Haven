"use client"

export function HavenOperatorActions({
  actions,
  variant = "dark",
}: {
  actions: Array<{ step: string; detail?: string }>
  variant?: "dark" | "light"
}) {
  const isDark = variant === "dark"
  return (
    <ol
      className={
        isDark
          ? "space-y-2.5 text-left text-[13px] text-zinc-300"
          : "space-y-2.5 text-left text-[13px] text-[color:var(--haven-muted)]"
      }
    >
      {actions.map((action, i) => (
        <li key={action.step} className="flex gap-2">
          <span
            className={
              isDark
                ? "font-mono text-[11px] font-semibold tabular-nums text-zinc-500"
                : "font-mono text-[11px] font-semibold tabular-nums text-[color:var(--haven-faint)]"
            }
          >
            {i + 1}.
          </span>
          <span>
            <span className={isDark ? "font-medium text-zinc-100" : "font-medium text-[color:var(--haven-ink)]"}>
              {action.step}
            </span>
            {action.detail ? (
              <span className={isDark ? "mt-0.5 block text-[11px] text-zinc-500" : "mt-0.5 block text-[11px] text-[color:var(--haven-faint)]"}>
                {action.detail}
              </span>
            ) : null}
          </span>
        </li>
      ))}
    </ol>
  )
}
